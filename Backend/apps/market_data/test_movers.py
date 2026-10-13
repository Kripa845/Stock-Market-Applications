"""Tests for services.movers -- the one definition of a tracked company's session change."""

import io
import logging
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.companies.models import Company, TrackedCompany
from apps.crawler_runs.models import CrawlRun
from apps.market_data.models import DailyPrice
from apps.market_data.services import movers
from apps.users.models import User

MONDAY = date(2026, 9, 28)
TUESDAY = date(2026, 9, 29)
HOLIDAY = date(2026, 9, 8)  # a Tuesday with no rows for anyone


def trading_days(start, count, holidays=(HOLIDAY,)):
    """Weekdays from ``start``, skipping weekends and ``holidays`` (test data only)."""
    days, day = [], start
    while len(days) < count:
        if day.weekday() < 5 and day not in holidays:
            days.append(day)
        day += timedelta(days=1)
    return days


class MoversFixture(TestCase):

    def setUp(self):
        cache.clear()
        self.companies = {}

    def company(self, symbol):
        if symbol not in self.companies:
            company = Company.objects.create(symbol=symbol, name=f"{symbol} Ltd", sector="Banking")
            TrackedCompany.objects.create(company=company, is_tracked=True)
            self.companies[symbol] = company
        return self.companies[symbol]

    def add(self, symbol, day, close, volume=1000, turnover=None, source_pct=None):
        close = Decimal(str(close))
        return DailyPrice.objects.create(
            company=self.company(symbol), source="crawled", date=day,
            open=close, high=close, low=close, close=close, volume=volume,
            turnover=Decimal(str(turnover)) if turnover is not None else close * volume,
            source_change_pct=None if source_pct is None else Decimal(str(source_pct)),
        )

    @staticmethod
    def symbols(rows):
        return [row["symbol"] for row in rows]

    def assert_reconciles(self, result):
        self.assertEqual(
            result["gainers_count"] + result["losers_count"] + result["unchanged_count"]
            + sum(result["excluded_counts"].values()),
            result["tracked_count"],
        )


