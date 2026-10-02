from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.companies.models import Company, TrackedCompany
from apps.crawler_runs.models import CrawlRun
from apps.crawler_runs.tasks import crawl_daily_prices, crawl_floorsheet
from apps.market_data.models import DailyPrice, DividendAnnouncement, FloorsheetTransaction, TradingHoliday
from apps.market_data.services import market_stats
from apps.market_data.services.price_fields import derive_price_fields
from apps.market_data.services.trading_days import is_market_day, market_closed_reason
from apps.market_intelligence.models import ProxyIndexSnapshot
from apps.market_intelligence.services.snapshots import compute_market_snapshots
from apps.users.models import User, WatchlistItem


MONDAY = date(2026, 9, 28)
TUESDAY = date(2026, 9, 29)


class TrackedMarketFixture(TestCase):
    """Seven tracked companies covering every summary bucket, plus one untracked company."""

    # symbol: (Monday close, Tuesday close); None = no row that day
    CLOSES = {
        "GAIN": (100, 105),          # +5%
        "UPC": (100, Decimal("109.9")),  # +9.9% -> positive circuit (tolerance, not exact 10%)
        "FLAT": (50, 50),            # unchanged
        "LOSE": (200, 190),          # -5%
        "CIRC": (Decimal("107.9"), Decimal("96.9")),  # -10.19% -> still a negative circuit
        "ZERO": (0, 10),             # prev_close = 0 -> no change, not "unchanged"
        "NOPREV": (None, 40),        # first session -> prev_close NULL
    }

    def setUp(self):
        cache.clear()
        self.companies = {}
        for symbol, closes in self.CLOSES.items():
            company = Company.objects.create(symbol=symbol, name=f"{symbol} Ltd", sector="Banking")
            TrackedCompany.objects.create(company=company, is_tracked=True)
            self.companies[symbol] = company
            for day, close in zip((MONDAY, TUESDAY), closes):
                if close is not None:
                    self.add_price(company, day, close)

        self.untracked = Company.objects.create(symbol="OUT", name="Untracked", sector="Banking")
        self.add_price(self.untracked, MONDAY, 100)
        self.add_price(self.untracked, TUESDAY, 150)

    def add_price(self, company, day, close, volume=1000, turnover=None, source="crawled"):
        close = Decimal(str(close))
        return DailyPrice.objects.create(
            company=company, source=source, date=day,
            open=close, high=close, low=close, close=close,
            volume=volume, turnover=turnover if turnover is not None else close * volume,
        )

    def add_trade(self, company, day, contract, buyer, seller, quantity, rate):
        return FloorsheetTransaction.objects.create(
            company=company, date=day, transaction_id=contract,
            buyer_broker=buyer, seller_broker=seller,
            quantity=quantity, rate=Decimal(str(rate)), amount=Decimal(str(rate)) * quantity,
        )


class DerivePriceFieldsTests(TrackedMarketFixture):

    def test_ltp_prev_close_and_transactions(self):
        gain = self.companies["GAIN"]
        self.add_trade(gain, TUESDAY, "1", "10", "20", 5, 105)
        self.add_trade(gain, TUESDAY, "2", "10", "30", 5, 105)
        self.add_trade(gain, TUESDAY, "TX-demo", "10", "30", 5, 105)  # synthetic, not counted

        derive_price_fields()

        tuesday = DailyPrice.objects.get(company=gain, date=TUESDAY)
        monday = DailyPrice.objects.get(company=gain, date=MONDAY)
        self.assertEqual(tuesday.ltp, Decimal("105"))
        self.assertEqual(tuesday.prev_close, Decimal("100"))
        self.assertEqual(tuesday.transactions, 2)
        self.assertIsNone(monday.prev_close)
        self.assertIsNone(monday.transactions)  # no floorsheet crawled: NULL, never 0

    def test_prev_close_recomputed_after_gap_filled(self):
        derive_price_fields()
        lose = self.companies["LOSE"]
        wednesday = TUESDAY + timedelta(days=1)
        thursday = TUESDAY + timedelta(days=2)
        self.add_price(lose, thursday, 180)
        derive_price_fields()
        self.assertEqual(DailyPrice.objects.get(company=lose, date=thursday).prev_close, Decimal("190"))

        self.add_price(lose, wednesday, 185)  # back-filled missing session
        derive_price_fields()
        self.assertEqual(DailyPrice.objects.get(company=lose, date=thursday).prev_close, Decimal("185"))


