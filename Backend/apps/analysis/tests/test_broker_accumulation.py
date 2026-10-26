"""
Broker accumulation / distribution over a small hand-calculated floorsheet.

Sample (buyer <- seller, qty @ rate):

    2026-09-14  T1  10 <- 20   100 @ 500
                T2  10 <- 30   200 @ 510
                T3  40 <- 20    50 @ 505
                T4  20 <- 20    30 @ 500   (self trade)
    2026-09-15  T5  10 <- 30   100 @ 520
                T6  30 <- 40    60 @ 515

Total traded 540.  Per broker over both days:

    10: buy 400 / 204,000 (avg 510.00), sell 0            -> net +400 (74.07%)
    20: buy  30 /  15,000, sell 180 / 90,250 (avg 501.39) -> net -150 (-27.78%)
    30: buy  60 /  30,900, sell 300 / 154,000 (avg 513.33)-> net -240 (-44.44%)
    40: buy  50 /  25,250, sell  60 /  30,900             -> net  -10 (-1.85%)

Top buy net 400, top sell net -400, ratio 1.00 -> neutral.
"""

from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.analysis.services.broker_accumulation import (
    ACCUMULATION, DISTRIBUTION, NEUTRAL, NO_DATA,
    Window, broker_rows, build_broker_flow, build_broker_signal, classify, resolve_window, streaks,
)
from apps.companies.models import Company
from apps.market_data.models import DailyPrice
from apps.floorsheet.models import FloorsheetTransaction
from apps.users.models import User

D1 = date(2026, 9, 14)
D2 = date(2026, 9, 15)


class AccumulationTestBase(TestCase):

    def setUp(self):
        self.company = Company.objects.create(symbol="ACCU", name="Accumulation Test", sector="Banking")
        self.counter = 0
        for when, buyer, seller, quantity, rate in (
            (D1, "10", "20", 100, 500), (D1, "10", "30", 200, 510), (D1, "40", "20", 50, 505),
            (D1, "20", "20", 30, 500), (D2, "10", "30", 100, 520), (D2, "30", "40", 60, 515),
        ):
            self.tx(when, buyer, seller, quantity, rate)
        DailyPrice.objects.create(company=self.company, date=D2, open=520, high=530, low=515, close=530, volume=160, turnover=84000, source="crawled")
        # Synthetic prices must never be used as the latest close.
        DailyPrice.objects.create(company=self.company, date=date(2026, 9, 16), open=999, high=999, low=999, close=999, volume=1, turnover=999, source="unverified")

    def tx(self, when, buyer, seller, quantity, rate):
        self.counter += 1
        return FloorsheetTransaction.objects.create(
            company=self.company, date=when, transaction_id=f"ACC{self.counter:04d}",
            buyer_broker=buyer, seller_broker=seller, quantity=quantity, rate=Decimal(str(rate)),
        )

    def both_days(self):
        return Window("custom", D1, D2, (D2, D1))

    @staticmethod
    def by_broker(rows):
        return {row["broker"]: row for row in rows}


class BrokerRowTests(AccumulationTestBase):

    def test_net_averages_and_share_of_volume(self):
        rows, totals = broker_rows(self.company, self.both_days(), exclude_self_trades=False)
        brokers = self.by_broker(rows)

        self.assertEqual(totals["total_qty"], 540)
        self.assertEqual(totals["self_trade_qty"], 30)
        self.assertEqual([row["broker"] for row in rows], ["10", "40", "20", "30"])  # biggest net buyer first

        self.assertEqual((brokers["10"]["buy_qty"], brokers["10"]["sell_qty"], brokers["10"]["net_qty"]), (400, 0, 400))
        self.assertEqual(brokers["10"]["buy_amount"], Decimal("204000"))
        self.assertEqual(brokers["10"]["avg_buy"], Decimal("510.00"))
        self.assertEqual(brokers["10"]["net_pct_of_volume"], Decimal("74.07"))

        self.assertEqual(brokers["20"]["net_qty"], -150)
        self.assertEqual(brokers["20"]["avg_sell"], Decimal("501.39"))
        self.assertEqual(brokers["20"]["net_pct_of_volume"], Decimal("-27.78"))
        self.assertEqual(brokers["30"]["avg_sell"], Decimal("513.33"))
        self.assertEqual(brokers["30"]["net_pct_of_volume"], Decimal("-44.44"))
        self.assertEqual(sum(row["net_qty"] for row in rows), 0)

    def test_broker_with_no_sells_has_no_average_sell_price(self):
        rows, _ = broker_rows(self.company, self.both_days(), exclude_self_trades=False)
        self.assertIsNone(self.by_broker(rows)["10"]["avg_sell"])

    def test_excluding_self_trades_removes_them_from_totals(self):
        rows, totals = broker_rows(self.company, self.both_days(), exclude_self_trades=True)
        brokers = self.by_broker(rows)

        self.assertEqual(totals["total_qty"], 510)
        self.assertEqual(totals["self_trade_qty"], 0)
        self.assertEqual((brokers["20"]["buy_qty"], brokers["20"]["sell_qty"]), (0, 150))
        self.assertEqual(brokers["10"]["net_pct_of_volume"], Decimal("78.43"))

    @override_settings(BROKER_EXCLUDE_SELF_TRADES=True)
    def test_self_trade_exclusion_defaults_to_the_setting(self):
        _, totals = broker_rows(self.company, self.both_days())
        self.assertTrue(totals["exclude_self_trades"])
        self.assertEqual(totals["total_qty"], 510)


