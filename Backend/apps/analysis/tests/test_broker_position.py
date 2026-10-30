"""
Broker position: one broker's running net in one stock, daily and intraday.

Sample (buyer <- seller, qty @ rate, Nepal time):

    2026-09-14  11:00:30  10 <- 20   100 @ 500
                11:00:50  20 <- 10    40 @ 505
                11:03:00  30 <- 40    70 @ 502     (broker 10 not involved)
                11:07:10  10 <- 10    25 @ 506     (self trade)
    2026-09-15  11:02:00  10 <- 30    60 @ 520
    2026-09-16  11:01:00  30 <- 40    10 @ 510     (broker 10 idle)

Broker 10: day 1 bought 125 / sold 65 -> net +60; day 2 +60; day 3 0 -> position 60, 120, 120.
Without self trades: day 1 bought 100 / sold 40 -> +60 (the self trade nets to zero anyway).
"""

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.test import TestCase
from rest_framework.test import APIClient

from apps.analysis.services.broker_position import build_broker_position
from apps.companies.models import Company
from apps.floorsheet.models import FloorsheetTransaction, IntradayCandle
from apps.market_data.models import DailyPrice
from apps.users.models import CustomRole, User, UserCompanyAccess

NPT = ZoneInfo("Asia/Kathmandu")
D1, D2, D3 = date(2026, 9, 14), date(2026, 9, 15), date(2026, 9, 16)


def at(day, hour, minute, second=0):
    return datetime(day.year, day.month, day.day, hour, minute, second, tzinfo=NPT)


class BrokerPositionTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(symbol="POSN", name="Position Test", sector="Banking")
        self.seq = 0
        for day, when, buyer, seller, quantity, rate in (
            (D1, at(D1, 11, 0, 30), "10", "20", 100, 500),
            (D1, at(D1, 11, 0, 50), "20", "10", 40, 505),
            (D1, at(D1, 11, 3), "30", "40", 70, 502),
            (D1, at(D1, 11, 7, 10), "10", "10", 25, 506),
            (D2, at(D2, 11, 2), "10", "30", 60, 520),
            (D3, at(D3, 11, 1), "30", "40", 10, 510),
        ):
            self.seq += 1
            FloorsheetTransaction.objects.create(
                company=self.company, date=day, trade_time=when, transaction_id=f"P{self.seq:04d}",
                buyer_broker=buyer, seller_broker=seller, quantity=quantity, rate=Decimal(rate),
                amount=Decimal(rate) * quantity,
            )
        for day, close in ((D1, 506), (D2, 520), (D3, 510)):
            DailyPrice.objects.create(company=self.company, date=day, open=close, high=close, low=close,
                                      close=close, volume=1, turnover=close, source="crawled")

    def test_daily_running_total_keeps_idle_sessions(self):
        data = build_broker_position(self.company, "10", "1W", exclude_self=False)
        self.assertEqual(data["mode"], "daily")
        self.assertEqual([p["date"] for p in data["points"]], [D1, D2, D3])
        self.assertEqual([(p["bought"], p["sold"], p["net"]) for p in data["points"]], [(125, 65, 60), (60, 0, 60), (0, 0, 0)])
        self.assertEqual([p["position"] for p in data["points"]], [60, 120, 120])
        self.assertEqual([p["price"] for p in data["points"]], [Decimal("506"), Decimal("520"), Decimal("510")])

    def test_totals(self):
        totals = build_broker_position(self.company, "10", "1W", exclude_self=False)["totals"]
        self.assertEqual((totals["bought"], totals["sold"], totals["net"]), (185, 65, 120))
        # (50,000 + 12,650 + 31,200) / 185 = 507.297 and (20,200 + 12,650) / 65 = 505.38
        self.assertEqual(totals["avg_buy_price"], Decimal("507.30"))
        self.assertEqual(totals["avg_sell_price"], Decimal("505.38"))
        self.assertEqual((totals["active_sessions"], totals["self_trades"], totals["stock_volume"]), (2, 1, 305))
        # Broker 10 was on 185 + 65 = 250 sides of 2 x 305 = 610.
        self.assertEqual(totals["share_of_volume_pct"], Decimal("40.98"))
        self.assertEqual(totals["last_price"], Decimal("510"))

    def test_excluding_self_trades(self):
        data = build_broker_position(self.company, "10", "1W", exclude_self=True)
        self.assertEqual((data["points"][0]["bought"], data["points"][0]["sold"]), (100, 40))
        self.assertEqual(data["totals"]["net"], 120)

    def test_range_counts_sessions_back_from_the_latest(self):
        data = build_broker_position(self.company, "10", "2D", exclude_self=False)
        self.assertEqual((data["start_date"], data["end_date"], data["sessions"]), (D2, D3, 2))

    def test_intraday_buckets_follow_trade_times(self):
        IntradayCandle.objects.create(company=self.company, interval="1m", bucket_start=at(D3, 11, 1),
                                      open=510, high=510, low=510, close=510, volume=10, turnover=5100, trade_count=1)
        data = build_broker_position(self.company, "30", "1D", exclude_self=False)
        self.assertEqual((data["mode"], data["bucket_minutes"]), ("intraday", 1))
        self.assertEqual(len(data["points"]), 1)
        point = data["points"][0]
        self.assertEqual((point["time"], point["bought"], point["position"], point["price"]), (at(D3, 11, 1), 10, 10, Decimal("510")))

    def test_two_day_intraday_uses_five_minute_buckets(self):
        data = build_broker_position(self.company, "10", "2D", exclude_self=False)
        self.assertEqual(data["bucket_minutes"], 5)
        self.assertEqual([(p["time"], p["net"]) for p in data["points"]], [(at(D2, 11, 0), 60)])

    def test_untimed_trades_are_reported_not_charted(self):
        FloorsheetTransaction.objects.filter(date=D3).update(trade_time=None)
        data = build_broker_position(self.company, "30", "1D", exclude_self=False)
        self.assertEqual(data["points"], [])
        self.assertTrue(data["warnings"])

    def test_top_brokers_by_gross(self):
        top = build_broker_position(self.company, "10", "1W", exclude_self=False)["top_brokers"]
        self.assertEqual(top[0], {"broker": "10", "bought": 185, "sold": 65, "net": 120})

    def test_no_broker_opens_on_the_most_active_one(self):
        data = build_broker_position(self.company, "", "1W", exclude_self=False)
        self.assertEqual(data["broker"], "10")
        self.assertEqual(data["points"][-1]["position"], 120)


