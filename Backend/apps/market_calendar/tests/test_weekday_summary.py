"""Weekday summary: weekday averages, week moves, gaps, closed weeks, the week-config boundary and the API."""

from datetime import date, timedelta
from decimal import Decimal as D

from django.test import TestCase
from rest_framework.test import APIClient

from apps.market_calendar.services.weekday_summary import weekday_summary
from apps.market_data.models import TradingHoliday
from apps.market_indices.models import IndexDaily, MarketIndex
from apps.users.models import CustomRole, User

# Mondays (Mon-Fri trading week since 2026-04-06).
W1, W2, W3 = date(2026, 10, 5), date(2026, 10, 12), date(2026, 10, 26)   # 19-23 Oct: closed
TODAY = date(2026, 10, 29)                                                  # Thursday of W3


class WeekdaySummaryTests(TestCase):

    def setUp(self):
        self.nepse = MarketIndex.objects.create(code="NEPSE", name="NEPSE Index", kind="main")
        self.row(date(2026, 10, 2), "1000", "0")   # previous week's last close
        close = D("1000")
        # (week start, [(weekday offset, % change)])
        for start, days in [
            (W1, [(0, "1"), (1, "-1"), (2, "2"), (4, "0.5")]),   # Thursday: no session
            (W2, [(0, "-0.5"), (1, "1"), (2, "-1"), (3, "1"), (4, "1")]),
            (W3, [(0, "1"), (1, "1"), (2, "-0.5")]),             # Thu = today, not stored yet
        ]:
            for offset, pct in days:
                close = (close * (1 + D(pct) / 100)).quantize(D("0.01"))
                self.row(start + timedelta(days=offset), close, pct)
        TradingHoliday.objects.create(date=W1 + timedelta(days=3), name="Ghatasthapana")

    def row(self, day, close, pct):
        IndexDaily.objects.create(index=self.nepse, date=day, close=D(close), source_change_pct=D(pct))

    def test_weekday_columns_average_and_count_sessions(self):
        data = weekday_summary(3, today=TODAY)
        self.assertEqual(data["trading_week"], ["Mon", "Tue", "Wed", "Thu", "Fri"])
        monday = data["columns"][0]
        self.assertEqual((monday["sessions"], monday["up"], monday["down"]), (3, 2, 1))
        self.assertEqual(monday["average_pct"], (D("1") + D("-0.5") + D("1")) / 3)
        self.assertEqual(monday["dots"], ["up", "down", "up"])           # oldest week first
        thursday = data["columns"][3]
        self.assertEqual(thursday["dots"], ["holiday", "up", "pending"])
        self.assertEqual((thursday["sessions"], thursday["up"]), (1, 1))

    def test_weeks_newest_first_with_week_move_from_closes(self):
        data = weekday_summary(3, today=TODAY)
        rows = data["week_rows"]
        self.assertEqual([w["week_start"] for w in rows], [W3, W2, W1])
        self.assertTrue(rows[0]["partial"])
        self.assertEqual([d["status"] for d in rows[0]["days"]], ["up", "up", "down", "pending", "pending"])
        w1_close = IndexDaily.objects.get(date=W1 + timedelta(days=4)).close
        self.assertEqual(rows[2]["change_pct"], (w1_close - D("1000")) * 100 / D("1000"))
        self.assertEqual(rows[0]["label"], "9 Kartik")

    def test_best_and_worst_ignore_the_partial_week(self):
        rows = {w["week_start"]: w for w in weekday_summary(3, today=TODAY)["week_rows"]}
        self.assertTrue(rows[W1]["best"])
        self.assertTrue(rows[W2]["worst"])
        self.assertFalse(rows[W3]["best"] or rows[W3]["worst"])

    def test_closed_week_is_skipped_and_noted(self):
        data = weekday_summary(3, today=TODAY)
        self.assertEqual(data["weeks"], 3)
        self.assertEqual([w["week_start"] for w in data["closed_weeks"]], [date(2026, 10, 19)])
        self.assertTrue(any("2 Kartik" in note for note in data["notes"]))

    def test_up_days_and_session_totals(self):
        data = weekday_summary(3, today=TODAY)
        self.assertEqual([(w["up_days"], w["sessions"]) for w in data["week_rows"]], [(2, 3), (3, 5), (3, 4)])
        self.assertEqual((data["sessions_up"], data["sessions_total"]), (8, 12))
        self.assertEqual(data["today"], TODAY)

    def test_streak_counts_back_from_the_newest_week_over_gaps(self):
        streak = next(i for i in weekday_summary(3, today=TODAY)["insights"] if i["kind"] == "streak")
        # Thursday: pending today, up in W2, holiday in W1 -> only 1; Friday: up in W2 and W1 (pending skipped).
        self.assertEqual((streak["weekdays"], streak["sessions"]), (["Fri"], 2))

    def test_window_counts_traded_weeks(self):
        data = weekday_summary(2, today=TODAY)
        self.assertEqual([w["week_start"] for w in data["week_rows"]], [W3, W2])

    def test_insights(self):
        insights = {i["kind"]: i for i in weekday_summary(3, today=TODAY)["insights"]}
        # Thursday's single +1% session is not enough for "best"; Friday averages +0.75%.
        self.assertEqual(insights["best"]["weekdays"], ["Fri"])
        # "Always up" needs at least two sessions: Friday, 2 of 2 (Thursday's single session doesn't count).
        self.assertEqual((insights["always_up"]["weekdays"], insights["always_up"]["sessions"]), (["Fri"], 2))
        self.assertNotIn("negative", insights)                           # every weekday averages above zero

    def test_window_stops_at_the_trading_week_change(self):
        IndexDaily.objects.create(index=self.nepse, date=date(2026, 4, 2), close=D("900"), source_change_pct=D("1"))
        data = weekday_summary(26, today=TODAY)
        self.assertGreaterEqual(data["week_rows"][-1]["week_start"], date(2026, 4, 6))


class WeekdaySummaryAPITests(TestCase):
    URL = "/api/market-calendar/weekdays/"

    def setUp(self):
        nepse = MarketIndex.objects.create(code="NEPSE", name="NEPSE Index", kind="main")
        IndexDaily.objects.create(index=nepse, date=W2, close=D("1000"), source_change_pct=D("1"))
        role = CustomRole.objects.create(name="market", permissions=["view_market_data"])
        self.user = User.objects.create_user(username="m", email="m@example.com", password="Pw-12345!",
                                             role=User.Role.VIEWER, custom_role=role)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_returns_numbers(self):
        body = self.client.get(self.URL).json()
        self.assertEqual(body["week_rows"][0]["days"][0]["change_pct"], 1.0)
        self.assertEqual(body["from"], W2.isoformat())

    def test_rejects_unknown_week_count(self):
        self.assertEqual(self.client.get(self.URL, {"weeks": 5}).status_code, 400)

    def test_requires_permission(self):
        self.user.custom_role.permissions = []
        self.user.custom_role.save()
        self.assertEqual(self.client.get(self.URL).status_code, 403)
