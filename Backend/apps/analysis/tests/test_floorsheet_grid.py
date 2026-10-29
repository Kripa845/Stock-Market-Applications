"""Floor Sheet Summary grid: bucket boundaries, cell metrics, closing rules, the checks and the API."""

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.test import TestCase
from rest_framework.test import APIClient

from apps.analysis.services.floorsheet_grid import bucket_count, build_grid, serialize_grid
from apps.companies.models import Company, TrackedCompany
from apps.floorsheet.models import FloorsheetTransaction
from apps.market_data.models import DailyPrice
from apps.users.models import CustomRole, User, UserCompanyAccess

NPT = ZoneInfo("Asia/Kathmandu")
DAY = date(2026, 10, 9)
PREV = date(2026, 10, 8)
VWAP_ERA_DAY = date(2025, 8, 12)
VWAP_ERA_PREV = date(2025, 8, 11)


def at(hour, minute, second=0, micro=0, day=DAY):
    return datetime(day.year, day.month, day.day, hour, minute, second, micro, tzinfo=NPT)


class GridTestCase(TestCase):

    def setUp(self):
        self.company = self.tracked("NABIL")
        self.seq = 0

    def tracked(self, symbol):
        company = Company.objects.create(symbol=symbol, name=symbol, sector="Banking")
        TrackedCompany.objects.create(company=company, is_tracked=True)
        return company

    def trade(self, when, rate, quantity, company=None, day=DAY):
        self.seq += 1
        return FloorsheetTransaction.objects.create(
            company=company or self.company, date=day, trade_time=when,
            transaction_id=f"{day:%Y%m%d}01{self.seq:06d}", buyer_broker="1", seller_broker="2",
            quantity=quantity, rate=Decimal(rate), amount=Decimal(rate) * quantity,
        )

    def price(self, day, close, company=None, **fields):
        return DailyPrice.objects.create(
            company=company or self.company, source="crawled", date=day,
            open=close, high=close, low=close, close=Decimal(close),
            volume=fields.pop("volume", 0), turnover=fields.pop("turnover", 0), **fields,
        )

    def daily_from_trades(self, day=DAY, company=None, **fields):
        """The crawled daily row the exchange would publish for the trades entered so far."""
        trades = FloorsheetTransaction.objects.filter(company=company or self.company, date=day)
        return self.price(
            day, fields.pop("close"), company,
            volume=sum(t.quantity for t in trades),
            turnover=sum(t.amount for t in trades),
            transactions=trades.count(),
            **fields,
        )

    def row(self, grid, symbol="NABIL"):
        return next(c for c in grid["companies"] if c["symbol"] == symbol)

    def checks(self, grid):
        return {c["key"]: c for c in grid["checks"]}


class BucketTests(GridTestCase):

    def test_minute_boundaries(self):
        self.trade(at(11, 0, 0), "100", 10)
        self.trade(at(11, 0, 59, 999999), "101", 20)
        self.trade(at(11, 1, 0), "102", 30)
        cells = self.row(build_grid(DAY, 1))["cells"]
        self.assertEqual(sorted(cells), [0, 1])
        self.assertEqual((cells[0]["volume"], cells[0]["trade_count"]), (30, 2))
        self.assertEqual((cells[1]["volume"], cells[1]["trade_count"]), (30, 1))

    def test_five_minute_boundary(self):
        self.trade(at(11, 4, 59), "100", 10)
        self.trade(at(11, 5, 0), "100", 10)
        self.assertEqual(sorted(self.row(build_grid(DAY, 5))["cells"]), [0, 1])

    def test_pre_open_fill_folds_into_first_bucket(self):
        self.trade(at(10, 46, 0), "100", 10)
        self.trade(at(11, 0, 30), "101", 10)
        grid = build_grid(DAY, 1)
        self.assertEqual(grid["pre_open_trades"], 1)
        cell = self.row(grid)["cells"][0]
        self.assertEqual((cell["open"], cell["close"], cell["trade_count"]), (Decimal("100"), Decimal("101"), 2))
        self.assertEqual(self.checks(grid)["placement"]["status"], "pass")

    def test_bucket_counts_cover_the_session(self):
        self.assertEqual([bucket_count(m) for m in (1, 5, 10, 15, 30, 45)], [240, 48, 24, 16, 8, 6])
        self.trade(at(14, 59, 59), "100", 10)
        grid = build_grid(DAY, 45)
        self.assertEqual(len(grid["buckets"]), 6)
        self.assertEqual(sorted(self.row(grid)["cells"]), [5])
        self.assertEqual(serialize_grid(grid)["buckets"][-1], "14:45")


