from datetime import date
from decimal import Decimal

import nepali_datetime
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.companies.models import Company, TrackedCompany
from apps.market_calendar.services import calendar
from apps.market_data.models import TradingHoliday
from apps.market_indices.models import IndexDaily, MarketIndex
from apps.reports.models import DividendAnnouncement
from apps.users.models import UserCompanyAccess

D = Decimal
TODAY = date(2026, 10, 28)          # BS 2083-07-11 (Kartik), a Wednesday


def _by_date(view):
    return {day["date"]: day for day in view["days"]}


class MonthBoundsTests(TestCase):
    def setUp(self):
        MarketIndex.objects.create(code="NEPSE", name="NEPSE Index", kind="main")

    def test_defaults_to_todays_bs_month(self):
        view = calendar.month_view(today=TODAY)
        self.assertEqual((view["bs_year"], view["bs_month"]), (2083, 7))
        self.assertEqual((view["month_name"], view["month_name_np"], view["bs_year_np"]), ("Kartik", "कार्तिक", "२०८३"))
        self.assertEqual((view["ad_start"], view["ad_end"]), (date(2026, 10, 18), date(2026, 11, 16)))
        self.assertEqual(len(view["days"]), 30)
        self.assertEqual(view["leading_blanks"], 0)            # 2026-10-18 is a Sunday
        self.assertEqual(view["days"][10]["bs_day_np"], "११")
        self.assertTrue(_by_date(view)[TODAY]["is_today"])

    def test_month_length_comes_from_the_library(self):
        view = calendar.month_view(2083, 3, today=TODAY)       # Asar 2083 has 32 days
        self.assertEqual(len(view["days"]), 32)
        self.assertEqual(view["days"][-1]["bs_day_np"], "३२")
        self.assertEqual(view["leading_blanks"], view["days"][0]["weekday"])
        self.assertEqual(view["days"][0]["weekday"], (view["ad_start"].weekday() + 1) % 7)

    def test_prev_next_roll_over_the_bs_year(self):
        chaitra = calendar.month_view(2082, 12, today=TODAY)
        self.assertEqual(chaitra["next"], {"bs_year": 2083, "bs_month": 1})
        baishakh = calendar.month_view(2083, 1, today=TODAY)
        self.assertEqual(baishakh["prev"], {"bs_year": 2082, "bs_month": 12})
        self.assertEqual((baishakh["ad_start"] - chaitra["ad_end"]).days, 1)

    def test_last_supported_month_has_no_next(self):
        view = calendar.month_view(2100, 12, today=TODAY)
        self.assertIsNone(view["next"])
        self.assertIsNotNone(view["prev"])

    def test_invalid_months_are_rejected(self):
        for args in ((2083, 13), (2083, 0), (1900, 1), ("abc", 1), (2083, None), (None, 7)):
            with self.subTest(args=args), self.assertRaises(calendar.CalendarError):
                calendar.month_view(*args, today=TODAY)

    def test_missing_index_raises(self):
        MarketIndex.objects.all().delete()
        with self.assertRaises(calendar.IndexNotFound):
            calendar.month_view(today=TODAY)


class DayStatusTests(TestCase):
    def setUp(self):
        self.nepse = MarketIndex.objects.create(code="NEPSE", name="NEPSE Index", kind="main")
        for day, close, pct in [
            (date(2026, 10, 15), "2625.93", "0.17"),   # before Kartik: seeds the first change
            (date(2026, 10, 26), "2629.82", "-0.16"),
            (date(2026, 10, 27), "2630.76", "0.03"),
        ]:
            IndexDaily.objects.create(index=self.nepse, date=day, close=D(close), source_change_pct=D(pct))
        TradingHoliday.objects.create(date=date(2026, 10, 20), name="Laxmi Puja")
        TradingHoliday.objects.create(date=date(2026, 10, 27), name="Partial closure")
        TradingHoliday.objects.create(date=date(2026, 11, 2), name="Future holiday")
        self.days = _by_date(calendar.month_view(today=TODAY))

    def test_statuses(self):
        expected = {
            date(2026, 10, 18): calendar.WEEKEND,      # Sunday, Mon-Fri week
            date(2026, 10, 19): calendar.NO_SESSION,   # trading weekday, no row, no holiday entered
            date(2026, 10, 20): calendar.HOLIDAY,
            date(2026, 10, 24): calendar.WEEKEND,      # Saturday
            date(2026, 10, 26): calendar.TRADED,
            date(2026, 10, 28): calendar.PENDING,      # today, close not stored yet
            date(2026, 10, 29): calendar.FUTURE,
        }
        self.assertEqual({day: self.days[day]["status"] for day in expected}, expected)

    def test_change_uses_previous_stored_close_across_the_month_boundary(self):
        index = self.days[date(2026, 10, 26)]["index"]
        self.assertEqual(index["change"], "3.89")              # vs 2026-10-15, before the month
        self.assertEqual(index["previous_date"], date(2026, 10, 15))
        self.assertEqual(index["change_pct"], "-0.1600")       # NEPSE's own %
        self.assertEqual(set(index), set(calendar.MONTH_INDEX_FIELDS))

    def test_a_stored_session_beats_a_holiday_entry_but_keeps_the_name(self):
        day = self.days[date(2026, 10, 27)]
        self.assertEqual(day["status"], calendar.TRADED)
        self.assertEqual(day["holiday"], "Partial closure")

    def test_future_days_have_no_index_but_keep_holiday_names(self):
        day = self.days[date(2026, 11, 2)]
        self.assertEqual(day["status"], calendar.FUTURE)
        self.assertIsNone(day["index"])
        self.assertEqual(day["holiday"], "Future holiday")
        self.assertTrue(all(d["index"] is None for d in self.days.values() if d["date"] > TODAY))

    def test_days_before_stored_history_are_no_data(self):
        view = calendar.month_view(2083, 6, today=TODAY)       # Ashwin 2083 ends 2026-10-17
        days = _by_date(view)
        self.assertEqual(view["index_history_from"], date(2026, 10, 15))
        self.assertEqual(days[date(2026, 10, 14)]["status"], calendar.NO_DATA)
        self.assertEqual(days[date(2026, 10, 15)]["status"], calendar.TRADED)
        self.assertIsNone(days[date(2026, 10, 15)]["index"]["change"])   # first stored session


