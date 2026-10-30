from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.market_calendar.services.month_summary import month_summary
from apps.market_data.models import TradingHoliday
from apps.market_indices.models import IndexDaily, MarketIndex
from apps.users.models import CustomRole

D = Decimal
TODAY = date(2026, 10, 28)          # BS 2083-07-11; Kartik began 2026-10-18
URL = "/api/market-calendar/months/"


def _user(name, role="viewer", permissions=None):
    user = get_user_model().objects.create_user(username=name, email=f"{name}@example.com", password="pw", role=role)
    if permissions is not None:
        user.custom_role = CustomRole.objects.create(name=f"{name} role", permissions=permissions)
        user.save(update_fields=["custom_role"])
    return user


class MonthSummaryTests(TestCase):
    def setUp(self):
        self.nepse = MarketIndex.objects.create(code="NEPSE", name="NEPSE Index", kind="main")
        MarketIndex.objects.create(code="HOTELS", name="Hotels And Tourism Index", kind="sub",
                                   sector_name="Hotels And Tourism")
        for day, close, pct in (
            (date(2026, 9, 30), "2600.00", "0.10"),     # Aswin
            (date(2026, 10, 16), "2620.00", "0.50"),    # Aswin, last session before Kartik
            (date(2026, 10, 26), "2646.20", "1.00"),    # Kartik
            (date(2026, 10, 27), "2619.74", None),      # no published % -> previous stored close
        ):
            IndexDaily.objects.create(index=self.nepse, date=day, close=D(close),
                                      source_change_pct=D(pct) if pct else None)
        TradingHoliday.objects.create(date=date(2026, 10, 20), name="Laxmi Puja")

    def test_bs_months_newest_first_with_day_tiles(self):
        data = month_summary(today=TODAY, months=6)
        kartik, aswin = data["months"]
        self.assertEqual((kartik["label_np"], kartik["is_current"], kartik["partial"]), ("कात्तिक २०८३", True, True))
        self.assertEqual(aswin["label_np"], "असोज २०८३")
        self.assertEqual(data["today_day"], 11)
        days = {d["date"]: d for d in kartik["days"]}
        self.assertEqual(days[date(2026, 10, 26)]["change_pct"], D("1.00"))
        self.assertEqual(round(days[date(2026, 10, 27)]["change_pct"], 2), D("-1.00"))
        self.assertEqual(days[date(2026, 10, 26)]["previous_close"], D("2620.00"))
        self.assertEqual(days[date(2026, 10, 20)]["status"], "holiday")
        self.assertEqual(days[TODAY]["status"], "pending")
        self.assertEqual(days[date(2026, 10, 29)]["status"], "future")
        # Kartik: 2619.74 against Aswin's last close 2620.00.
        self.assertEqual(round(kartik["change_pct"], 2), D("-0.01"))
        self.assertEqual(kartik["sessions"], 2)

    def test_window_stops_at_history_start(self):
        data = month_summary(today=TODAY, months=12)
        self.assertEqual(len(data["months"]), 2)
        aswin = data["months"][1]
        # History starts inside Aswin, so its first day has no previous close.
        self.assertTrue(aswin["partial"])
        self.assertIsNone(aswin["change_pct"])
        self.assertEqual(data["notes"], ["Index history starts 30 Sep 2026."])

    def test_stats(self):
        stats = month_summary(today=TODAY, months=6)["stats"]
        self.assertEqual(stats["best_month"]["label"], "Kartik 2083")
        self.assertIsNone(stats["worst_month"])     # only one month with a change
        self.assertEqual((stats["sessions"], stats["up_days"]), (4, 3))
        # Each weekday has one session, which says nothing.
        self.assertIsNone(stats["strongest_weekday"])

    def test_ad_months(self):
        data = month_summary(mode="ad", today=TODAY, months=6)
        october, september = data["months"]
        self.assertEqual((october["label"], data["today_day"], len(october["days"])), ("October 2026", 28, 31))
        self.assertEqual(round(october["change_pct"], 4), round((D("2619.74") / D("2600.00") - 1) * 100, 4))
        self.assertTrue(september["partial"])

    def test_catalogue_short_labels(self):
        self.assertEqual(month_summary(today=TODAY)["indices"],
                         [{"code": "NEPSE", "label": "NEPSE"}, {"code": "HOTELS", "label": "Hotels"}])


class MonthSummaryApiTests(TestCase):
    def setUp(self):
        nepse = MarketIndex.objects.create(code="NEPSE", name="NEPSE Index", kind="main")
        MarketIndex.objects.create(code="TRADING", name="Trading Index", kind="sub", sector_name="Trading")
        IndexDaily.objects.create(index=nepse, date=date(2026, 10, 26), close=D("2629.82"), source_change_pct=D("-0.16"))
        self.client = APIClient()
        self.client.force_authenticate(_user("months-admin", role="admin"))

    def test_returns_json_numbers(self):
        body = self.client.get(URL, {"calendar": "ad", "months": 6}).json()
        self.assertEqual(body["calendar"], "ad")
        day = next(d for m in body["months"] for d in m["days"] if d["date"] == "2026-10-26")
        self.assertEqual(day["change_pct"], -0.16)

    def test_bad_params(self):
        for params in ({"calendar": "lunar"}, {"months": 5}, {"index": "NOPE"}):
            self.assertEqual(self.client.get(URL, params).status_code, 400, params)

    def test_index_without_sessions(self):
        self.assertEqual(self.client.get(URL, {"index": "trading"}).status_code, 404)

    def test_needs_market_data_permission(self):
        client = APIClient()
        client.force_authenticate(_user("months-none", permissions=[]))
        self.assertEqual(client.get(URL).status_code, 403)