class SignalTests(AccumulationTestBase):

    def test_classify_thresholds_and_zero_division(self):
        self.assertEqual(classify(130, -100), (ACCUMULATION, Decimal("1.3")))
        self.assertEqual(classify(70, -100), (DISTRIBUTION, Decimal("0.7")))
        self.assertEqual(classify(100, -100), (NEUTRAL, Decimal("1")))
        self.assertEqual(classify(120, -100)[0], NEUTRAL)  # 1.2 is not above 1.2
        self.assertEqual(classify(100, 0), (ACCUMULATION, None))  # nobody net sold
        self.assertEqual(classify(0, 0), (NEUTRAL, None))
        self.assertEqual(classify(0, -50)[0], DISTRIBUTION)

    @override_settings(BROKER_SIGNAL_ACCUMULATION_RATIO="0.9", BROKER_SIGNAL_DISTRIBUTION_RATIO="0.5")
    def test_thresholds_come_from_settings(self):
        self.assertEqual(classify(100, -100)[0], ACCUMULATION)

    def test_signal_top_lists_and_close(self):
        signal = build_broker_signal(self.company, self.both_days(), exclude_self_trades=False)

        self.assertEqual(signal["signal"], NEUTRAL)
        self.assertEqual(signal["ratio"], Decimal("1.00"))
        self.assertEqual((signal["top5_buy_net"], signal["top5_sell_net"]), (400, -400))
        self.assertEqual([row["broker"] for row in signal["accumulators"]], ["10"])
        self.assertEqual([row["broker"] for row in signal["distributors"]], ["30", "20", "40"])
        self.assertEqual(signal["latest_close"], Decimal("530"))
        self.assertEqual(signal["latest_close_date"], D2)
        # (530 - 510) / 510
        self.assertEqual(signal["accumulators"][0]["close_vs_avg_buy_pct"], Decimal("3.92"))

    def test_one_day_window_reads_only_the_latest_session(self):
        # D2 alone: 10 +100, 30 +60-100 = -40, 40 -60.
        signal = build_broker_signal(self.company, resolve_window(self.company, "1d"), exclude_self_trades=False)
        self.assertEqual((signal["top5_buy_net"], signal["top5_sell_net"]), (100, -100))
        self.assertEqual([row["broker"] for row in signal["distributors"]], ["40", "30"])

    def test_empty_window_has_no_data(self):
        window = resolve_window(self.company, start_date=date(2026, 1, 1), end_date=date(2026, 1, 31))
        signal = build_broker_signal(self.company, window)
        self.assertEqual(signal["signal"], NO_DATA)
        self.assertEqual(signal["accumulators"], [])
        self.assertEqual(build_broker_flow(self.company, window), {"points": [], "warnings": []})


class WindowAndStreakTests(AccumulationTestBase):

    def test_windows_count_sessions_from_the_latest_one(self):
        one_day = resolve_window(self.company, "1d")
        self.assertEqual((one_day.start_date, one_day.end_date, one_day.sessions), (D2, D2, (D2,)))
        # Only two sessions exist, so "1w" covers both instead of reaching back 7 calendar days.
        week = resolve_window(self.company, "1w")
        self.assertEqual((week.start_date, week.end_date, len(week.sessions)), (D1, D2, 2))
        self.assertEqual(resolve_window(self.company, "bogus").key, "1w")

    def test_streaks(self):
        runs = streaks(self.company, ["10", "20", "30", "40"], D2, exclude_self_trades=False)
        self.assertEqual(runs["10"], {"direction": "buying", "days": 2})
        self.assertEqual(runs["30"], {"direction": "selling", "days": 2})
        self.assertEqual(runs["40"], {"direction": "selling", "days": 1})  # bought on D1, sold on D2
        self.assertEqual(runs["20"], {"direction": None, "days": 0})  # no trade on D2


