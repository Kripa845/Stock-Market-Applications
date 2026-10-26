"""1-minute bars built from timestamped floorsheet trades."""

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from django.test import TestCase

from apps.floorsheet.services.intraday import aggregate_intraday_trades


class IntradayAggregationTests(TestCase):

    def setUp(self):
        self.npt = ZoneInfo("Asia/Kathmandu")

    def trade(self, hour, minute, second, rate, quantity):
        return SimpleNamespace(
            trade_time=datetime(2026, 9, 28, hour, minute, second, tzinfo=self.npt),
            rate=Decimal(rate),
            quantity=quantity,
        )

    def test_aggregates_first_last_high_low_and_volume(self):
        bars = aggregate_intraday_trades([
            self.trade(11, 0, 5, "100", 2),
            self.trade(11, 0, 45, "103", 3),
            self.trade(11, 0, 58, "99", 4),
        ])

        self.assertEqual(len(bars), 1)
        self.assertEqual(
            {key: bars[0][key] for key in ("open", "high", "low", "close", "volume")},
            {"open": 100.0, "high": 103.0, "low": 99.0, "close": 99.0, "volume": 9},
        )

    def test_leaves_empty_minutes_as_gaps(self):
        bars = aggregate_intraday_trades([
            self.trade(11, 0, 10, "100", 1),
            self.trade(11, 3, 10, "101", 1),
        ])

        self.assertEqual(len(bars), 2)
        self.assertNotEqual(bars[0]["time"], bars[1]["time"])

    def test_serializes_nepal_timezone_offset(self):
        bars = aggregate_intraday_trades([self.trade(11, 0, 10, "100", 1)])

        self.assertTrue(bars[0]["time"].endswith("+05:45"))