class TradingWeekSwitchTests(TestCase):
    """NEPSE traded Sun-Thu until 2026-04-05 and Mon-Fri from 2026-04-06."""

    def test_weekend_follows_the_week_in_force_on_each_date(self):
        nepse = MarketIndex.objects.create(code="NEPSE", name="NEPSE Index", kind="main")
        IndexDaily.objects.create(index=nepse, date=date(2026, 3, 1), close=D("2700"))
        bs = nepali_datetime.date.from_datetime_date(date(2026, 4, 5))
        days = {}
        for year, month in ((bs.year, bs.month), (bs.year + (bs.month == 12), bs.month % 12 + 1)):
            days.update(_by_date(calendar.month_view(year, month, today=date(2026, 4, 30))))
        expected = {
            date(2026, 4, 3): calendar.WEEKEND,       # Friday, old week
            date(2026, 4, 5): calendar.NO_SESSION,    # Sunday, old week: a session was due
            date(2026, 4, 10): calendar.NO_SESSION,   # Friday, new week
            date(2026, 4, 12): calendar.WEEKEND,      # Sunday, new week
        }
        self.assertEqual({day: days[day]["status"] for day in expected}, expected)


def _user(name, role):
    return get_user_model().objects.create_user(
        username=name, email=f"{name}@example.com", password="pw", role=role,
    )


class DividendEventTests(TestCase):
    def setUp(self):
        MarketIndex.objects.create(code="NEPSE", name="NEPSE Index", kind="main")
        self.nabil, self.adbl, untracked = (
            Company.objects.create(symbol=symbol, name=f"{symbol} Ltd", sector="Banking")
            for symbol in ("NABIL", "ADBL", "OTHER")
        )
        TrackedCompany.objects.create(company=self.nabil, is_tracked=True)
        TrackedCompany.objects.create(company=self.adbl, is_tracked=True)
        TrackedCompany.objects.create(company=untracked, is_tracked=False)
        DividendAnnouncement.objects.create(
            symbol="NABIL", company=self.nabil, fiscal_year="2082/2083", bonus_pct=D("10"), cash_pct=D("5.26"),
            announcement_date=date(2026, 10, 19), book_closure_date=date(2026, 11, 3),
            bonus_listing_date=date(2026, 12, 20),      # next BS month: not in Kartik
        )
        DividendAnnouncement.objects.create(
            symbol="ADBL", company=self.adbl, fiscal_year="2082/2083", book_closure_date=date(2026, 11, 3),
        )
        DividendAnnouncement.objects.create(
            symbol="OTHER", company=untracked, fiscal_year="2082/2083", book_closure_date=date(2026, 11, 3),
        )
        DividendAnnouncement.objects.create(      # whole-market row with no Company link
            symbol="NOTOURS", fiscal_year="2082/2083", book_closure_date=date(2026, 11, 3),
        )
        self.admin = _user("cal-admin", "admin")

    def _events(self, user):
        days = _by_date(calendar.month_view(user=user, today=TODAY))
        return {day: [event["label"] for event in d["events"]] for day, d in days.items() if d["events"]}

    def test_tracked_companies_only_on_their_dates(self):
        self.assertEqual(self._events(self.admin), {
            date(2026, 10, 19): ["Div NABIL"],
            date(2026, 11, 3): ["BC ADBL", "BC NABIL"],     # future day keeps its events
        })

    def test_month_events_carry_only_the_cell_fields(self):
        day = _by_date(calendar.month_view(user=self.admin, today=TODAY))[date(2026, 10, 19)]
        self.assertEqual(day["events"], [{"type": "dividend_announced", "symbol": "NABIL", "label": "Div NABIL"}])

    def test_full_event_detail(self):
        events = calendar.dividend_events(date(2026, 11, 3), date(2026, 12, 31), self.admin)
        self.assertEqual([e["type"] for e in events[date(2026, 12, 20)]], ["bonus_listed"])
        nabil = next(e for e in events[date(2026, 11, 3)] if e["symbol"] == "NABIL")
        self.assertEqual(
            {k: nabil[k] for k in ("company_name", "fiscal_year", "bonus_pct", "cash_pct", "status")},
            {"company_name": "NABIL Ltd", "fiscal_year": "2082/2083", "bonus_pct": "10.0000",
             "cash_pct": "5.2600", "status": "proposed"},
        )

    def test_events_of_one_day_are_ordered_by_type_then_symbol(self):
        DividendAnnouncement.objects.create(
            symbol="ADBL", company=self.adbl, fiscal_year="2081/2082", announcement_date=date(2026, 11, 3),
        )
        self.assertEqual(self._events(self.admin)[date(2026, 11, 3)], ["BC ADBL", "BC NABIL", "Div ADBL"])

    def test_company_access_narrows_events(self):
        viewer = _user("cal-viewer", "viewer")
        UserCompanyAccess.objects.create(user=viewer, company=self.adbl, status=1)
        self.assertEqual(self._events(viewer), {date(2026, 11, 3): ["BC ADBL"]})

    def test_no_user_no_events(self):
        self.assertEqual(self._events(None), {})