class CellMetricTests(GridTestCase):

    def test_cell_values_and_change_across_skipped_buckets(self):
        self.price(PREV, "100")
        self.trade(at(11, 0, 5), "102", 10)
        self.trade(at(11, 0, 40), "104", 30)
        # 11:01-11:02 have no trades: 11:03 compares with 11:00's close.
        self.trade(at(11, 3, 0), "99", 20)
        cells = self.row(build_grid(DAY, 1))["cells"]

        first = cells[0]
        self.assertEqual(first["volume"], 40)
        self.assertEqual(first["trade_count"], 2)
        self.assertEqual(first["turnover"], Decimal("1020") + Decimal("3120"))
        self.assertEqual(first["close"], Decimal("104"))
        self.assertEqual(first["vwap"], Decimal("4140") / 40)
        self.assertEqual(first["change_pct"], Decimal("4"))
        self.assertNotIn(1, cells)
        self.assertEqual(cells[3]["change_pct"], (Decimal("99") - Decimal("104")) * 100 / Decimal("104"))

    def test_no_previous_close_leaves_first_change_empty(self):
        self.trade(at(11, 0), "100", 10)
        self.trade(at(11, 1), "110", 10)
        cells = self.row(build_grid(DAY, 1))["cells"]
        self.assertIsNone(cells[0]["change_pct"])
        self.assertEqual(cells[1]["change_pct"], Decimal("10"))

    def test_regrouping_keeps_totals(self):
        for minute in range(0, 60, 3):
            self.trade(at(11, minute, 30), str(100 + minute), 10 + minute)
        totals = {
            m: {k: self.row(build_grid(DAY, m, with_checks=False))[k] for k in ("quantity", "trades", "turnover")}
            for m in (1, 5, 10, 15, 30, 45)
        }
        self.assertEqual(len({tuple(t.values()) for t in totals.values()}), 1)


class ClosingRuleTests(GridTestCase):

    def test_last_trade_rule_skips_odd_lots(self):
        self.price(PREV, "300")
        self.trade(at(14, 59, 40), "320", 95)
        self.trade(at(14, 59, 53), "320.6", 2)
        self.daily_from_trades(close="320", source_change_pct=Decimal("6.67"))
        grid = build_grid(DAY, 1)
        row = self.row(grid)
        self.assertEqual(row["last_trade_close"], Decimal("320.6"))
        self.assertEqual(row["session_close"], Decimal("320"))
        checks = self.checks(grid)
        self.assertEqual(checks["close"]["status"], "pass")
        self.assertEqual(checks["day_change"]["status"], "pass")
        self.assertIn("NABIL", checks["close"]["note"])

    def test_closing_vwap_rule_before_september_2025(self):
        day = VWAP_ERA_DAY
        self.price(VWAP_ERA_PREV, "100", )
        self.trade(at(14, 40, day=day), "90", 100, day=day)      # before the window
        self.trade(at(14, 45, day=day), "100", 100, day=day)
        self.trade(at(14, 50, day=day), "103", 50, day=day)
        self.trade(at(14, 55, day=day), "200", 5, day=day)       # odd lot, ignored
        self.daily_from_trades(day=day, close="101", source_change_pct=Decimal("1"))
        row = self.row(build_grid(day, 1))
        self.assertEqual(row["session_close"], Decimal("101.00"))
        self.assertEqual(row["day_change_pct"], Decimal("1"))