class MarketStatsTests(TrackedMarketFixture):

    def setUp(self):
        super().setUp()
        derive_price_fields()

    def rows_by_symbol(self):
        return {row["symbol"]: row for row in market_stats.ranked_by_change(TUESDAY)["rows"]}

    def test_gainer_loser_unchanged(self):
        rows = self.rows_by_symbol()
        self.assertEqual(rows["GAIN"]["change"], Decimal("5"))
        self.assertAlmostEqual(rows["GAIN"]["change_pct"], Decimal("5"), places=4)
        self.assertAlmostEqual(rows["LOSE"]["change_pct"], Decimal("-5"), places=4)
        self.assertEqual(rows["FLAT"]["change"], Decimal("0"))

    def test_prev_close_zero_and_missing_have_no_change(self):
        rows = self.rows_by_symbol()
        for symbol in ("ZERO", "NOPREV"):
            self.assertIsNone(rows[symbol]["change"])
            self.assertIsNone(rows[symbol]["change_pct"])

    def test_ranked_by_change_pct_with_nulls_last_and_untracked_excluded(self):
        symbols = [row["symbol"] for row in market_stats.ranked_by_change(TUESDAY)["rows"]]
        self.assertEqual(symbols[:5], ["UPC", "GAIN", "FLAT", "LOSE", "CIRC"])
        self.assertEqual(set(symbols[5:]), {"ZERO", "NOPREV"})
        self.assertNotIn("OUT", symbols)

    def test_sparkline_has_recent_closes_oldest_first(self):
        spark = self.rows_by_symbol()["GAIN"]["sparkline"]
        self.assertEqual([point["close"] for point in spark], [Decimal("100"), Decimal("105")])

    def test_summary_buckets_and_circuits(self):
        summary = market_stats.tracked_summary(TUESDAY)

        self.assertEqual(summary["tracked_count"], 7)
        self.assertEqual(summary["advanced"], 2)        # GAIN, UPC
        self.assertEqual(summary["declined"], 2)        # LOSE, CIRC
        self.assertEqual(summary["unchanged"], 1)       # FLAT
        self.assertEqual(summary["no_prev_close"], 2)   # ZERO, NOPREV
        self.assertEqual(summary["positive_circuit"], 1)  # UPC at +9.9%
        self.assertEqual(summary["negative_circuit"], 1)  # CIRC at -10.19%
        self.assertEqual(
            summary["advanced"] + summary["declined"] + summary["unchanged"] + summary["no_prev_close"],
            summary["tracked_count"],
        )

    def test_summary_defaults_to_latest_date(self):
        self.assertEqual(market_stats.tracked_summary()["trade_date"], TUESDAY)

    def test_summary_respects_company_access(self):
        ids = [self.companies["GAIN"].id, self.companies["LOSE"].id]
        summary = market_stats.tracked_summary(TUESDAY, ids)
        self.assertEqual(summary["tracked_count"], 2)

    def test_top_transactions_nulls_last(self):
        self.add_trade(self.companies["LOSE"], TUESDAY, "1", "1", "2", 10, 190)
        derive_price_fields()
        rows = market_stats.top_by("transactions", TUESDAY)["rows"]
        self.assertEqual(rows[0]["symbol"], "LOSE")
        self.assertEqual(rows[0]["transactions"], 1)
        self.assertTrue(all(row["transactions"] is None for row in rows[1:]))

    def test_book_closure_flag(self):
        DividendAnnouncement.objects.create(
            company=self.companies["LOSE"], fiscal_year="2082/83",
            bonus_pct=10, cash_pct=Decimal("0.5263"), book_closure_date=TUESDAY,
        )
        rows = self.rows_by_symbol()
        self.assertTrue(rows["LOSE"]["book_closure_in_window"])
        self.assertFalse(rows["GAIN"]["book_closure_in_window"])
        dividend = market_stats.dividend_rows()[0]
        self.assertEqual(dividend["total_pct"], Decimal("10.5263"))


