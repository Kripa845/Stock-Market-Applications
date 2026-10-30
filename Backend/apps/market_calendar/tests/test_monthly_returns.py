from datetime import date
from decimal import Decimal

import nepali_datetime
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.market_calendar.services.month_summary import month_summary
from apps.market_calendar.services.monthly_returns import monthly_returns
from apps.market_indices.models import IndexDaily, MarketIndex
from apps.users.models import CustomRole

D = Decimal
TODAY = date(2026, 10, 28)          # BS 2083-07-11 (Kartik, running)
URL = "/api/market-calendar/monthly/"


def bs(year, month, day):
    return nepali_datetime.date(year, month, day).to_datetime_date()


# BS date -> close.  Jestha 2082 has no session; Falgun 2081 is where the history starts.
CLOSES = {
    (2081, 11, 10): "2000.00",
    (2081, 12, 15): "2100.00",      # Chaitra 2081  +5%
    (2082, 1, 10): "2205.00",       # Baishakh 2082 +5%
    (2082, 3, 5): "2100.00",        # Asar 2082 vs Baishakh's close: -4.7619%
    (2082, 12, 20): "2310.00",      # Chaitra 2082 +10%
    (2083, 1, 5): "2079.00",        # Baishakh 2083 -10%
    (2083, 7, 5): "2120.58",        # Kartik 2083 (running) +2%
}


def _user(name, role="viewer", permissions=None):
    user = get_user_model().objects.create_user(username=name, email=f"{name}@example.com", password="pw", role=role)
    if permissions is not None:
        user.custom_role = CustomRole.objects.create(name=f"{name} role", permissions=permissions)
        user.save(update_fields=["custom_role"])
    return user


class MonthlyReturnsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.nepse = MarketIndex.objects.create(code="NEPSE", name="NEPSE Index", kind="main")
        MarketIndex.objects.create(code="HOTELS", name="Hotels And Tourism Index", kind="sub",
                                   sector_name="Hotels And Tourism")
        for (y, m, d), close in CLOSES.items():
            IndexDaily.objects.create(index=self.nepse, date=bs(y, m, d), close=D(close))

    def data(self):
        return monthly_returns(today=TODAY)

    def year(self, data, year):
        return next(y for y in data["years"] if y["year"] == year)

    def pct(self, data, year, month):
        cell = self.year(data, year)["months"][month - 1]
        return None if cell is None or cell["return_pct"] is None else round(cell["return_pct"], 4)

    def test_rows_newest_year_first_down_to_history_start(self):
        data = self.data()
        self.assertEqual([y["year"] for y in data["years"]], [2083, 2082, 2081])
        self.assertEqual(data["months"][0]["label_np"], "वैशाख")
        self.assertEqual(data["current"], {"year": 2083, "month": 7})

    def test_month_is_last_close_against_previous_months_last_close(self):
        data = self.data()
        self.assertEqual(self.pct(data, 2081, 12), D("5"))
        self.assertEqual(self.pct(data, 2082, 1), D("5"))
        self.assertEqual(self.pct(data, 2083, 1), D("-10"))
        cell = self.year(data, 2082)["months"][0]
        self.assertEqual((cell["close"], cell["previous_close"], cell["close_date"]),
                         (D("2205.00"), D("2100.00"), bs(2082, 1, 10)))

    def test_month_without_a_session_is_blank_and_the_next_spans_it(self):
        data = self.data()
        self.assertIsNone(self.pct(data, 2082, 2))
        self.assertEqual(self.pct(data, 2082, 3), round((D("2100") / D("2205") - 1) * 100, 4))

    def test_pre_history_and_future_months_are_blank(self):
        data = self.data()
        self.assertIsNone(self.year(data, 2081)["months"][0])           # before the history
        self.assertIsNone(self.year(data, 2083)["months"][7])           # Mangsir 2083, future
        first = self.year(data, 2081)["months"][10]                     # history starts inside Falgun
        self.assertEqual((first["return_pct"], first["partial"]), (None, True))

    def test_year_return_compounds_from_closes_not_the_sum_of_months(self):
        data = self.data()
        y2082 = self.year(data, 2082)
        self.assertEqual(round(y2082["year_return"], 4), D("10"))      # 2310 / 2100
        months = [c["return_pct"] for c in y2082["months"] if c and c["return_pct"] is not None]
        compounded = 1
        for move in months:
            compounded *= 1 + move / 100
        self.assertAlmostEqual(float((compounded - 1) * 100), float(y2082["year_return"]), places=6)
        self.assertNotAlmostEqual(float(sum(months)), float(y2082["year_return"]), places=2)

    def test_partial_flags(self):
        data = self.data()
        kartik = self.year(data, 2083)["months"][6]
        self.assertEqual((kartik["is_current"], kartik["partial"], round(kartik["return_pct"], 4)), (True, True, D("2")))
        self.assertTrue(self.year(data, 2083)["partial"])               # running year
        self.assertTrue(self.year(data, 2081)["partial"])               # history starts in it
        self.assertFalse(self.year(data, 2082)["partial"])
        self.assertIsNone(self.year(data, 2081)["year_return"])         # no close before it

    def test_avg_row_and_months_up_skip_blanks(self):
        data = self.data()
        avg = data["avg_row"]
        self.assertEqual((round(avg[0]["average_pct"], 4), avg[0]["years"]), (D("-2.5"), 2))   # Baishakh 5, -10
        self.assertIsNone(avg[1])                                        # Jestha: only a blank
        self.assertEqual(round(avg[6]["average_pct"], 4), D("2"))       # Kartik: the running month so far
        stats = data["stats"]
        self.assertEqual((stats["months_up"], stats["months_counted"]), (4, 6))

    def test_sidebar_stats(self):
        stats = self.data()["stats"]
        self.assertEqual((stats["best_year"]["year"], round(stats["best_year"]["year_return"], 4)), (2082, D("10")))
        self.assertEqual(stats["worst_year"]["year"], 2083)
        self.assertEqual((stats["strongest_month"]["month"], stats["strongest_month"]["label_np"]), (12, "चैत"))
        self.assertEqual(round(stats["strongest_month"]["average_pct"], 4), D("7.5"))

    def test_daily_changes_compound_to_the_month_tile(self):
        # Day-by-day falls back to the previous stored close without a published %.
        for day, close in ((bs(2083, 7, 6), "2150.00"), (bs(2083, 7, 7), "2101.33")):
            IndexDaily.objects.create(index=self.nepse, date=day, close=D(close))
        daily = month_summary(today=TODAY, months=6)["months"][0]
        compounded = 1
        for day in daily["days"]:
            if day["change_pct"] is not None:
                compounded *= 1 + day["change_pct"] / 100
        tile = self.year(monthly_returns(today=TODAY), 2083)["months"][6]["return_pct"]
        self.assertAlmostEqual(float((compounded - 1) * 100), float(tile), places=6)

    def test_new_close_refreshes_the_cached_result(self):
        self.data()
        IndexDaily.objects.create(index=self.nepse, date=bs(2083, 7, 8), close=D("2286.90"))
        self.assertEqual(self.pct(self.data(), 2083, 7), D("10"))

    def test_api(self):
        client = APIClient()
        client.force_authenticate(_user("viewer"))
        body = client.get(URL).json()
        self.assertEqual((body["index"]["code"], body["years"][0]["year"]), ("NEPSE", 2083))
        self.assertEqual([i["code"] for i in body["indices"]], ["NEPSE", "HOTELS"])
        self.assertEqual(client.get(URL, {"index": "nope"}).status_code, 400)
        self.assertEqual(client.get(URL, {"index": "hotels"}).status_code, 404)    # no sessions yet

    def test_needs_view_market_data(self):
        client = APIClient()
        client.force_authenticate(_user("limited", role="custom", permissions=["view_news"]))
        self.assertEqual(client.get(URL).status_code, 403)
