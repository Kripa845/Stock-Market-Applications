"""Tests for services.market_overview and the /api/market/overview/ endpoints."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from django.test import SimpleTestCase
from rest_framework.test import APIClient

from apps.market_data.services import market_overview, movers
from apps.floorsheet.services.intraday_candles import NPT
from apps.market_data.tests.test_movers import MONDAY, TUESDAY, MoversFixture
from apps.market_indices.models import IndexDaily, IndexIntradayPoint, MarketIndex
from apps.users.models import User


def row(bucket, change_pct=None, volume=100, turnover=1000, transactions=5):
    return {"bucket": bucket, "change_pct": change_pct, "volume": volume, "turnover": turnover,
            "transactions": transactions}


class NepaliGroupingTests(SimpleTestCase):

    def test_groups_last_three_then_pairs(self):
        self.assertEqual(market_overview.nepali_grouping(Decimal("4465246360.73")), "4,46,52,46,360.73")
        self.assertEqual(market_overview.nepali_grouping(12719734, decimals=0), "1,27,19,734")
        self.assertEqual(market_overview.nepali_grouping(100000), "1,00,000.00")
        self.assertEqual(market_overview.nepali_grouping(999), "999.00")
        self.assertEqual(market_overview.nepali_grouping(Decimal("-1234.5")), "-1,234.50")
        self.assertIsNone(market_overview.nepali_grouping(None))


class ComputeMarketStatsTests(SimpleTestCase):

    def test_counts_and_totals(self):
        threshold = movers.CIRCUIT_THRESHOLD_PCT
        stats = market_overview.compute_market_stats([
            row("gainer", threshold),                     # exactly at the circuit threshold
            row("gainer", Decimal("2.5")),
            row("loser", -threshold - 1),
            row("unchanged", Decimal("0")),
            # Traded, but no previous close: counted as traded, not ranked, no crash.
            row("missing_previous_session", None, transactions=None),
            row("possible_corporate_action", Decimal("-30")),
            row("not_traded", None, volume=0, turnover=0, transactions=None),
            row("missing_price", None, volume=None, turnover=None, transactions=None),
        ])
        self.assertEqual((stats["advanced"], stats["declined"], stats["unchanged"]), (2, 1, 1))
        self.assertEqual((stats["positive_circuit"], stats["negative_circuit"]), (1, 1))
        self.assertEqual(stats["not_ranked"], 2)                 # no previous close + corporate action
        self.assertEqual(stats["total_scrips_traded"], 6)
        self.assertEqual(stats["total_turnover"], 6000)
        self.assertEqual(stats["total_turnover_display"], "6,000.00")
        self.assertEqual(stats["total_traded_shares"], 600)
        self.assertEqual((stats["total_transactions"], stats["transactions_reported"]), (25, 5))
        self.assertEqual(stats["tracked_count"], 8)

    def test_corporate_action_is_never_a_circuit(self):
        stats = market_overview.compute_market_stats([row("possible_corporate_action", Decimal("-25"))])
        self.assertEqual((stats["negative_circuit"], stats["declined"]), (0, 0))

    def test_nothing_traded(self):
        stats = market_overview.compute_market_stats([row("not_traded", volume=0, turnover=0, transactions=None)])
        self.assertEqual(stats["total_scrips_traded"], 0)
        self.assertIsNone(stats["total_turnover"])
        self.assertIsNone(stats["total_turnover_display"])
        self.assertIsNone(stats["total_transactions"])

    def test_empty(self):
        stats = market_overview.compute_market_stats([])
        self.assertEqual(stats["advanced"], 0)
        self.assertIsNone(stats["total_traded_shares"])


class OverviewFixture(MoversFixture):

    def setUp(self):
        super().setUp()
        self.add("GAIN", MONDAY, 100); self.add("GAIN", TUESDAY, 110)               # +10% -> circuit
        self.add("LOSE", MONDAY, 200); self.add("LOSE", TUESDAY, 190)
        self.add("FLAT", MONDAY, 50); self.add("FLAT", TUESDAY, 50)
        self.add("NEW", TUESDAY, 40)                                               # no previous close
        self.add("IDLE", MONDAY, 70); self.add("IDLE", TUESDAY, 70, volume=0, turnover=0)
        self.nepse = MarketIndex.objects.create(code="NEPSE", name="NEPSE Index", kind="main")
        for day, close, pct in ((MONDAY - timedelta(days=40), 2500, None), (MONDAY, 2580, None), (TUESDAY, 2600, "0.78")):
            IndexDaily.objects.create(index=self.nepse, date=day, open=close, high=close + 10, low=close - 10,
                                      close=close, source_change_pct=pct)


class MarketOverviewTests(OverviewFixture):

    def test_stats_agree_with_tracked_summary(self):
        overview = market_overview.market_overview()
        summary = movers.tracked_summary()
        stats = overview["stats"]
        for key in ("advanced", "declined", "unchanged", "positive_circuit", "negative_circuit",
                    "total_turnover", "total_traded_shares"):
            self.assertEqual(stats[key], summary[key], key)
        self.assertEqual(stats["total_scrips_traded"], 4)          # IDLE did not trade
        self.assertEqual(overview["trade_date"], TUESDAY)
        self.assertEqual(overview["stats_label"], "Your Companies")

    def test_index_quote_from_stored_sessions(self):
        quote = market_overview.market_overview(now=datetime(2026, 10, 3, 12, tzinfo=NPT))["instrument"]
        self.assertEqual((quote["value"], quote["change"], quote["change_pct"]), (2600, 20, Decimal("0.78")))
        self.assertFalse(quote["live"])
        self.assertEqual(quote["as_of"], datetime(2026, 9, 29, 15, 0, tzinfo=NPT))

    def test_newer_live_snapshot_wins(self):
        at = datetime.combine(TUESDAY + timedelta(days=1), datetime.min.time(), tzinfo=NPT) + timedelta(hours=11)
        IndexIntradayPoint.objects.create(index=self.nepse, recorded_at=at, value=2610, change=10, change_pct="0.38")
        quote = market_overview.index_quote()
        self.assertTrue(quote["live"])
        self.assertEqual(quote["value"], 2610)

    def test_status_follows_trading_calendar(self):
        open_moment = datetime(2026, 10, 1, 12, 0, tzinfo=NPT)      # Thursday 12:00
        closed_moment = datetime(2026, 10, 3, 12, 0, tzinfo=NPT)    # Saturday
        self.assertEqual(market_overview.market_overview(now=open_moment)["status"], "OPEN")
        self.assertEqual(market_overview.market_overview(now=closed_moment)["status"], "CLOSE")

    def test_company_header(self):
        gain = self.company("GAIN")
        quote = market_overview.market_overview(company=gain)["instrument"]
        self.assertEqual((quote["symbol"], quote["value"]), ("GAIN", Decimal("110")))
        self.assertEqual(quote["change_pct"], Decimal("10"))


class ChartSeriesTests(OverviewFixture):

    def test_daily_ranges_only_when_history_reaches(self):
        result = market_overview.chart_series("1M")                 # 1M back from 29 Sep = 29 Aug
        self.assertEqual([p["close"] for p in result["points"]], [2580, 2600])
        self.assertEqual(len(market_overview.chart_series("ALL")["points"]), 3)
        self.assertIn("1M", result["available_ranges"])
        self.assertNotIn("1Y", result["available_ranges"])
        self.assertNotIn("1D", result["available_ranges"])          # no intraday snapshots
        self.assertIn("reason", market_overview.chart_series("1Y"))

    def test_intraday_index_points(self):
        start = datetime.combine(TUESDAY, datetime.min.time(), tzinfo=NPT) + timedelta(hours=11)
        for minutes, value in ((0, 2590), (2, 2595)):
            IndexIntradayPoint.objects.create(index=self.nepse, recorded_at=start + timedelta(minutes=minutes), value=value)
        result = market_overview.chart_series("1D")
        self.assertEqual(result["interval"], "intraday")
        self.assertEqual([p["close"] for p in result["points"]], [2590, 2595])
        self.assertIn("1D", result["available_ranges"])

    def test_session_is_the_nepal_day_not_the_utc_day(self):
        # Nepal midnight 14 Oct = 18:15 UTC on 13 Oct.  Ticks just either side of it,
        # and around UTC midnight, must land on the Nepal day they belong to.
        utc = timezone.utc
        ticks = [
            (datetime(2026, 10, 13, 18, 10, tzinfo=utc), 1),   # 13 Oct 23:55 NPT -> previous day
            (datetime(2026, 10, 13, 18, 15, tzinfo=utc), 2),   # 14 Oct 00:00 NPT -> included
            (datetime(2026, 10, 13, 23, 59, tzinfo=utc), 3),   # 14 Oct 05:44 NPT, before UTC midnight
            (datetime(2026, 10, 14, 0, 1, tzinfo=utc), 4),     # 14 Oct 05:46 NPT, after UTC midnight
            (datetime(2026, 10, 14, 5, 15, tzinfo=utc), 5),    # 14 Oct 11:00 NPT, session open
            (datetime(2026, 10, 14, 18, 14, tzinfo=utc), 6),   # 14 Oct 23:59 NPT -> included
            (datetime(2026, 10, 14, 18, 15, tzinfo=utc), 7),   # 15 Oct 00:00 NPT -> next day
        ]
        for at, value in reversed(ticks):                       # insertion order must not matter
            IndexIntradayPoint.objects.create(index=self.nepse, recorded_at=at, value=value)
        IndexIntradayPoint.objects.filter(value=7).delete()     # make 14 Oct the latest session
        result = market_overview.chart_series("1D", now=datetime(2026, 10, 14, 13, 0, tzinfo=NPT))
        self.assertEqual(result["session_date"], date(2026, 10, 14))
        self.assertEqual([p["close"] for p in result["points"]], [2, 3, 4, 5, 6])
        times = [p["t"] for p in result["points"]]
        self.assertEqual(times, sorted(times))
        self.assertTrue(result["is_live"])                      # Wednesday 13:00, trading

    def test_falls_back_to_latest_session_with_ticks(self):
        tuesday_11 = datetime.combine(TUESDAY, datetime.min.time(), tzinfo=NPT) + timedelta(hours=11)
        for minutes, value in ((0, 2590), (1, 2591)):
            IndexIntradayPoint.objects.create(
                index=self.nepse, recorded_at=tuesday_11 + timedelta(minutes=minutes), value=value)
        for label, now in (
            ("before the open", datetime.combine(TUESDAY + timedelta(days=1), datetime.min.time(), tzinfo=NPT)
                + timedelta(hours=10)),
            ("weekend", datetime(2026, 10, 3, 12, 0, tzinfo=NPT)),
            ("same day after the close", tuesday_11 + timedelta(hours=5)),
        ):
            with self.subTest(label):
                result = market_overview.chart_series("1D", now=now)
                self.assertEqual(result["session_date"], TUESDAY)
                self.assertEqual([p["close"] for p in result["points"]], [2590, 2591])
                self.assertFalse(result["is_live"])

    def test_lone_tick_session_is_skipped_for_the_last_full_session(self):
        tuesday_11 = datetime.combine(TUESDAY, datetime.min.time(), tzinfo=NPT) + timedelta(hours=11)
        for minutes, value in ((0, 2590), (1, 2591)):
            IndexIntradayPoint.objects.create(
                index=self.nepse, recorded_at=tuesday_11 + timedelta(minutes=minutes), value=value)
        wednesday_pre_open = tuesday_11 + timedelta(days=1, minutes=-10)
        IndexIntradayPoint.objects.create(index=self.nepse, recorded_at=wednesday_pre_open, value=2600)
        result = market_overview.chart_series("1D", now=wednesday_pre_open + timedelta(minutes=12))
        self.assertEqual(result["session_date"], TUESDAY)
        self.assertEqual([p["close"] for p in result["points"]], [2590, 2591])
        self.assertFalse(result["is_live"])

    def test_single_tick_only_gives_no_chart(self):
        IndexIntradayPoint.objects.create(
            index=self.nepse, recorded_at=datetime(2026, 10, 13, 10, 50, tzinfo=NPT), value=2597.93)
        result = market_overview.chart_series("1D")
        self.assertEqual(result["points"], [])
        self.assertNotIn("1D", result["available_ranges"])
        self.assertIn("reason", result)

    def test_no_ticks_at_all(self):
        result = market_overview.chart_series("1D")
        self.assertEqual((result["points"], result["session_date"], result["is_live"]), ([], None, False))
        self.assertIn("reason", result)

    def test_company_daily_series(self):
        result = market_overview.chart_series("ALL", self.company("GAIN"))
        self.assertEqual([p["close"] for p in result["points"]], [Decimal("100"), Decimal("110")])

    def test_months_before_clamps_to_month_end(self):
        self.assertEqual(market_overview._months_before(date(2026, 3, 31), 1), date(2026, 2, 28))


class OverviewApiTests(OverviewFixture):

    def setUp(self):
        super().setUp()
        user = User.objects.create_user(
            username="overview-admin", email="overview-admin@example.test",
            password="unused-test-password", role=User.Role.ADMIN,
        )
        self.client = APIClient()
        self.client.force_authenticate(user)

    def test_overview_payload(self):
        response = self.client.get("/api/market/overview/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["instrument"]["symbol"], "NEPSE")
        self.assertIn(data["status"], ("OPEN", "CLOSE"))
        self.assertEqual(data["stats"]["advanced"], 1)
        self.assertEqual(data["instruments"][0]["symbol"], "NEPSE")

    def test_chart_and_technical(self):
        self.assertEqual(self.client.get("/api/market/overview/chart/", {"range": "ALL"}).status_code, 200)
        self.assertEqual(self.client.get("/api/market/overview/chart/", {"range": "2D"}).status_code, 400)
        response = self.client.get("/api/market/overview/technical/", {"symbol": "GAIN"})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["summary"]["signal"])    # two sessions: not enough history

    def test_unknown_symbol_is_404(self):
        self.assertEqual(self.client.get("/api/market/overview/", {"symbol": "NOPE"}).status_code, 404)

    def test_requires_login(self):
        self.assertEqual(APIClient().get("/api/market/overview/").status_code, 401)
