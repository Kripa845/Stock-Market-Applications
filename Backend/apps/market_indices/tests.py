from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from apps.market_indices.models import IndexDaily, MarketIndex, MarketStockDaily
from apps.market_indices.services import aggregates
from apps.market_indices.services.calc import build_sector_rows, pct_change, pct_of

D = Decimal
TODAY = date(2026, 10, 9)
YESTERDAY = TODAY - timedelta(days=1)


class PureCalcTests(TestCase):
    def test_pct_change_normal(self):
        self.assertEqual(pct_change(110, 100), D("10"))

    def test_pct_change_guards(self):
        self.assertIsNone(pct_change(110, 0))
        self.assertIsNone(pct_change(110, None))
        self.assertIsNone(pct_change(None, 100))

    def test_pct_of(self):
        self.assertEqual(pct_of(25, 100), D("25"))
        self.assertIsNone(pct_of(25, 0))
        self.assertIsNone(pct_of(None, 100))

    def test_shares_sum_to_100(self):
        today = {
            "Banking": {"turnover": D(60), "volume": 600, "transactions": 30, "companies": 2, "transactions_reported": 2},
            "Hydro": {"turnover": D(30), "volume": 300, "transactions": 15, "companies": 1, "transactions_reported": 1},
            "Trading": {"turnover": D(10), "volume": 100, "transactions": 5, "companies": 1, "transactions_reported": 1},
        }
        rows, totals = build_sector_rows(today, {})
        self.assertEqual(totals["turnover"], D(100))
        self.assertAlmostEqual(float(sum(r["turnover_share_pct"] for r in rows)), 100.0, places=4)
        self.assertAlmostEqual(float(sum(r["volume_share_pct"] for r in rows)), 100.0, places=4)

    def test_sector_missing_yesterday_has_no_change(self):
        today = {"New": {"turnover": D(10), "volume": 1, "transactions": 1, "companies": 1, "transactions_reported": 1}}
        rows, _ = build_sector_rows(today, {})
        self.assertIsNone(rows[0]["tu_ch_pct"])
        self.assertIsNone(rows[0]["tu_ch"])

    def test_incomplete_transactions_flagged(self):
        today = {"A": {"turnover": D(10), "volume": 1, "transactions": 5, "companies": 2, "transactions_reported": 1}}
        rows, _ = build_sector_rows(today, {})
        self.assertFalse(rows[0]["transactions_complete"])


class AggregateTests(TestCase):
    def setUp(self):
        for symbol, sector, turnover, volume, trans in [
            ("NABIL", "Banking", 600, 1000, 50),
            ("NICA", "Banking", 400, 800, 40),
            ("NHPC", "HydroPower", 500, 900, None),
        ]:
            MarketStockDaily.objects.create(
                symbol=symbol, sector=sector, date=TODAY, close=100, prev_close=95,
                volume=volume, turnover=turnover, transactions=trans,
            )
        MarketStockDaily.objects.create(
            symbol="NABIL", sector="Banking", date=YESTERDAY, close=95, prev_close=94,
            volume=500, turnover=500, transactions=25,
        )

    def test_market_sector_table(self):
        data = aggregates.market_sector_table()
        self.assertEqual(data["as_of"], TODAY)
        self.assertEqual(data["base_date"], YESTERDAY)
        banking = next(r for r in data["rows"] if r["sector"] == "Banking")
        self.assertEqual(banking["turnover"], D("1000"))
        self.assertEqual(banking["tu_ch_pct"], D("100"))        # 500 -> 1000
        hydro = next(r for r in data["rows"] if r["sector"] == "HydroPower")
        self.assertFalse(hydro["transactions_complete"])
        self.assertIsNone(hydro["tu_ch_pct"])                    # no previous row

    def test_top_turnover_orders_desc(self):
        data = aggregates.market_top("turnover", limit=2)
        self.assertEqual([r["symbol"] for r in data["rows"]], ["NABIL", "NHPC"])
        self.assertEqual(data["rows"][0]["ch_pct"].quantize(D("0.01")), D("5.26"))

    def test_top_rejects_unknown_metric(self):
        with self.assertRaises(ValueError):
            aggregates.market_top("price")


class IndexTableTests(TestCase):
    def test_single_row_has_no_change(self):
        idx = MarketIndex.objects.create(code="NEPSE", name="NEPSE Index", kind="main")
        IndexDaily.objects.create(index=idx, date=TODAY, close=D("2596.59"))
        row = aggregates.index_table("main")[0]
        self.assertIsNone(row["ch"])
        self.assertIsNone(row["ch_pct"])

    def test_two_rows_change(self):
        idx = MarketIndex.objects.create(code="NEPSE", name="NEPSE Index", kind="main")
        IndexDaily.objects.create(index=idx, date=YESTERDAY, close=D("2591.81"))
        IndexDaily.objects.create(index=idx, date=TODAY, close=D("2596.59"))
        row = aggregates.index_table("main")[0]
        self.assertEqual(row["ch"], D("4.78"))
        self.assertEqual(row["ch_pct"].quantize(D("0.01")), D("0.18"))