class BrokerActivityTests(TrackedMarketFixture):

    def test_shares_sum_to_100_and_denominator(self):
        gain = self.companies["GAIN"]
        self.add_trade(gain, MONDAY, "1", "10", "20", 100, 100)    # 10,000
        self.add_trade(gain, TUESDAY, "2", "10", "30", 50, 105)    # 5,250
        self.add_trade(gain, TUESDAY, "3", " 20 ", "10", 30, 105)  # 3,150 (codes are trimmed)
        self.add_trade(gain, TUESDAY, "TX-1", "99", "98", 1000, 1)  # synthetic: excluded

        five, twenty = market_stats.broker_activity(gain.id)

        self.assertEqual(five["total_amount"], Decimal("18400"))
        self.assertEqual(five["sessions_available"], 2)
        shares = {row["broker"]: row["share_pct"] for row in five["brokers"]}
        self.assertNotIn("99", shares)
        self.assertAlmostEqual(sum(shares.values()), Decimal("100"), places=6)
        # broker 10: buys 10,000 + 5,250, sells 3,150 -> 18,400 / (2 * 18,400) = 50%
        self.assertAlmostEqual(shares["10"], Decimal("50"), places=6)
        broker_10 = next(row for row in five["brokers"] if row["broker"] == "10")
        self.assertEqual(broker_10["net_quantity"], 150 - 30)
        volume_total = sum(row["volume_share_pct"] for row in five["brokers"])
        self.assertAlmostEqual(volume_total, Decimal("100"), places=6)
        self.assertEqual(five["concentration"]["top_n"], 5)
        self.assertAlmostEqual(five["concentration"]["volume_share_pct"], Decimal("100"), places=6)

    def test_window_uses_latest_sessions(self):
        gain = self.companies["GAIN"]
        days = [MONDAY + timedelta(days=offset) for offset in range(7)]
        for index, day in enumerate(days):
            self.add_trade(gain, day, str(index), "1", "2", 10, 100)
        five, twenty = market_stats.broker_activity(gain.id)
        self.assertEqual(five["dates"], days[-5:])
        self.assertEqual(twenty["sessions_available"], 7)


class SignalsTests(TrackedMarketFixture):

    def test_insufficient_history_is_null_not_guessed(self):
        derive_price_fields()
        result = market_stats.signals(self.companies["GAIN"].id)
        self.assertEqual(result["trade_date"], TUESDAY)
        self.assertIsNone(result["moving_averages"]["ma5"]["value"])
        self.assertEqual(result["moving_averages"]["ma5"]["sessions"], 2)
        self.assertIsNone(result["volume_vs_20d_avg"]["ratio"])
        self.assertEqual(result["range_52w"]["sessions"], 2)
        self.assertEqual(result["range_52w"]["distance_from_high_pct"], Decimal("0"))

    def test_moving_averages_and_volume_ratio(self):
        company = Company.objects.create(symbol="LONG", name="Long Ltd", sector="Hydro")
        TrackedCompany.objects.create(company=company)
        day = date(2026, 6, 1)
        for index in range(21):
            self.add_price(company, day, 100 + index, volume=100 if index < 20 else 300)
            day += timedelta(days=1)
        derive_price_fields()
        result = market_stats.signals(company.id)
        self.assertEqual(result["moving_averages"]["ma5"]["value"], Decimal("118"))
        self.assertEqual(result["volume_vs_20d_avg"]["ratio"], Decimal("3"))


class TradingDayTests(TestCase):

    def test_weekday_holiday_is_skipped(self):
        holiday = date(2026, 10, 2)  # a Friday
        TradingHoliday.objects.create(date=holiday, name="Test holiday")
        self.assertFalse(is_market_day(holiday))
        self.assertIn("Test holiday", market_closed_reason(holiday))
        self.assertTrue(is_market_day(date(2026, 10, 1)))
        self.assertFalse(is_market_day(date(2026, 10, 3)))  # Saturday

    def test_scheduled_crawls_skip_holidays_without_starting_a_run(self):
        holiday = date(2026, 10, 2)
        TradingHoliday.objects.create(date=holiday, name="Test holiday")
        with mock.patch("django.utils.timezone.localdate", return_value=holiday):
            self.assertTrue(crawl_daily_prices()["skipped"])
            self.assertTrue(crawl_floorsheet()["skipped"])
        self.assertFalse(CrawlRun.objects.exists())


