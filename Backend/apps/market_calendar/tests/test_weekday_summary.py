"""Weekday summary of tracked companies: weekday averages, week moves, gaps, closed weeks, scopes and the API."""

from datetime import date, timedelta
from decimal import Decimal as D

from django.test import TestCase
from rest_framework.test import APIClient

from apps.companies.models import Company, TrackedCompany
from apps.market_calendar.services.weekday_summary import ScopeError, weekday_summary
from apps.market_data.models import DailyPrice, TradingHoliday
from apps.users.models import CustomRole, User, UserCompanyAccess

# Mondays (Mon-Fri trading week since 2026-04-06).
W1, W2, W3 = date(2026, 10, 5), date(2026, 10, 12), date(2026, 10, 26)   # 19-23 Oct: closed
TODAY = date(2026, 10, 29)                                                  # Thursday of W3


def tracked(symbol, sector="Commercial Bank"):
    company = Company.objects.create(symbol=symbol, name=symbol, sector=sector)
    TrackedCompany.objects.create(company=company, is_tracked=True)
    return company


def price(company, day, close, pct):
    DailyPrice.objects.create(
        company=company, source="crawled", date=day, open=close, high=close, low=close,
        close=D(close), volume=100, turnover=D(close) * 100,
        source_change_pct=None if pct is None else D(pct),
    )


def compound(*pcts):
    growth = D(1)
    for pct in pcts:
        growth *= 1 + D(pct) / 100
    return (growth - 1) * 100


class WeekdaySummaryTests(TestCase):
    """One tracked company, so each day's basket move is that company's move."""

    def setUp(self):
        self.company = tracked("NABIL")
        price(self.company, date(2026, 10, 2), "1000", "0")   # previous session for W1's Monday
        close = D("1000")
        # (week start, [(weekday offset, % change)])
        for start, days in [
            (W1, [(0, "1"), (1, "-1"), (2, "2"), (4, "0.5")]),   # Thursday: holiday
            (W2, [(0, "-0.5"), (1, "1"), (2, "-1"), (3, "1"), (4, "1")]),
            (W3, [(0, "1"), (1, "1"), (2, "-0.5")]),             # Thu = today, not crawled yet
        ]:
            for offset, pct in days:
                close = (close * (1 + D(pct) / 100)).quantize(D("0.01"))
                price(self.company, start + timedelta(days=offset), close, pct)
        TradingHoliday.objects.create(date=W1 + timedelta(days=3), name="Ghatasthapana")

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

    def test_weeks_newest_first_with_compounded_week_move(self):
        rows = weekday_summary(3, today=TODAY)["week_rows"]
        self.assertEqual([w["week_start"] for w in rows], [W3, W2, W1])
        self.assertTrue(rows[0]["partial"])
        self.assertEqual([d["status"] for d in rows[0]["days"]], ["up", "up", "down", "pending", "pending"])
        self.assertEqual(rows[2]["change_pct"], compound("1", "-1", "2", "0.5"))
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
        # Thursday: pending today, up in W2, holiday in W1 -> 1.  Tuesday (up W3, W2; down W1) and
        # Friday (pending skipped, up W2, W1) both run 2; a tie goes to the earlier weekday.
        self.assertEqual((streak["weekdays"], streak["sessions"]), (["Tue"], 2))

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
        price(self.company, date(2026, 4, 2), "900", "1")
        data = weekday_summary(26, today=TODAY)
        self.assertGreaterEqual(data["week_rows"][-1]["week_start"], date(2026, 4, 6))