class BrokerPositionAPITests(TestCase):
    URL = "/api/analysis/broker-position/"

    def setUp(self):
        self.company = Company.objects.create(symbol="POSN", name="Position Test", sector="Banking")
        FloorsheetTransaction.objects.create(
            company=self.company, date=D1, trade_time=at(D1, 11, 0), transaction_id="A1",
            buyer_broker="10", seller_broker="20", quantity=5, rate=Decimal("100"), amount=Decimal("500"),
        )
        role = CustomRole.objects.create(name="analyst", permissions=["view_analysis"])
        self.user = User.objects.create_user(username="a", email="a@example.com", password="Pw-12345!",
                                             role=User.Role.VIEWER, custom_role=role)
        UserCompanyAccess.objects.create(user=self.user, company=self.company, status=1)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_returns_numbers(self):
        body = self.client.get(self.URL, {"symbol": "POSN", "broker": "10", "range": "1W"}).json()
        self.assertEqual(body["points"][0]["position"], 5)
        self.assertEqual(body["totals"]["avg_buy_price"], 100.0)
        self.assertEqual(body["points"][0]["date"], D1.isoformat())

    def test_validation(self):
        self.assertEqual(self.client.get(self.URL, {"broker": "10"}).status_code, 400)
        self.assertEqual(self.client.get(self.URL, {"symbol": "POSN", "broker": "10", "range": "5Y"}).status_code, 400)
        self.assertEqual(self.client.get(self.URL, {"symbol": "POSN"}).json()["broker"], "10")

    def test_company_access_and_permission(self):
        UserCompanyAccess.objects.filter(user=self.user).delete()
        self.assertEqual(self.client.get(self.URL, {"symbol": "POSN", "broker": "10"}).status_code, 403)
        self.user.custom_role.permissions = []
        self.user.custom_role.save()
        self.assertEqual(self.client.get(self.URL, {"symbol": "POSN", "broker": "10"}).status_code, 403)


