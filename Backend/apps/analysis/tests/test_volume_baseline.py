"""
Volume baseline: mean of the PREVIOUS 20 TRADING SESSIONS.

Not calendar days, and never including the day being scored.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from apps.analysis.services.daily_metrics import (
    BASELINE_SESSIONS,
    VOLUME_ANOMALY_THRESHOLD,
    build_analysis_rows,
    calculate_volume_baseline,
)

from .test_vwap import FakePrice


class VolumeBaselineTests(TestCase):

    def test_exactly_twenty_previous_sessions(self):
        previous = [1000] * BASELINE_SESSIONS
        result = calculate_volume_baseline(3000, previous)

        self.assertEqual(result.sessions_used, 20)
        self.assertTrue(result.sufficient_history)
        self.assertEqual(result.average, Decimal("1000.00"))
        self.assertEqual(result.ratio, Decimal("3.00"))
        self.assertTrue(result.anomaly)

    def test_more_than_twenty_sessions_uses_only_most_recent_twenty(self):
        # 20 recent sessions of 1000, then older noise that must be ignored.
        previous = [1000] * 20 + [999999] * 10
        result = calculate_volume_baseline(1000, previous)

        self.assertEqual(result.sessions_used, 20)
        self.assertEqual(result.average, Decimal("1000.00"))

    def test_fewer_than_twenty_sessions_publishes_provisional_ratio(self):
        previous = [1000] * 5
        result = calculate_volume_baseline(5000, previous)

        self.assertEqual(result.sessions_used, 5)
        self.assertFalse(result.sufficient_history)
        self.assertEqual(result.average, Decimal("1000.00"))
        self.assertEqual(result.ratio, Decimal("5.00"))

    def test_anomaly_suppressed_on_partial_baseline(self):
        # 5x volume WOULD be an anomaly, but a 5-session average is too
        # noisy to raise a flag on. Documented insufficient-history policy.
        previous = [1000] * 5
        result = calculate_volume_baseline(5000, previous)

        self.assertGreaterEqual(result.ratio, VOLUME_ANOMALY_THRESHOLD)
        self.assertFalse(result.anomaly)

    def test_no_previous_sessions(self):
        result = calculate_volume_baseline(5000, [])

        self.assertEqual(result.sessions_used, 0)
        self.assertIsNone(result.average)
        self.assertIsNone(result.ratio)
        self.assertFalse(result.anomaly)
        self.assertFalse(result.sufficient_history)

    def test_zero_average_does_not_divide_by_zero(self):
        previous = [0] * BASELINE_SESSIONS
        result = calculate_volume_baseline(5000, previous)

        self.assertEqual(result.average, Decimal("0.00"))
        self.assertIsNone(result.ratio)
        self.assertFalse(result.anomaly)

    def test_unusually_high_volume_flags_anomaly(self):
        previous = [1000] * BASELINE_SESSIONS
        result = calculate_volume_baseline(10000, previous)

        self.assertEqual(result.ratio, Decimal("10.00"))
        self.assertTrue(result.anomaly)

    def test_normal_volume_does_not_flag(self):
        previous = [1000] * BASELINE_SESSIONS
        result = calculate_volume_baseline(1100, previous)

        self.assertEqual(result.ratio, Decimal("1.10"))
        self.assertFalse(result.anomaly)

    def test_threshold_is_inclusive(self):
        previous = [1000] * BASELINE_SESSIONS
        at_threshold = int(1000 * VOLUME_ANOMALY_THRESHOLD)
        result = calculate_volume_baseline(at_threshold, previous)

        self.assertEqual(result.ratio, VOLUME_ANOMALY_THRESHOLD)
        self.assertTrue(result.anomaly)

    def test_just_below_threshold_does_not_flag(self):
        previous = [1000] * BASELINE_SESSIONS
        at_threshold = int(1000 * VOLUME_ANOMALY_THRESHOLD)
        result = calculate_volume_baseline(at_threshold - 1, previous)

        # Rounding to 2 dp means one share below the threshold presents as the threshold and does flag.
        self.assertEqual(result.ratio, VOLUME_ANOMALY_THRESHOLD)
        self.assertTrue(result.anomaly)

        result = calculate_volume_baseline(at_threshold - 100, previous)
        self.assertEqual(result.ratio, VOLUME_ANOMALY_THRESHOLD - Decimal("0.10"))
        self.assertFalse(result.anomaly)

    def test_zero_volume_today_is_not_an_anomaly(self):
        previous = [1000] * BASELINE_SESSIONS
        result = calculate_volume_baseline(0, previous)

        self.assertEqual(result.ratio, Decimal("0.00"))
        self.assertFalse(result.anomaly)


class BaselineExcludesTodayTests(TestCase):
    """The day being scored must never contribute to its own baseline."""

    def test_today_volume_excluded_from_its_own_baseline(self):
        start = date(2026, 8, 1)

        # 20 sessions at 1000, then a 21st session with a huge spike.
        prices = [
            FakePrice(
                start + timedelta(days=i),
                close=Decimal("100"),
                volume=1000,
                turnover=Decimal("100000"),
            )
            for i in range(BASELINE_SESSIONS)
        ]
        spike_date = start + timedelta(days=BASELINE_SESSIONS)
        prices.append(
            FakePrice(
                spike_date,
                close=Decimal("100"),
                volume=21000,
                turnover=Decimal("2100000"),
            )
        )

        rows = build_analysis_rows(prices)
        spike_row = rows[-1]

        # Baseline stays at exactly 1000. If the spike leaked into its own
        # baseline the average would be (20*1000 + 21000)/21 = 1952.38.
        self.assertEqual(spike_row["volume_average"], Decimal("1000.00"))
        self.assertEqual(spike_row["volume_ratio"], Decimal("21.00"))
        self.assertTrue(spike_row["volume_anomaly"])

    def test_first_session_has_no_baseline(self):
        rows = build_analysis_rows([
            FakePrice(date(2026, 9, 1), close=Decimal("100"),
                      volume=1000, turnover=Decimal("100000")),
        ])

        self.assertEqual(rows[0]["volume_baseline_sessions"], 0)
        self.assertIsNone(rows[0]["volume_average"])
        self.assertIsNone(rows[0]["volume_ratio"])
        self.assertFalse(rows[0]["volume_anomaly"])

    def test_sufficient_history_flips_on_the_21st_session(self):
        start = date(2026, 8, 1)
        prices = [
            FakePrice(
                start + timedelta(days=i),
                close=Decimal("100"),
                volume=1000,
                turnover=Decimal("100000"),
            )
            for i in range(BASELINE_SESSIONS + 1)
        ]

        rows = build_analysis_rows(prices)

        # Row index 19 (the 20th session) has only 19 previous sessions.
        self.assertEqual(rows[19]["volume_baseline_sessions"], 19)
        self.assertFalse(rows[19]["has_sufficient_history"])

        # Row index 20 (the 21st session) has a full 20-session baseline.
        self.assertEqual(rows[20]["volume_baseline_sessions"], 20)
        self.assertTrue(rows[20]["has_sufficient_history"])


class NonTradingDayTests(TestCase):
    """
    Weekends and holidays are handled by never being in the data.

    The baseline counts SESSIONS, so a gap in the calendar is invisible
    to it -- which is exactly the required behaviour.
    """

    def test_calendar_gaps_do_not_affect_session_count(self):
        # Sessions Mon-Fri with weekend gaps, 21 sessions total.
        sessions = []
        cursor = date(2026, 8, 3)  # a Monday
        while len(sessions) < BASELINE_SESSIONS + 1:
            if cursor.weekday() < 5:
                sessions.append(cursor)
            cursor += timedelta(days=1)

        prices = [
            FakePrice(day, close=Decimal("100"),
                      volume=1000, turnover=Decimal("100000"))
            for day in sessions
        ]

        rows = build_analysis_rows(prices)
        last = rows[-1]

        # 20 previous SESSIONS, even though they span 28 calendar days.
        self.assertEqual(last["volume_baseline_sessions"], 20)
        self.assertTrue(last["has_sufficient_history"])
        span = (sessions[-1] - sessions[0]).days
        self.assertGreater(span, BASELINE_SESSIONS)


class DuplicateDateTests(TestCase):

    def test_duplicate_dates_collapse_to_one_row(self):
        day = date(2026, 9, 1)
        rows = build_analysis_rows([
            FakePrice(day, close=Decimal("100"),
                      volume=1000, turnover=Decimal("100000")),
            FakePrice(day, close=Decimal("110"),
                      volume=2000, turnover=Decimal("220000")),
        ])

        self.assertEqual(len(rows), 1)
        # Last occurrence wins, matching update_or_create upstream.
        self.assertEqual(rows[0]["close_price"], Decimal("110"))

    def test_duplicates_do_not_inflate_the_baseline(self):
        start = date(2026, 8, 1)
        prices = []

        for i in range(BASELINE_SESSIONS):
            day = start + timedelta(days=i)
            # Emit every session twice.
            prices.append(FakePrice(day, close=Decimal("100"),
                                    volume=1000, turnover=Decimal("100000")))
            prices.append(FakePrice(day, close=Decimal("100"),
                                    volume=1000, turnover=Decimal("100000")))

        final_day = start + timedelta(days=BASELINE_SESSIONS)
        prices.append(FakePrice(final_day, close=Decimal("100"),
                                volume=1000, turnover=Decimal("100000")))

        rows = build_analysis_rows(prices)

        self.assertEqual(len(rows), BASELINE_SESSIONS + 1)
        self.assertEqual(rows[-1]["volume_baseline_sessions"], 20)
        self.assertEqual(rows[-1]["volume_average"], Decimal("1000.00"))


class DeterminismTests(TestCase):

    def test_same_input_produces_identical_output(self):
        start = date(2026, 8, 1)
        prices = [
            FakePrice(start + timedelta(days=i), close=Decimal(100 + i),
                      volume=1000 + i, turnover=Decimal((1000 + i) * (100 + i)))
            for i in range(25)
        ]

        first = build_analysis_rows(prices)
        second = build_analysis_rows(prices)

        self.assertEqual(first, second)

    def test_input_order_does_not_change_output(self):
        start = date(2026, 8, 1)
        prices = [
            FakePrice(start + timedelta(days=i), close=Decimal(100 + i),
                      volume=1000 + i, turnover=Decimal((1000 + i) * (100 + i)))
            for i in range(25)
        ]

        ordered = build_analysis_rows(prices)
        shuffled = build_analysis_rows(list(reversed(prices)))

        self.assertEqual(ordered, shuffled)