class FlowTests(AccumulationTestBase):

    def test_daily_flow_points(self):
        points = build_broker_flow(self.company, self.both_days(), exclude_self_trades=False)["points"]
        self.assertEqual([p["date"] for p in points], [D1, D2])
        self.assertEqual((points[0]["top5_buy_net"], points[0]["top5_sell_net"], points[0]["volume"]), (350, -350, 380))
        self.assertEqual((points[1]["top5_buy_net"], points[1]["top5_sell_net"], points[1]["volume"]), (100, -100, 160))
        self.assertIsNone(points[0]["close"])
        self.assertEqual(points[1]["close"], Decimal("530"))

    def test_bought_must_equal_sold_per_day(self):
        self.assertEqual(build_broker_flow(self.company, self.both_days())["warnings"], [])
        self.tx(D2, "10", "", 10, 520)  # unusable seller code: the buy side counts it, the sell side cannot

        with self.assertLogs("apps.analysis.services.broker_accumulation", level="WARNING"):
            warnings = build_broker_flow(self.company, self.both_days())["warnings"]
        self.assertEqual(warnings, ["ACCU 2026-09-15: bought 170 != sold 160"])


class DuplicateImportTests(AccumulationTestBase):

    def test_reimporting_the_same_trades_adds_nothing(self):
        before = FloorsheetTransaction.objects.count()
        duplicates = [
            FloorsheetTransaction(company=self.company, date=D1, transaction_id="ACC0001",
                                  buyer_broker="10", seller_broker="20", quantity=100, rate=Decimal("500")),
        ]
        FloorsheetTransaction.objects.bulk_create(duplicates, ignore_conflicts=True)
        self.assertEqual(FloorsheetTransaction.objects.count(), before)

        with self.assertRaises(IntegrityError), transaction.atomic():
            FloorsheetTransaction.objects.create(
                company=self.company, date=D1, transaction_id="ACC0001",
                buyer_broker="10", seller_broker="20", quantity=100, rate=Decimal("500"),
            )


class AccumulationApiTests(AccumulationTestBase):

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username="accumulation-admin", email="accumulation-admin@example.test",
            password="unused-test-password", role=User.Role.ADMIN,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_signal_endpoint(self):
        response = self.client.get("/api/analysis/broker-signal/", {"symbol": "accu", "window": "1w"})
        self.assertEqual(response.status_code, 200, response.content[:500])
        self.assertEqual(response.data["window"], {"key": "1w", "start_date": D1, "end_date": D2, "sessions": 2})
        self.assertEqual(response.data["accumulators"][0]["broker"], "10")
        self.assertEqual(response.data["accumulators"][0]["name"], "Broker 10")
        self.assertEqual(response.data["accumulators"][0]["streak"], {"direction": "buying", "days": 2})

    def test_summary_and_flow_endpoints(self):
        summary = self.client.get("/api/analysis/broker-summary/", {"symbol": "ACCU", "start_date": "2026-09-14", "exclude_self": "1"})
        self.assertEqual(summary.status_code, 200, summary.content[:500])
        self.assertEqual(summary.data["total_qty"], 510)
        self.assertEqual(summary.data["broker_count"], 4)

        flow = self.client.get("/api/analysis/broker-flow/", {"symbol": "ACCU", "window": "1m"})
        self.assertEqual(flow.status_code, 200)
        self.assertEqual(len(flow.data["points"]), 2)

    def test_new_trades_are_not_hidden_by_the_cache(self):
        first = self.client.get("/api/analysis/broker-summary/", {"symbol": "ACCU", "window": "1m"}).data["total_qty"]
        self.tx(D2, "10", "30", 25, 520)
        second = self.client.get("/api/analysis/broker-summary/", {"symbol": "ACCU", "window": "1m"}).data["total_qty"]
        self.assertEqual((first, second), (540, 565))

    def test_query_validation(self):
        self.assertEqual(self.client.get("/api/analysis/broker-signal/").status_code, 400)
        self.assertEqual(self.client.get("/api/analysis/broker-signal/", {"symbol": "ACCU", "window": "2y"}).status_code, 400)
        self.assertEqual(self.client.get("/api/analysis/broker-signal/", {"symbol": "ACCU", "start_date": "14-09-2026"}).status_code, 400)
        self.assertEqual(self.client.get("/api/analysis/broker-signal/", {"symbol": "ACCU", "exclude_self": "maybe"}).status_code, 400)
        self.assertEqual(self.client.get("/api/analysis/broker-signal/", {"symbol": "NOPE"}).status_code, 404)