class EqualWeightBasketTests(TestCase):

    def test_equal_weight_averages_returns(self):
        heavy = Company.objects.create(symbol="HEAVY", name="Heavy", sector="Banking")
        light = Company.objects.create(symbol="LIGHT", name="Light", sector="Banking")
        for company, closes, turnover in ((heavy, (100, 105), 9000), (light, (200, 190), 1000)):
            for day, close in zip((MONDAY, TUESDAY), closes):
                DailyPrice.objects.create(
                    company=company, source="crawled", date=day, open=close, high=close,
                    low=close, close=close, volume=10, turnover=turnover,
                )

        compute_market_snapshots()

        row = ProxyIndexSnapshot.objects.get(date=TUESDAY)
        self.assertEqual(row.equal_weight_return_pct, Decimal("0"))       # (+5% - 5%) / 2
        self.assertEqual(row.daily_return_pct, Decimal("4"))               # (5*9000 - 5*1000) / 10000
        self.assertEqual(row.equal_weight_level, Decimal("1000"))
        self.assertEqual(ProxyIndexSnapshot.objects.get(date=MONDAY).equal_weight_level, Decimal("1000"))


class MarketApiTests(TrackedMarketFixture):

    def setUp(self):
        super().setUp()
        derive_price_fields()
        self.user = User.objects.create_user(
            username="market-admin", email="market-admin@example.test",
            password="unused-test-password", role=User.Role.ADMIN,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_summary_is_labelled_tracked(self):
        response = self.client.get("/api/market/summary/", {"date": TUESDAY.isoformat()})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["scope"], "tracked_companies")
        self.assertEqual(response.data["summary"]["tracked_count"], 7)
        self.assertEqual(response.data["units"]["turnover"], "NPR")

    def test_bad_date_is_400(self):
        self.assertEqual(self.client.get("/api/market/movers/", {"date": "2026-13-01"}).status_code, 400)

    def test_top_endpoints_and_unknown_symbol(self):
        for path in ("top-turnover", "top-volume", "top-transactions", "movers", "basket-index", "dividends"):
            self.assertEqual(self.client.get(f"/api/market/{path}/").status_code, 200, path)
        self.assertEqual(self.client.get("/api/market/brokers/OUT/").status_code, 404)  # untracked
        self.assertEqual(self.client.get("/api/market/signals/GAIN/").status_code, 200)

    def test_watchlist_add_list_remove(self):
        created = self.client.post("/api/market/watchlist/", {"symbol": "gain"}, format="json")
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data["symbol"], "GAIN")
        self.assertEqual(self.client.post("/api/market/watchlist/", {"symbol": "GAIN"}, format="json").status_code, 200)

        rows = self.client.get("/api/market/watchlist/").data["rows"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["ltp"], Decimal("105"))
        self.assertAlmostEqual(rows[0]["change_pct"], Decimal("5"), places=4)

        self.assertEqual(self.client.delete("/api/market/watchlist/GAIN/").status_code, 204)
        self.assertFalse(WatchlistItem.objects.exists())
        self.assertEqual(self.client.delete("/api/market/watchlist/GAIN/").status_code, 404)

    def test_requires_authentication(self):
        self.assertIn(APIClient().get("/api/market/summary/").status_code, (401, 403))


class PublicSnapshotTests(TrackedMarketFixture):

    def setUp(self):
        super().setUp()
        derive_price_fields()

    def test_anonymous_gets_only_public_fields(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer expired.or.invalid")  # stale token is ignored
        response = client.get("/api/market/public/snapshot/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["scope"], "tracked_companies")
        self.assertEqual(response.data["trade_date"], TUESDAY)
        self.assertEqual(response.data["summary"]["tracked_count"], 7)
        self.assertNotIn("total_transactions", response.data["summary"])
        mover = response.data["movers"][0]
        self.assertEqual(mover["symbol"], "UPC")
        self.assertEqual(
            set(mover),
            {"symbol", "name", "sector", "ltp", "prev_close", "change", "change_pct", "volume", "turnover", "sparkline"},
        )
        self.assertEqual(response.data["basket"]["label"], "Tracked Basket")
        self.assertNotIn("OUT", [row["symbol"] for row in response.data["movers"]])

