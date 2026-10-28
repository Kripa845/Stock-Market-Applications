from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.companies.models import Company, TrackedCompany
from apps.market_data.models import TradingHoliday
from apps.market_indices.models import IndexDaily, MarketIndex
from apps.reports.models import DividendAnnouncement
from apps.users.models import CustomRole, UserCompanyAccess

D = Decimal
TODAY = date(2026, 10, 28)          # BS 2083-07-11
MONTH_URL = "/api/market-calendar/month/"
DAY_URL = "/api/market-calendar/day/"


def _user(name, role="viewer", permissions=None):
    user = get_user_model().objects.create_user(
        username=name, email=f"{name}@example.com", password="pw", role=role,
    )
    if permissions is not None:
        user.custom_role = CustomRole.objects.create(name=f"{name} role", permissions=permissions)
        user.save(update_fields=["custom_role"])
    return user


@patch("apps.market_calendar.services.calendar.timezone.localdate", return_value=TODAY)
class CalendarApiTests(TestCase):
    def setUp(self):
        nepse = MarketIndex.objects.create(code="NEPSE", name="NEPSE Index", kind="main")
        IndexDaily.objects.create(index=nepse, date=date(2026, 10, 26), close=D("2629.82"), source_change_pct=D("-0.16"))
        IndexDaily.objects.create(
            index=nepse, date=date(2026, 10, 27), open=D("2629.00"), high=D("2640.10"), low=D("2620.00"),
            close=D("2630.76"), source_change_pct=D("0.03"), turnover=D("4500000000"), volume=9000000,
            transactions=60000,
        )
        TradingHoliday.objects.create(date=date(2026, 10, 20), name="Laxmi Puja")
        self.nabil, self.adbl = (Company.objects.create(symbol=s, name=f"{s} Ltd", sector="Banking") for s in ("NABIL", "ADBL"))
        for company in (self.nabil, self.adbl):
            TrackedCompany.objects.create(company=company, is_tracked=True)
            DividendAnnouncement.objects.create(
                symbol=company.symbol, company=company, fiscal_year="2082/2083", bonus_pct=D("10"),
                book_closure_date=date(2026, 10, 27),
            )
        self.client = APIClient()
        self.client.force_authenticate(_user("cal-api-admin", role="admin"))

    def test_month_defaults_to_todays_bs_month(self, _today):
        body = self.client.get(MONTH_URL).json()
        self.assertEqual((body["bs_year"], body["bs_month"], body["month_name_np"]), (2083, 7, "कार्तिक"))
        self.assertEqual((body["ad_start"], body["today"]), ("2026-10-18", "2026-10-28"))
        days = {day["date"]: day for day in body["days"]}
        self.assertEqual(len(days), 30)
        self.assertEqual(days["2026-10-20"]["holiday"], "Laxmi Puja")
        traded = days["2026-10-27"]
        self.assertEqual(traded["status"], "traded")
        self.assertEqual(traded["index"], {
            "close": "2630.76", "change": "0.94", "change_pct": "0.0300",
            "previous_date": "2026-10-26", "source": "crawled",
        })
        self.assertEqual([e["label"] for e in traded["events"]], ["BC ADBL", "BC NABIL"])
        self.assertEqual(days["2026-10-28"]["status"], "pending")

    def test_month_by_bs_year_and_month(self, _today):
        body = self.client.get(MONTH_URL, {"bs_year": "2082", "bs_month": "12"}).json()
        self.assertEqual((body["month_name"], body["next"]), ("Chaitra", {"bs_year": 2083, "bs_month": 1}))

    def test_month_rejects_bad_params(self, _today):
        for params in ({"bs_year": "2083", "bs_month": "13"}, {"bs_year": "abc", "bs_month": "1"},
                       {"bs_year": "2083"}, {"bs_year": "1900", "bs_month": "1"}):
            with self.subTest(params=params):
                self.assertEqual(self.client.get(MONTH_URL, params).status_code, 400)

    def test_day_has_full_index_events_and_bs_labels(self, _today):
        body = self.client.get(DAY_URL, {"date": "2026-10-27"}).json()
        self.assertEqual(body["status"], "traded")
        self.assertEqual(body["bs"], {
            "year": 2083, "month": 7, "day": 10, "month_name": "Kartik",
            "label_np": "१० कार्तिक २०८३", "weekday_np": "मंगलबार",
        })
        self.assertEqual(
            {k: body["index"][k] for k in ("open", "high", "low", "close", "change", "turnover", "volume", "transactions")},
            {"open": "2629.00", "high": "2640.10", "low": "2620.00", "close": "2630.76", "change": "0.94",
             "turnover": "4500000000.00", "volume": 9000000, "transactions": 60000},
        )
        event = body["events"][0]
        self.assertEqual((event["type"], event["symbol"], event["company_name"], event["bonus_pct"]),
                         ("book_closure", "ADBL", "ADBL Ltd", "10.0000"))

    def test_day_defaults_to_today(self, _today):
        body = self.client.get(DAY_URL).json()
        self.assertEqual((body["date"], body["status"], body["is_today"], body["index"]), ("2026-10-28", "pending", True, None))

    def test_future_day_has_no_index(self, _today):
        body = self.client.get(DAY_URL, {"date": "2026-11-02"}).json()
        self.assertEqual((body["status"], body["index"]), ("future", None))

    def test_day_rejects_bad_dates(self, _today):
        for raw in ("27-10-2026", "2026-02-30", "1900-01-01"):
            with self.subTest(raw=raw):
                self.assertEqual(self.client.get(DAY_URL, {"date": raw}).status_code, 400)

    def test_missing_index_is_404(self, _today):
        MarketIndex.objects.all().delete()
        self.assertEqual(self.client.get(MONTH_URL).status_code, 404)
        self.assertEqual(self.client.get(DAY_URL).status_code, 404)

    def test_needs_view_market_data(self, _today):
        client = APIClient()
        for url in (MONTH_URL, DAY_URL):
            self.assertIn(client.get(url).status_code, (401, 403))
        client.force_authenticate(_user("cal-no-market", permissions=["view_news"]))
        for url in (MONTH_URL, DAY_URL):
            self.assertEqual(client.get(url).status_code, 403)

    def test_company_access_narrows_events(self, _today):
        viewer = _user("cal-api-viewer", permissions=["view_market_data"])
        UserCompanyAccess.objects.create(user=viewer, company=self.nabil, status=1)
        client = APIClient()
        client.force_authenticate(viewer)
        month = {d["date"]: d for d in client.get(MONTH_URL).json()["days"]}
        self.assertEqual([e["symbol"] for e in month["2026-10-27"]["events"]], ["NABIL"])
        day = client.get(DAY_URL, {"date": "2026-10-27"}).json()
        self.assertEqual([e["symbol"] for e in day["events"]], ["NABIL"])
        # The index is whole-market: not narrowed.
        self.assertEqual(day["index"]["close"], "2630.76")