class IssueEventTests(TestCase):
    def setUp(self):
        from apps.reports.models import IpoIssue

        MarketIndex.objects.create(code="NEPSE", name="NEPSE Index", kind="main")
        IpoIssue.objects.create(
            issue_type="ipo_migrant", symbol="HPHL", company_name="Him Parbat Hydropower Limited", units=422500,
            price=D("100"), open_date=date(2026, 10, 28), close_date=date(2026, 11, 2), final_date=date(2026, 11, 11),
            source_id="ipo_migrant-1171-422500",
        )
        IpoIssue.objects.create(      # announced, no dates yet
            issue_type="ipo", symbol="HPHL", company_name="Him Parbat Hydropower Limited", units=5915000,
            source_id="ipo-1171-5915000",
        )
        tracked = Company.objects.create(symbol="NABIL", name="NABIL Ltd", sector="Banking")
        TrackedCompany.objects.create(company=tracked, is_tracked=True)
        DividendAnnouncement.objects.create(symbol="NABIL", company=tracked, fiscal_year="2082/2083",
                                            book_closure_date=date(2026, 11, 2))
        self.restricted = _user("cal-issue-viewer", "viewer")      # no company access at all

    def test_open_and_close_are_market_wide_and_ignore_company_access(self):
        days = _by_date(calendar.month_view(user=self.restricted, today=TODAY))
        self.assertEqual(days[date(2026, 10, 28)]["events"],
                         [{"type": "ipo_open", "symbol": "HPHL", "label": "IPO-Migrant open HPHL"}])
        # The final (extended) date is detail only; the restricted user sees no dividend events.
        self.assertEqual([e["label"] for e in days[date(2026, 11, 2)]["events"]], ["IPO-Migrant close HPHL"])
        self.assertEqual(days[date(2026, 11, 11)]["events"], [])
        self.assertEqual(calendar.month_view(today=TODAY)["data_notes"], [])

    def test_book_closure_sorts_before_issue_events(self):
        admin = _user("cal-issue-admin", "admin")
        labels = [e["label"] for e in _by_date(calendar.month_view(user=admin, today=TODAY))[date(2026, 11, 2)]["events"]]
        self.assertEqual(labels, ["BC NABIL", "IPO-Migrant close HPHL"])

    def test_day_view_issue_detail(self):
        event = calendar.day_view(date(2026, 10, 28), user=self.restricted, today=TODAY)["events"][0]
        self.assertEqual(
            {k: event[k] for k in ("category", "issue_type", "issue_type_label", "units", "price", "final_date", "logo_url")},
            {"category": "issue", "issue_type": "ipo_migrant", "issue_type_label": "IPO (migrant workers)",
             "units": 422500, "price": "100.00", "final_date": date(2026, 11, 11), "logo_url": None},
        )

    def test_note_until_issues_are_crawled(self):
        from apps.reports.models import IpoIssue

        IpoIssue.objects.all().delete()
        self.assertEqual(calendar.month_view(today=TODAY)["data_notes"], ["ipo_not_crawled"])
