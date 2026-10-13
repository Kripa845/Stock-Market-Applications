"""Tests for services.top_movers and GET /api/market/top-gainers/ (tracked companies only)."""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest import mock

from rest_framework.test import APIClient

from apps.market_data.services import top_movers
from apps.market_data.services.live_prices import NPT
from apps.market_data.test_movers import MONDAY, TUESDAY, MoversFixture, trading_days
from apps.users.models import User

WEDNESDAY = TUESDAY + timedelta(days=1)


def at(day, hour=12, minute=0):
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=NPT)


class TopMoversFixture(MoversFixture):

    def setUp(self):
        super().setUp()
        closed = mock.patch("apps.market_data.services.top_movers.is_market_open", return_value=False)
        closed.start()
        self.addCleanup(closed.stop)

    def live(self, symbol, ltp, previous_close, when):
        company = self.company(symbol)
        company.ltp = Decimal(str(ltp))
        company.previous_close = None if previous_close is None else Decimal(str(previous_close))
        company.prices_updated_at = when
        company.save(update_fields=["ltp", "previous_close", "prices_updated_at"])

    @staticmethod
    def symbols(result):
        return [row["symbol"] for row in result["rows"]]


class OfficialPeriodTests(TopMoversFixture):
    """Every period from crawled closes (no live session newer than the crawl)."""

    def setUp(self):
        super().setUp()
        self.add("GAIN", MONDAY, 100); self.add("GAIN", TUESDAY, 105)
        self.add("BIG", MONDAY, 100); self.add("BIG", TUESDAY, 109)
        self.add("LOSE", MONDAY, 200); self.add("LOSE", TUESDAY, 190)
        self.add("ZERO", MONDAY, 0); self.add("ZERO", TUESDAY, 10)          # previous close 0
        self.add("NEW", TUESDAY, 50)                                          # new listing: no earlier session
        self.add("IDLE", MONDAY, 100); self.add("IDLE", TUESDAY, 120, volume=0)  # no trades

    def test_today_ranks_gainers_and_skips_unrankable(self):
        result = top_movers.top_movers("gainers", "today")
        self.assertFalse(result["live"])
        self.assertEqual(result["as_of"], TUESDAY)
        self.assertEqual(self.symbols(result), ["BIG", "GAIN"])
        self.assertEqual(result["total"], 2)
        big = result["rows"][0]
        self.assertEqual((big["ltp"], big["change"], big["change_pct"]), (Decimal("109.00"), Decimal("9.00"), Decimal("9.00")))
        self.assertIsNone(big["last_updated"])          # no floorsheet crawled in the fixture

    def test_losers(self):
        result = top_movers.top_movers("losers", "today")
        self.assertEqual(self.symbols(result), ["LOSE"])
        self.assertEqual(result["rows"][0]["change_pct"], Decimal("-5.00"))

    def test_paging_and_sector_filter(self):
        first = top_movers.top_movers("gainers", "today", page=1, page_size=1)
        second = top_movers.top_movers("gainers", "today", page=2, page_size=1)
        self.assertEqual((self.symbols(first), self.symbols(second)), (["BIG"], ["GAIN"]))
        self.assertEqual((first["total"], first["pages"]), (2, 2))
        self.assertEqual(top_movers.top_movers("gainers", "today", sector="Hydro")["total"], 0)
        self.assertEqual(top_movers.top_movers("gainers", "today", sector="Banking")["total"], 2)

    def test_too_short_history_returns_reason_not_error(self):
        result = top_movers.top_movers("gainers", "1y")
        self.assertEqual((result["total"], result["rows"]), (0, []))
        self.assertIn("Not enough crawled sessions", result["reason"])