class OneSessionTests(MoversFixture):

    def setUp(self):
        super().setUp()
        self.add("GAIN", MONDAY, 100); self.add("GAIN", TUESDAY, 105)
        self.add("LOSE", MONDAY, 200); self.add("LOSE", TUESDAY, 190)
        self.add("FLAT", MONDAY, 50); self.add("FLAT", TUESDAY, 50)
        self.add("NOROW", MONDAY, 100)                                     # no row on as_of
        self.add("NOVOL", MONDAY, 100); self.add("NOVOL", TUESDAY, 101, volume=0)
        self.add("ZERO", MONDAY, 0); self.add("ZERO", TUESDAY, 10)
        self.add("MISS", MONDAY - timedelta(days=3), 80); self.add("MISS", TUESDAY, 90)  # skipped Monday
        self.add("CIRC", MONDAY, Decimal("107.9")); self.add("CIRC", TUESDAY, Decimal("96.9"))  # -10.19%, no source %

    def bucket(self, result, symbol):
        rows = result["gainers"] + result["losers"] + result["unchanged"] + result["excluded"]
        return next(row for row in rows if row["symbol"] == symbol)

    def test_gainer_loser_unchanged(self):
        result = movers.tracked_movers("1D")
        self.assertEqual(result["as_of"], TUESDAY)
        self.assertEqual(result["base_date"], MONDAY)
        self.assertEqual(self.symbols(result["gainers"]), ["GAIN"])
        self.assertEqual(self.symbols(result["losers"]), ["LOSE"])
        self.assertEqual(self.symbols(result["unchanged"]), ["FLAT"])
        gain = result["gainers"][0]
        self.assertEqual(gain["close"], Decimal("105"))
        self.assertEqual(gain["prev_close"], Decimal("100"))
        self.assertEqual(gain["change"], Decimal("5"))
        self.assertEqual(gain["change_pct"], Decimal("5"))
        self.assertEqual(gain["change_basis"], "close_to_close")
        self.assertTrue(gain["unadjusted"])
        self.assertFalse(gain["possible_corporate_action"])
        self.assertEqual(gain["price_source"], "crawled")

    def test_exclusion_reasons(self):
        result = movers.tracked_movers("1D")
        self.assertEqual(result["excluded_counts"], {
            "missing_price": 1,              # NOROW
            "not_traded": 1,                 # NOVOL
            "missing_previous_session": 1,   # MISS
            "prev_close_zero": 1,            # ZERO
            "possible_corporate_action": 1,  # CIRC
        })
        self.assertEqual(result["not_traded_count"], 1)
        self.assertEqual(result["missing_price_count"], 1)
        self.assertEqual(self.bucket(result, "NOROW")["bucket"], "missing_price")
        self.assertIn("1 of 8 tracked companies have no crawled price", result["warning"])
        self.assertIn("1 of 8 tracked companies have no crawled price", movers.tracked_summary()["warning"])
        self.assertEqual(self.bucket(result, "MISS")["bucket"], "missing_previous_session")
        circ = self.bucket(result, "CIRC")
        self.assertTrue(circ["possible_corporate_action"])
        self.assertAlmostEqual(circ["close_to_close_change_pct"], Decimal("-10.1946"), places=4)

    def test_counts_reconcile_to_tracked_count(self):
        result = movers.tracked_movers("1D", limit=50)
        self.assertEqual(result["tracked_count"], 8)
        self.assert_reconciles(result)
        self.assertEqual(
            len(result["gainers"]) + len(result["losers"]) + len(result["unchanged"]) + len(result["excluded"]),
            result["tracked_count"],
        )

    def test_summary_uses_the_same_buckets(self):
        summary = movers.tracked_summary()
        result = movers.tracked_movers("1D")
        self.assertEqual(summary["advanced"], result["gainers_count"])
        self.assertEqual(summary["declined"], result["losers_count"])
        self.assertEqual(summary["unchanged"], result["unchanged_count"])
        self.assertEqual(summary["excluded_counts"], result["excluded_counts"])

    def test_sparkline_last_closes_oldest_first(self):
        spark = movers.tracked_movers("1D")["gainers"][0]["sparkline"]
        self.assertEqual([point["close"] for point in spark], [Decimal("100"), Decimal("105")])

    def test_requested_date_after_data_falls_back_to_last_completed_day(self):
        result = movers.tracked_movers("1D", requested_date=TUESDAY + timedelta(days=3))
        self.assertEqual(result["as_of"], TUESDAY)


class RankingTests(MoversFixture):

    def test_equal_change_pct_breaks_ties_by_turnover(self):
        self.add("SMALL", MONDAY, 100); self.add("SMALL", TUESDAY, 105, turnover=5000)
        self.add("BIG", MONDAY, 200); self.add("BIG", TUESDAY, 210, turnover=9000)
        self.add("DOWNA", MONDAY, 100); self.add("DOWNA", TUESDAY, 95, turnover=1000)
        self.add("DOWNB", MONDAY, 100); self.add("DOWNB", TUESDAY, 95, turnover=7000)
        result = movers.tracked_movers("1D")
        self.assertEqual(self.symbols(result["gainers"]), ["BIG", "SMALL"])
        self.assertEqual(self.symbols(result["losers"]), ["DOWNB", "DOWNA"])

    def test_day_with_no_gainers_is_not_padded(self):
        self.add("A", MONDAY, 100); self.add("A", TUESDAY, 99)
        self.add("B", MONDAY, 100); self.add("B", TUESDAY, 98)
        result = movers.tracked_movers("1D", limit=5)
        self.assertEqual(result["gainers"], [])
        self.assertEqual(result["gainers_count"], 0)
        self.assertEqual(self.symbols(result["losers"]), ["B", "A"])
        self.assertNotIn("warning", result)  # every tracked company has a row on as_of

    def test_limit_caps_lists_but_not_counts(self):
        for index in range(4):
            self.add(f"G{index}", MONDAY, 100); self.add(f"G{index}", TUESDAY, 101 + index)
        result = movers.tracked_movers("1D", limit=2)
        self.assertEqual(len(result["gainers"]), 2)
        self.assertEqual(result["gainers_count"], 4)
        self.assert_reconciles(result)

    def test_top_lists_sort_numerically_desc_with_unknown_trades_last(self):
        # Values chosen so text sorting ("9" > "10...") or ascending order would fail.
        for symbol, volume, turnover, trades in (
            ("A", 9, 900, None), ("B", 10000, 25_200_000, 9), ("C", 120, 4_000_000, 1000),
        ):
            self.add(symbol, MONDAY, 100)
            row = self.add(symbol, TUESDAY, 100, volume=volume, turnover=turnover)
            DailyPrice.objects.filter(pk=row.pk).update(transactions=trades)
        self.add("IDLE", MONDAY, 100); self.add("IDLE", TUESDAY, 100, volume=0, turnover=0)

        def top(metric):
            return self.symbols(movers.top_by(metric)["rows"])

        self.assertEqual(top("turnover"), ["B", "C", "A"])
        self.assertEqual(top("volume"), ["B", "C", "A"])
        self.assertEqual(top("transactions"), ["C", "B", "A"])   # NULL trade count last, IDLE excluded
        self.assertEqual(movers.top_by("volume", limit=1)["rows"][0]["volume"], 10000)