class BrokerActivityTests(TestCase):
    """Several stocks on one time axis for one broker."""

    def setUp(self):
        from apps.analysis.services.broker_position import build_broker_activity

        self.build = build_broker_activity
        self.a = Company.objects.create(symbol="AAA", name="A", sector="Banking")
        self.b = Company.objects.create(symbol="BBB", name="B", sector="Hydropower")
        seq = 0
        for company, day, when, buyer, seller, quantity in (
            (self.a, D1, at(D1, 11, 0, 30), "10", "20", 100),
            (self.a, D2, at(D2, 11, 2), "20", "10", 40),
            (self.b, D2, at(D2, 11, 2, 30), "10", "30", 25),   # BBB only trades on D2
            (self.b, D3, at(D3, 14, 59, 59), "30", "10", 5),
        ):
            seq += 1
            FloorsheetTransaction.objects.create(
                company=company, date=day, trade_time=when, transaction_id=f"M{seq:04d}",
                buyer_broker=buyer, seller_broker=seller, quantity=quantity, rate=Decimal("100"), amount=Decimal(100 * quantity),
            )

    def test_daily_series_share_the_union_of_sessions(self):
        data = self.build("10", [self.a, self.b], "1W", exclude_self=False)
        self.assertEqual(data["times"], [D1, D2, D3])
        a, b = data["series"]
        self.assertEqual((a["symbol"], a["bought"], a["sold"]), ("AAA", [100, 0, 0], [0, 40, 0]))
        self.assertEqual((b["symbol"], b["bought"], b["sold"]), ("BBB", [0, 25, 0], [0, 0, 5]))
        self.assertEqual((a["totals"]["net"], b["totals"]["net"]), (60, 20))

    def test_intraday_uses_the_full_session_grid(self):
        data = self.build("10", [self.a, self.b], "1D", exclude_self=False)
        self.assertEqual((data["mode"], len(data["times"])), ("intraday", 240))
        b = data["series"][1]
        # The 14:59:59 trade falls in the last bucket.
        self.assertEqual((b["sold"][-1], sum(b["sold"])), (5, 5))

    def test_two_days_in_five_minute_buckets(self):
        data = self.build("10", [self.a, self.b], "2D", exclude_self=False)
        self.assertEqual(len(data["times"]), 96)
        a = data["series"][0]
        self.assertEqual(a["sold"][0], 40)                       # D2 11:02 -> 11:00 bucket

    def test_without_broker_opens_on_the_most_active(self):
        self.assertEqual(self.build("", [self.a, self.b], "1W", exclude_self=False)["broker"], "10")


class BrokerActivityAPITests(TestCase):
    URL = "/api/analysis/broker-activity/"

    def setUp(self):
        self.company = Company.objects.create(symbol="AAA", name="A", sector="Banking")
        FloorsheetTransaction.objects.create(
            company=self.company, date=D1, trade_time=at(D1, 11, 0), transaction_id="Z1",
            buyer_broker="10", seller_broker="20", quantity=5, rate=Decimal("100"), amount=Decimal("500"),
        )
        role = CustomRole.objects.create(name="analyst", permissions=["view_analysis"])
        self.user = User.objects.create_user(username="b", email="b@example.com", password="Pw-12345!",
                                             role=User.Role.VIEWER, custom_role=role)
        UserCompanyAccess.objects.create(user=self.user, company=self.company, status=1)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_returns_series(self):
        body = self.client.get(self.URL, {"symbols": "aaa", "broker": "10", "range": "1W"}).json()
        self.assertEqual(body["times"], [D1.isoformat()])
        self.assertEqual(body["series"][0]["bought"], [5])

    def test_validation_and_access(self):
        self.assertEqual(self.client.get(self.URL, {"broker": "10"}).status_code, 400)
        self.assertEqual(self.client.get(self.URL, {"symbols": ",".join("ABCDEFGHI")}).status_code, 400)
        self.assertEqual(self.client.get(self.URL, {"symbols": "NOPE"}).status_code, 404)
        UserCompanyAccess.objects.filter(user=self.user).delete()
        self.assertEqual(self.client.get(self.URL, {"symbols": "AAA"}).status_code, 403)