class AdjustedModeTests(TopMoversFixture):
    """A bonus-share book closure: the close halves, the exchange-adjusted change is +2%."""

    def setUp(self):
        super().setUp()
        self.add("BONUS", MONDAY, 200); self.add("BONUS", TUESDAY, 102, source_pct=2)

    def test_adjusted_uses_source_pct(self):
        row = top_movers.top_movers("gainers", "today", adjusted=True)["rows"][0]
        self.assertEqual(row["change_pct"], Decimal("2.00"))
        self.assertTrue(row["adjusted"])
        self.assertEqual(top_movers.top_movers("losers", "today", adjusted=True)["total"], 0)

    def test_unadjusted_never_ranks_the_book_closure_drop(self):
        # close-to-close is -49%: beyond the daily circuit, so excluded rather than a top loser
        self.assertEqual(top_movers.top_movers("losers", "today", adjusted=False)["total"], 0)
        self.assertEqual(top_movers.top_movers("gainers", "today", adjusted=False)["total"], 0)

    def test_multi_session_compounds_source_pct(self):
        days = trading_days(TUESDAY - timedelta(days=7), 6)       # six sessions ending on TUESDAY
        self.assertEqual(days[-1], TUESDAY)
        for i, day in enumerate(days):
            self.add("STEP", day, 100 + i, source_pct=1 if i else None)
        result = top_movers.top_movers("gainers", "5d", adjusted=True)
        row = next(r for r in result["rows"] if r["symbol"] == "STEP")
        self.assertEqual(row["change_pct"], Decimal("5.10"))   # 1.01 ** 5 - 1
        self.assertEqual(top_movers.top_movers("gainers", "1w")["rows"], result["rows"])


class LiveTodayTests(TopMoversFixture):
    """Wednesday's live session is newer than the last crawled close (Tuesday)."""

    def setUp(self):
        super().setUp()
        self.add("UP", MONDAY, 90); self.add("UP", TUESDAY, 100)
        self.add("DOWN", MONDAY, 90); self.add("DOWN", TUESDAY, 100)
        self.add("BONUS", MONDAY, 190); self.add("BONUS", TUESDAY, 200)
        self.add("STALE", MONDAY, 90); self.add("STALE", TUESDAY, 100)
        self.add("NEW", TUESDAY, 100)
        self.live("UP", 104, 100, at(WEDNESDAY, 12, 30))
        self.live("DOWN", 97, 100, at(WEDNESDAY, 12, 45))
        self.live("BONUS", 102, 100, at(WEDNESDAY, 13))         # exchange-adjusted previous close
        self.live("STALE", 150, 100, at(TUESDAY, 14, 59))       # did not trade on Wednesday
        self.live("NEW", 110, 0, at(WEDNESDAY, 11, 5))          # previous close 0

    def test_live_today_uses_ltp_and_nepse_previous_close(self):
        result = top_movers.top_movers("gainers", "today")
        self.assertTrue(result["live"])
        self.assertEqual((result["as_of"], result["base_date"]), (WEDNESDAY, TUESDAY))
        self.assertEqual(self.symbols(result), ["UP", "BONUS"])
        up = result["rows"][0]
        self.assertEqual((up["ltp"], up["change"], up["change_pct"]), (Decimal("104"), Decimal("4.00"), Decimal("4.00")))
        self.assertEqual(up["last_updated"], "2026-09-30T12:30:00+05:45")
        self.assertFalse(up["adjusted"])
        self.assertTrue(result["rows"][1]["adjusted"])

    def test_live_unadjusted_compares_with_crawled_close(self):
        # BONUS is -49% against the crawled close 200: beyond the daily circuit, so left out.
        result = top_movers.top_movers("losers", "today", adjusted=False)
        self.assertEqual(self.symbols(result), ["DOWN"])
        self.assertEqual(result["rows"][0]["change_pct"], Decimal("-3.00"))
        # NEW has no NEPSE previous close (0) but a crawled close, so it ranks only when unadjusted.
        self.assertEqual(self.symbols(top_movers.top_movers("gainers", "today", adjusted=False)), ["NEW", "UP"])

    def test_other_periods_stay_official(self):
        result = top_movers.top_movers("gainers", "2d")
        self.assertFalse(result["live"])
        self.assertEqual(result["as_of"], TUESDAY)

    def test_after_the_crawl_today_is_official(self):
        for symbol, close in (("UP", 104), ("DOWN", 97), ("BONUS", 102), ("NEW", 110)):
            self.add(symbol, WEDNESDAY, close)
        result = top_movers.top_movers("gainers", "today")
        self.assertFalse(result["live"])
        self.assertEqual(result["as_of"], WEDNESDAY)