class SourceChangeTests(MoversFixture):

    def test_source_pct_used_and_marked_adjusted(self):
        # NABIL 2026-09-30: 566.00 -> 530.70 is -6.24% close-to-close, ShareSansar says -1.55%
        # (5% bonus book closure: the exchange's adjusted previous close was ~539.06).
        self.add("NABIL", MONDAY, Decimal("566.00"))
        self.add("NABIL", TUESDAY, Decimal("530.70"), source_pct="-1.55")
        row = movers.tracked_movers("1D")["losers"][0]
        self.assertEqual(row["change_pct"], Decimal("-1.55"))
        self.assertEqual(row["change_basis"], "source")
        self.assertTrue(row["adjusted"])
        self.assertFalse(row["unadjusted"])
        self.assertEqual(row["raw_prev_close"], Decimal("566.00"))
        self.assertAlmostEqual(row["prev_close"], Decimal("539.06"), places=2)
        self.assertAlmostEqual(row["close_to_close_change_pct"], Decimal("-6.2367"), places=4)

    def test_source_pct_matching_close_to_close_is_not_adjusted(self):
        self.add("UPPER", MONDAY, Decimal("189.10"))
        self.add("UPPER", TUESDAY, Decimal("191.00"), source_pct="1.00")
        row = movers.tracked_movers("1D")["gainers"][0]
        self.assertEqual(row["change_basis"], "source")
        self.assertFalse(row["adjusted"])

    def test_big_move_with_source_pct_is_ranked_not_excluded(self):
        self.add("CIRC", MONDAY, Decimal("107.9"))
        self.add("CIRC", TUESDAY, Decimal("96.9"), source_pct="-10.19")
        result = movers.tracked_movers("1D")
        self.assertEqual(self.symbols(result["losers"]), ["CIRC"])
        self.assertFalse(result["losers"][0]["possible_corporate_action"])
        self.assertEqual(result["excluded_counts"]["possible_corporate_action"], 0)