class CheckTests(GridTestCase):

    def setUp(self):
        super().setUp()
        self.other = self.tracked("ADBL")
        self.price(PREV, "100")
        self.price(PREV, "200", company=self.other)
        for second, (rate, qty) in enumerate([("101", 10), ("99.5", 15), ("102", 40)]):
            self.trade(at(11, 0, second * 20), rate, qty)
        self.trade(at(12, 30), "103", 25)
        self.trade(at(11, 10), "201", 10, company=self.other)

    def test_all_checks_pass_on_consistent_data(self):
        self.daily_from_trades(close="103", source_change_pct=Decimal("3"))
        self.daily_from_trades(company=self.other, close="201", source_change_pct=Decimal("0.5"))
        for minutes in (1, 5, 45):
            checks = build_grid(DAY, minutes)["checks"]
            self.assertEqual({c["key"]: c["status"] for c in checks}, {
                "quantity": "pass", "trades": "pass", "turnover": "pass", "vwap": "pass", "change": "pass",
                "regroup": "pass", "placement": "pass", "close": "pass", "day_change": "pass",
            })

    def test_mismatches_name_the_symbol_and_values(self):
        self.daily_from_trades(close="103", source_change_pct=Decimal("3"))
        self.daily_from_trades(company=self.other, close="205", source_change_pct=Decimal("2.5"))
        DailyPrice.objects.filter(company=self.company, date=DAY).update(volume=91)
        checks = self.checks(build_grid(DAY, 1))

        self.assertEqual(checks["quantity"]["status"], "fail")
        self.assertEqual(checks["quantity"]["mismatches"], [{
            "symbol": "NABIL", "bucket": None, "field": "quantity",
            "expected": 91, "actual": 90, "source": "crawled daily price",
        }])
        self.assertEqual([m["symbol"] for m in checks["close"]["mismatches"]], ["ADBL"])
        self.assertEqual([m["symbol"] for m in checks["day_change"]["mismatches"]], ["ADBL"])

    def test_official_checks_are_not_applicable_before_prices_are_crawled(self):
        checks = self.checks(build_grid(DAY, 1))
        self.assertEqual(checks["close"]["status"], "n/a")
        self.assertEqual(checks["day_change"]["status"], "n/a")
        # The first bucket (close 102) still compares with the previous session's close.
        self.assertEqual(self.row(build_grid(DAY, 1))["cells"][0]["change_pct"], Decimal("2"))


class FloorsheetGridAPITests(GridTestCase):
    URL = "/api/analysis/floorsheet-grid/"

    def setUp(self):
        super().setUp()
        self.other = self.tracked("ADBL")
        self.trade(at(11, 0), "100", 10)
        self.trade(at(11, 0), "200", 10, company=self.other)
        role = CustomRole.objects.create(name="tape", permissions=["view_trading_volume"])
        self.user = User.objects.create_user(username="u", email="u@example.com", password="Pw-12345!",
                                             role=User.Role.VIEWER, custom_role=role)
        UserCompanyAccess.objects.create(user=self.user, company=self.company, status=1)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_scoped_to_accessible_companies(self):
        response = self.client.get(self.URL, {"minutes": 5})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["date"], DAY.isoformat())
        self.assertEqual(body["dates"], [DAY.isoformat()])
        self.assertEqual(len(body["buckets"]), 48)
        self.assertEqual([c["symbol"] for c in body["companies"]], ["NABIL"])
        self.assertEqual(body["companies"][0]["cells"][0]["i"], 0)
        self.assertEqual(body["status"], "stored")

    def test_rejects_unknown_bucket_size_and_bad_date(self):
        self.assertEqual(self.client.get(self.URL, {"minutes": 7}).status_code, 400)
        self.assertEqual(self.client.get(self.URL, {"date": "28-10-2026"}).status_code, 400)

    def test_requires_permission(self):
        self.user.custom_role.permissions = []
        self.user.custom_role.save()
        self.assertEqual(self.client.get(self.URL).status_code, 403)