class TopMoversAPITests(TopMoversFixture):

    def setUp(self):
        super().setUp()
        self.add("GAIN", MONDAY, 100); self.add("GAIN", TUESDAY, 105)
        user = User.objects.create_user(username="top-admin", email="top@example.test",
                                        password="unused-test-password", role=User.Role.ADMIN)
        self.client = APIClient()
        self.client.force_authenticate(user)

    def test_response_shape(self):
        data = self.client.get("/api/market/top-gainers/", {"type": "gainers", "period": "today"}).data
        self.assertEqual(data["scope"], "tracked_companies")
        self.assertEqual(data["rows"][0]["symbol"], "GAIN")
        self.assertEqual(set(data["rows"][0]), set(top_movers.ROW_KEYS))
        for key in ("total", "page", "page_size", "pages", "sectors", "live", "market_open", "as_of"):
            self.assertIn(key, data)

    def test_invalid_params_are_400(self):
        for params in ({"type": "best"}, {"period": "2y"}, {"adjusted": "maybe"}, {"page": "0"}, {"page_size": "7"}):
            self.assertEqual(self.client.get("/api/market/top-gainers/", params).status_code, 400, params)

    def test_requires_login(self):
        self.assertEqual(APIClient().get("/api/market/top-gainers/").status_code, 401)

    def test_activity_endpoint_shape_and_validation(self):
        data = self.client.get("/api/market/top-activity/", {"metric": "volume", "period": "today"}).data
        self.assertEqual(data["scope"], "tracked_companies")
        self.assertEqual(set(data["rows"][0]), set(top_movers.ACTIVITY_ROW_KEYS))
        for params in ({"metric": "price"}, {"period": "2y"}, {"page_size": "7"}):
            self.assertEqual(self.client.get("/api/market/top-activity/", params).status_code, 400, params)


class TopActivityTests(TopMoversFixture):

    def setUp(self):
        super().setUp()
        self.add("BIG", MONDAY, 100, volume=500, turnover=50_000)
        self.add("BIG", TUESDAY, 110, volume=1_000, turnover=110_000)
        self.add("SMALL", MONDAY, 100, volume=100, turnover=10_000)
        self.add("SMALL", TUESDAY, 99, volume=900, turnover=89_100)
        self.add("IDLE", MONDAY, 50, volume=0, turnover=0)
        self.add("IDLE", TUESDAY, 50, volume=0, turnover=0)                 # never traded: not listed
        self.add("NEW", TUESDAY, 20, volume=50, turnover=1_000)            # new listing: no % change

    def test_today_ranks_by_the_latest_session(self):
        result = top_movers.top_activity("turnover", "today")
        self.assertEqual(self.symbols(result), ["BIG", "SMALL", "NEW"])
        big = result["rows"][0]
        self.assertEqual((big["value"], big["sessions_traded"], big["ltp"]), (Decimal("110000"), 1, Decimal("110")))
        self.assertEqual(big["change_pct"], Decimal("10.00"))
        self.assertIsNone(result["rows"][2]["change_pct"])

    def test_period_sums_every_session(self):
        result = top_movers.top_activity("volume", "2d")
        self.assertEqual(self.symbols(result), ["BIG", "SMALL", "NEW"])
        self.assertEqual([r["value"] for r in result["rows"]], [1_500, 1_000, 50])
        self.assertEqual(result["rows"][0]["sessions_traded"], 2)

    def test_missing_trade_counts_mark_the_total_incomplete(self):
        for price in self.companies["BIG"].dailyprice_set.all():
            price.transactions = 7 if price.date == TUESDAY else None
            price.save(update_fields=["transactions"])
        row = next(r for r in top_movers.top_activity("transactions", "2d")["rows"] if r["symbol"] == "BIG")
        self.assertEqual(row["value"], 7)
        self.assertFalse(row["complete"])
        today = top_movers.top_activity("transactions", "today")["rows"]
        self.assertEqual(self.symbols({"rows": today}), ["BIG"])          # NULL counts are not ranked
        self.assertTrue(today[0]["complete"])

    def test_sector_filter_and_paging(self):
        page2 = top_movers.top_activity("turnover", "today", page=2, page_size=1)
        self.assertEqual((self.symbols(page2), page2["total"], page2["pages"]), (["SMALL"], 3, 3))
        self.assertEqual(top_movers.top_activity("turnover", "today", sector="Hydro")["total"], 0)