class MultiSessionTests(MoversFixture):

    def setUp(self):
        super().setUp()
        # Thu 3 Sep .. Fri 11 Sep 2026: crosses a weekend and the Tue 8 Sep holiday.
        self.days = trading_days(date(2026, 9, 3), 6)
        self.assertEqual(self.days, [date(2026, 9, d) for d in (3, 4, 7, 9, 10, 11)])

    def test_five_sessions_skip_weekend_and_holiday(self):
        for day, close in zip(self.days, (100, 101, 102, 103, 104, 108)):
            self.add("X", day, close)
        result = movers.tracked_movers("5S")
        self.assertEqual(result["as_of"], date(2026, 9, 11))
        self.assertEqual(result["base_date"], date(2026, 9, 3))
        self.assertEqual(result["period_label"], "5 sessions")
        row = result["gainers"][0]
        self.assertEqual(row["raw_prev_close"], Decimal("100"))
        self.assertEqual(row["change_pct"], Decimal("8"))
        self.assertTrue(row["unadjusted"])

    def test_source_pct_compounded_when_every_session_has_it(self):
        close = Decimal("100")
        self.add("Y", self.days[0], close)
        for day in self.days[1:]:
            close = (close * Decimal("1.01")).quantize(Decimal("0.01"))
            self.add("Y", day, close, source_pct="1")
        row = movers.tracked_movers("5S")["gainers"][0]
        self.assertEqual(row["change_basis"], "source")
        self.assertAlmostEqual(row["change_pct"], Decimal("5.101005"), places=4)  # 1.01^5 - 1

    def test_missing_source_pct_on_one_session_falls_back_unadjusted(self):
        self.add("Z", self.days[0], 100)
        for index, day in enumerate(self.days[1:]):
            self.add("Z", day, 100 + index + 1, source_pct=None if index == 2 else "1")
        row = movers.tracked_movers("5S")["gainers"][0]
        self.assertEqual(row["change_basis"], "close_to_close")
        self.assertTrue(row["unadjusted"])
        self.assertEqual(row["change_pct"], Decimal("5"))

    def test_twenty_sessions(self):
        days = trading_days(date(2026, 8, 24), 21)
        for index, day in enumerate(days):
            self.add("W", day, Decimal("100") + Decimal("0.25") * index)   # +5% over 20 sessions
            self.add("BIG", day, 100 + index)                               # +20%, no source %
        result = movers.tracked_movers("20S")
        self.assertEqual(result["base_date"], days[0])
        self.assertNotIn(HOLIDAY, days)
        self.assertEqual(result["period_label"], "20 sessions")
        self.assertEqual(self.symbols(result["gainers"]), ["W"])
        self.assertEqual(result["gainers"][0]["change_pct"], Decimal("5"))
        # Close-to-close beyond 10% with no source % is excluded, not ranked.
        self.assertEqual(self.symbols(result["excluded"]), ["BIG"])
        self.assertEqual(result["excluded"][0]["bucket"], "possible_corporate_action")

    def test_close_to_close_is_not_integer_divided(self):
        self.add("ODD", self.days[-2], 107)
        self.add("ODD", self.days[-1], 101)
        self.assertAlmostEqual(movers.tracked_movers("1D")["losers"][0]["change_pct"], Decimal("-5.607477"), places=5)

    def test_not_enough_history_says_so(self):
        for day in self.days:
            self.add("X", day, 100)
        result = movers.tracked_movers("20S")
        self.assertIsNone(result["base_date"])
        self.assertEqual(result["excluded_counts"]["missing_previous_session"], 1)
        self.assertIn("fewer than 21", result["reason"])


class EmptyDataTests(MoversFixture):

    def test_no_prices_returns_honest_empty_response(self):
        self.company("NABIL")
        result = movers.tracked_movers("1D")
        self.assertIsNone(result["as_of"])
        self.assertEqual(result["gainers"], [])
        self.assertEqual(result["losers"], [])
        self.assertEqual(result["tracked_count"], 1)
        self.assertIn("no completed trading day", result["reason"])
        self.assertIn("scrapy crawl trading_data", result["action"])

    def test_unverified_rows_are_ignored(self):
        company = self.company("SEED")
        for day, close in ((MONDAY, 100), (TUESDAY, 150)):
            DailyPrice.objects.create(company=company, source="unverified", date=day, open=close, high=close,
                                      low=close, close=close, volume=10, turnover=1000)
        self.assertIsNone(movers.tracked_movers("1D")["as_of"])


