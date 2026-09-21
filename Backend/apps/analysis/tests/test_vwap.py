"""Daily VWAP: turnover / volume, per trading day."""

from decimal import Decimal

from django.test import TestCase

from apps.analysis.services.daily_metrics import (
    build_analysis_rows,
    calculate_daily_vwap,
    calculate_period_vwap,
)


class FakePrice:
    """Minimal stand-in for DailyPrice so the maths is testable without a DB."""

    def __init__(self, date, close=None, volume=None, turnover=None):
        self.date = date
        self.close = close
        self.volume = volume
        self.turnover = turnover


class DailyVWAPTests(TestCase):

    def test_known_value(self):
        # The worked example from the specification.
        self.assertEqual(
            calculate_daily_vwap(Decimal("1000000"), 5000),
            Decimal("200.0000"),
        )

    def test_non_integer_result_keeps_decimal_precision(self):
        # 1234567 / 3333 = 370.408... -> must not be truncated to an int
        # and must not go through float.
        result = calculate_daily_vwap(Decimal("1234567"), 3333)
        self.assertEqual(result, Decimal("370.4071"))
        self.assertIsInstance(result, Decimal)

    def test_zero_volume_returns_none_not_zero(self):
        # Returning 0 here would poison every close-vs-VWAP comparison
        # downstream, so the honest answer is "no VWAP for this day".
        self.assertIsNone(calculate_daily_vwap(Decimal("1000000"), 0))

    def test_zero_volume_does_not_raise(self):
        try:
            calculate_daily_vwap(Decimal("5000"), 0)
        except ZeroDivisionError:
            self.fail("zero volume must not raise ZeroDivisionError")

    def test_null_turnover_returns_none(self):
        self.assertIsNone(calculate_daily_vwap(None, 5000))

    def test_both_missing_returns_none(self):
        self.assertIsNone(calculate_daily_vwap(None, None))

    def test_negative_volume_returns_none(self):
        self.assertIsNone(calculate_daily_vwap(Decimal("1000"), -50))

    def test_negative_turnover_returns_none(self):
        self.assertIsNone(calculate_daily_vwap(Decimal("-1000"), 50))

    def test_string_inputs_are_coerced(self):
        # Crawled values arrive as comma-formatted strings.
        self.assertEqual(
            calculate_daily_vwap("1,000,000", "5,000"),
            Decimal("200.0000"),
        )

    def test_garbage_input_returns_none(self):
        self.assertIsNone(calculate_daily_vwap("not-a-number", 100))


class PeriodVWAPTests(TestCase):
    """The 30-day aggregate is a SEPARATE metric from the daily VWAP."""

    def test_aggregate_is_sum_turnover_over_sum_volume(self):
        rows = [
            FakePrice("d1", volume=100, turnover=Decimal("20000")),   # 200/unit
            FakePrice("d2", volume=300, turnover=Decimal("120000")),  # 400/unit
        ]
        # 140000 / 400 = 350 -- volume weighted, NOT the mean of 200 and 400.
        self.assertEqual(calculate_period_vwap(rows), Decimal("350.0000"))

    def test_aggregate_differs_from_daily_vwap(self):
        rows = [
            FakePrice("d1", volume=100, turnover=Decimal("20000")),
            FakePrice("d2", volume=300, turnover=Decimal("120000")),
        ]
        aggregate = calculate_period_vwap(rows)
        daily = calculate_daily_vwap(Decimal("120000"), 300)

        self.assertNotEqual(aggregate, daily)
        self.assertEqual(daily, Decimal("400.0000"))

    def test_zero_volume_rows_are_skipped(self):
        rows = [
            FakePrice("d1", volume=0, turnover=Decimal("0")),
            FakePrice("d2", volume=100, turnover=Decimal("25000")),
        ]
        self.assertEqual(calculate_period_vwap(rows), Decimal("250.0000"))

    def test_all_zero_volume_returns_none(self):
        rows = [FakePrice("d1", volume=0, turnover=Decimal("0"))]
        self.assertIsNone(calculate_period_vwap(rows))


class VWAPInAnalysisRowsTests(TestCase):

    def test_vwap_is_calculated_per_day_not_aggregated(self):
        from datetime import date

        rows = build_analysis_rows([
            FakePrice(date(2026, 9, 1), close=Decimal("200"),
                      volume=100, turnover=Decimal("20000")),
            FakePrice(date(2026, 9, 2), close=Decimal("400"),
                      volume=300, turnover=Decimal("120000")),
        ])

        # Each day keeps its own VWAP; the second day is not dragged
        # toward the first by aggregation.
        self.assertEqual(rows[0]["vwap"], Decimal("200.0000"))
        self.assertEqual(rows[1]["vwap"], Decimal("400.0000"))

    def test_zero_volume_day_gets_null_vwap_and_does_not_crash(self):
        from datetime import date

        rows = build_analysis_rows([
            FakePrice(date(2026, 9, 1), close=Decimal("100"),
                      volume=0, turnover=Decimal("0")),
        ])

        self.assertIsNone(rows[0]["vwap"])

    def test_missing_turnover_day_gets_null_vwap(self):
        from datetime import date

        rows = build_analysis_rows([
            FakePrice(date(2026, 9, 1), close=Decimal("100"),
                      volume=500, turnover=None),
        ])

        self.assertIsNone(rows[0]["vwap"])