class TrackedScopeTests(TestCase):
    """Equal-weighted baskets of several companies, from the movers session change."""

    def setUp(self):
        self.companies = {
            "NABIL": tracked("NABIL"), "SCB": tracked("SCB"), "UPPER": tracked("UPPER", "Hydropower"),
        }
        friday = W2 - timedelta(days=3)
        for company in self.companies.values():
            price(company, friday, "100", "0")
        price(self.companies["NABIL"], W2, "102", "2")
        price(self.companies["SCB"], W2, "99", "-1")
        price(self.companies["UPPER"], W2, "104", "4")
        # Tuesday: UPPER has no price (partial crawl) -> left out of that day's average.
        price(self.companies["NABIL"], W2 + timedelta(days=1), "103.02", "1")
        price(self.companies["SCB"], W2 + timedelta(days=1), "99.99", "1")

    def test_basket_is_the_plain_average_of_company_changes(self):
        data = weekday_summary(4, today=TODAY)
        monday, tuesday = data["week_rows"][0]["days"][:2]
        self.assertEqual((data["scope"], data["symbols"]), ("tracked", ["NABIL", "SCB", "UPPER"]))
        self.assertEqual(monday["change_pct"], (D("2") + D("-1") + D("4")) / 3)
        self.assertEqual((monday["companies"], monday["companies_up"], monday["excluded"]), (3, 2, 0))
        self.assertEqual((monday["best"]["symbol"], monday["worst"]["symbol"]), ("UPPER", "SCB"))
        self.assertEqual((tuesday["change_pct"], tuesday["companies"], tuesday["excluded"]), (D("1"), 2, 1))

    def test_week_change_compounds_the_daily_averages(self):
        week = weekday_summary(4, today=TODAY)["week_rows"][0]
        self.assertEqual(week["change_pct"], compound(D("5") / 3, "1"))

    def test_sector_scope(self):
        data = weekday_summary(4, today=TODAY, scope="tracked:Commercial Bank")
        self.assertEqual((data["scope_label"], data["symbols"]), ("Tracked Commercial Bank", ["NABIL", "SCB"]))
        self.assertEqual(data["week_rows"][0]["days"][0]["change_pct"], (D("2") + D("-1")) / 2)

    def test_company_access_narrows_the_basket(self):
        data = weekday_summary(4, today=TODAY, company_ids=[self.companies["UPPER"].pk])
        self.assertEqual(data["symbols"], ["UPPER"])

    def test_unknown_or_empty_scope(self):
        for scope in ("tracked:Microfinance", "index:NEPSE", "nope"):
            with self.assertRaises(ScopeError):
                weekday_summary(4, today=TODAY, scope=scope)


class WeekdaySummaryAPITests(TestCase):
    URL = "/api/market-calendar/weekdays/"

    def setUp(self):
        company = tracked("NABIL")
        price(company, W2 - timedelta(days=3), "100", "0")
        price(company, W2, "101", "1")
        role = CustomRole.objects.create(name="market", permissions=["view_market_data"])
        self.user = User.objects.create_user(username="m", email="m@example.com", password="Pw-12345!",
                                             role=User.Role.VIEWER, custom_role=role)
        UserCompanyAccess.objects.create(user=self.user, company=company, status=1)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_returns_numbers_and_tracked_scopes(self):
        body = self.client.get(self.URL).json()
        self.assertEqual(body["week_rows"][0]["days"][0]["change_pct"], 1.0)
        # The seed Friday (9 Oct) is a week of its own, with no change (no session before it).
        self.assertEqual(body["from"], W1.isoformat())
        self.assertEqual(set(body["scopes"]), {"tracked", "tracked_sectors"})

    def test_user_without_company_access_gets_400(self):
        UserCompanyAccess.objects.filter(user=self.user).delete()
        self.assertEqual(self.client.get(self.URL).status_code, 400)

    def test_rejects_unknown_week_count_and_index_scope(self):
        self.assertEqual(self.client.get(self.URL, {"weeks": 5}).status_code, 400)
        self.assertEqual(self.client.get(self.URL, {"scope": "index:NEPSE"}).status_code, 400)

    def test_requires_permission(self):
        self.user.custom_role.permissions = []
        self.user.custom_role.save()
        self.assertEqual(self.client.get(self.URL).status_code, 403)