class MoversApiTests(MoversFixture):

    def setUp(self):
        super().setUp()
        self.add("GAIN", MONDAY, 100); self.add("GAIN", TUESDAY, 105)
        CrawlRun.objects.create(
            crawl_type=CrawlRun.CrawlType.TRADING, source="trading_data",
            status=CrawlRun.Status.SUCCESS, sources=["trading_data"],
        )
        user = User.objects.create_user(username="movers-admin", email="movers@example.test",
                                        password="unused-test-password", role=User.Role.ADMIN)
        self.client = APIClient()
        self.client.force_authenticate(user)

    def test_response_shape_and_provenance(self):
        data = self.client.get("/api/market/movers/", {"period": "1W"}).data
        self.assertEqual(data["period"], "5S")
        for key in ("as_of", "gainers", "losers", "tracked_count", "unchanged_count", "not_traded_count", "excluded", "excluded_counts"):
            self.assertIn(key, data)
        self.assertEqual(data["scope"], "tracked_companies")
        self.assertEqual(data["provenance"]["price_source"], "crawled")
        self.assertEqual(data["provenance"]["table"], "market_data_dailyprice")
        self.assertIsNotNone(data["provenance"]["last_price_crawl"])

    def test_one_day_payload(self):
        data = self.client.get("/api/market/movers/", {"period": "1D", "limit": 5}).data
        self.assertEqual(data["as_of"], TUESDAY)
        self.assertEqual(data["gainers"][0]["symbol"], "GAIN")
        self.assertEqual(data["gainers"][0]["change_pct"], Decimal("5"))

    def test_invalid_period_is_400(self):
        self.assertEqual(self.client.get("/api/market/movers/", {"period": "2Y"}).status_code, 400)


class SpiderSourceChangeTests(SimpleTestCase):

    def setUp(self):
        from crawlers.crawlers.spiders.trading_data import TradingDataSpider
        self.spider = TradingDataSpider()

    def row(self, **extra):
        return {"published_date": "2026-09-30", "open": "566", "high": "566", "low": "528",
                "close": "530.70", "traded_quantity": "96,214", "traded_amount": "51,000,000", **extra}

    def test_per_change_is_parsed(self):
        self.assertEqual(self.spider.extract_row(self.row(per_change="-1.55"), "NABIL")["source_change_pct"], Decimal("-1.55"))

    def test_missing_per_change_never_rejects_the_row(self):
        parsed = self.spider.extract_row(self.row(), "NABIL")
        self.assertIsNotNone(parsed)
        self.assertIsNone(parsed["source_change_pct"])
        self.assertEqual(parsed["close"], Decimal("530.70"))


class PipelineSourceChangeTests(TestCase):

    def setUp(self):
        from crawlers.crawlers.pipelines import TradingDataPipeline
        self.company = Company.objects.create(symbol="NABIL", name="Nabil Bank", sector="Banking")
        self.pipeline = TradingDataPipeline()
        self.pipeline.file = io.StringIO()
        self.pipeline.first_item = True
        self.spider = SimpleNamespace(logger=logging.getLogger("test"), prices_found=0, prices_created=0, prices_updated=0)

    def save(self, **extra):
        item = {"item_type": "daily_price", "company": "NABIL", "date": "2026-09-30", "open": "566", "high": "566",
                "low": "528", "close": "530.70", "volume": "96214", "turnover": "51000000", **extra}
        self.pipeline._process_sync(item, self.spider)
        return DailyPrice.objects.get(company=self.company, date=date(2026, 9, 30))

    def test_source_change_pct_stored_without_changing_other_fields(self):
        row = self.save(source_change_pct="-1.55")
        self.assertEqual(row.source_change_pct, Decimal("-1.55"))
        self.assertEqual(row.close, Decimal("530.70"))
        self.assertEqual(row.volume, 96214)
        self.assertEqual(row.source, "crawled")

    def test_later_crawl_without_value_keeps_it(self):
        self.save(source_change_pct="-1.55")
        self.assertEqual(self.save().source_change_pct, Decimal("-1.55"))

    def test_unparseable_value_is_null_and_row_still_saved(self):
        row = self.save(source_change_pct="n/a%")
        self.assertIsNone(row.source_change_pct)
        self.assertEqual(row.close, Decimal("530.70"))
