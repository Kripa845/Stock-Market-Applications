from datetime import date, timedelta
from decimal import Decimal

from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.companies.models import Company, TrackedCompany
from apps.market_data.models import DailyPrice
from apps.market_data.services.trading_days import is_trading_weekday
from apps.market_intelligence.models import SupportResistanceSet
from apps.market_intelligence.services.support_resistance import (
    Bar,
    Params,
    adjust_history,
    cluster_levels,
    compute_levels,
    compute_support_resistance,
    find_pivots,
)
from apps.users.models import User


def trading_days(count, start=date(2025, 1, 6)):
    days, day = [], start
    while len(days) < count:
        if is_trading_weekday(day):
            days.append(day)
        day += timedelta(days=1)
    return days


def bars_from_closes(closes, start=date(2025, 1, 6), spread=1.0, volume=1000.0):
    """Bars whose high / low sit ``spread`` either side of the close (open = close)."""
    return [
        Bar(date=day, open=c, high=c + spread, low=c - spread, close=c, volume=volume)
        for day, c in zip(trading_days(len(closes), start), closes)
    ]


def zigzag_closes(top, bottom, legs, leg_length=8):
    """Price oscillating between ``top`` and ``bottom``: each swing is a clear 5-bar pivot."""
    closes = []
    for leg in range(legs):
        a, b = (bottom, top) if leg % 2 == 0 else (top, bottom)
        for k in range(leg_length):
            closes.append(a + (b - a) * k / leg_length)
    closes.append(closes[-1])
    return closes


class PivotTests(SimpleTestCase):
    def test_finds_swing_highs_and_lows(self):
        bars = bars_from_closes(zigzag_closes(120, 100, legs=6))
        pivots = find_pivots(bars, Params())
        highs = {round(p.price) for p in pivots if p.kind == "high"}
        lows = {round(p.price) for p in pivots if p.kind == "low"}
        self.assertEqual(highs, {121})        # top close + spread
        self.assertEqual(lows, {99})          # bottom close - spread

    def test_circuit_day_pivot_is_dropped(self):
        closes = [100.0] * 6 + [101, 102, 103, 104] + [114.5] + [104, 103, 102, 101, 100] + [100.0] * 6
        bars = bars_from_closes(closes)
        # The 114.5 bar is a +10% limit-up close: trading stopped there, price was not rejected.
        self.assertFalse([p for p in find_pivots(bars, Params()) if p.kind == "high"])
        loose = Params(circuit_pct=50)
        self.assertTrue([p for p in find_pivots(bars, loose) if p.kind == "high"])

    def test_zero_range_bar_is_not_a_pivot(self):
        closes = [100.0] * 5 + [101, 102, 103, 104, 110, 104, 103, 102, 101] + [100.0] * 5
        bars = bars_from_closes(closes)
        peak = bars[9]
        bars[9] = Bar(peak.date, 110, 110, 110, 110, peak.volume)
        self.assertFalse([p for p in find_pivots(bars, Params()) if p.kind == "high"])


class ClusterTests(SimpleTestCase):
    def test_levels_need_two_touches_and_are_labelled_against_the_close(self):
        bars = bars_from_closes(zigzag_closes(120, 100, legs=6))
        levels = cluster_levels(find_pivots(bars, Params()), latest_close=110, params=Params())
        by_kind = {level.kind: level for level in levels}
        self.assertEqual(set(by_kind), {"support", "resistance"})
        self.assertAlmostEqual(by_kind["resistance"].price, 121, places=4)
        self.assertAlmostEqual(by_kind["support"].price, 99, places=4)
        self.assertGreaterEqual(by_kind["resistance"].touches, 2)

    def test_single_touch_is_not_a_level(self):
        closes = [100.0] * 6 + [102, 104, 106, 108, 110, 108, 106, 104, 102] + [100.0] * 6
        levels = cluster_levels(find_pivots(bars_from_closes(closes), Params()), 100, Params())
        self.assertFalse([lv for lv in levels if lv.kind == "resistance"])

    def test_nearby_pivots_merge_within_tolerance(self):
        # Tops alternate 120 / 121.2 (1% apart): one resistance level, not two.
        closes = []
        for leg in range(8):
            top = 120 if leg % 4 == 0 else 121.2
            a, b = (100, top) if leg % 2 == 0 else (top, 100)
            closes.extend(a + (b - a) * k / 8 for k in range(8))
        levels = cluster_levels(find_pivots(bars_from_closes(closes), Params()), 110, Params())
        resistance = [lv for lv in levels if lv.kind == "resistance"]
        self.assertEqual(len(resistance), 1)
        self.assertGreater(resistance[0].price, 121)
        self.assertLess(resistance[0].price, 122.2)

    def test_recent_touches_weigh_more(self):
        old = Params(half_life_sessions=10)
        bars = bars_from_closes(zigzag_closes(120, 100, legs=10))
        pivots = find_pivots(bars, old)
        newest = max(pivots, key=lambda p: p.index)
        oldest = min(pivots, key=lambda p: p.index)
        self.assertGreater(newest.weight, oldest.weight)


class AdjustmentTests(SimpleTestCase):
    def test_bonus_adjustment_scales_earlier_bars(self):
        bars = bars_from_closes([200.0] * 5 + [100.0] * 5)
        # Raw move -50%, but against the exchange's adjusted previous close the price was flat:
        # a 100% bonus. Earlier bars are halved.
        bars[5].source_change_pct = 0.0
        adjusted, adjustments, cut = adjust_history(bars, set())
        self.assertIsNone(cut)
        self.assertEqual(len(adjustments), 1)
        self.assertAlmostEqual(adjustments[0]["factor"], 0.5)
        self.assertAlmostEqual(adjusted[0].close, 100.0)
        self.assertAlmostEqual(adjusted[0].volume, 2000.0)
        self.assertAlmostEqual(bars[0].close, 200.0)          # the input is not mutated

    def test_rounding_differences_are_not_adjustments(self):
        bars = bars_from_closes([100.0, 101.0])
        bars[1].source_change_pct = 1.03
        _, adjustments, cut = adjust_history(bars, set())
        self.assertEqual((adjustments, cut), ([], None))

    def test_flagged_session_without_factor_cuts_history(self):
        bars = bars_from_closes([100.0] * 5 + [80.0] * 5)
        adjusted, adjustments, cut = adjust_history(bars, {bars[5].date})
        self.assertEqual(cut, bars[5].date)
        self.assertEqual(len(adjusted), 5)
        self.assertEqual(adjustments, [])


class ComputeLevelsTests(SimpleTestCase):
    def test_too_little_history(self):
        result = compute_levels(bars_from_closes([100.0] * 30), set())
        self.assertEqual(result.status, "insufficient_history")
        self.assertEqual(result.levels, [])

    def test_ok_with_levels(self):
        result = compute_levels(bars_from_closes(zigzag_closes(120, 100, legs=10)), set())
        self.assertEqual(result.status, "ok")
        self.assertTrue(result.levels)
        self.assertEqual(result.sessions_used, 81)

    def test_flat_series_has_no_levels(self):
        result = compute_levels(bars_from_closes([100.0] * 80), set())
        self.assertEqual(result.status, "no_levels")


class SupportResistanceDbTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(symbol="SRCO", name="SR Co", sector="Banking")
        TrackedCompany.objects.create(company=self.company, is_tracked=True)
        closes = zigzag_closes(120, 100, legs=10)
        for index, (day, close) in enumerate(zip(trading_days(len(closes)), closes)):
            close = Decimal(str(round(close, 2)))
            DailyPrice.objects.create(
                company=self.company, source="crawled", date=day,
                open=close, high=close + 1, low=close - 1, close=close,
                volume=1000 + index, turnover=Decimal(1000),
            )
        self.user = User.objects.create_user(
            username="sr-admin", email="sr-admin@example.test",
            password="unused-test-password", role=User.Role.ADMIN,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url = f"/api/market-intelligence/companies/{self.company.pk}/support-resistance/"

    def test_api_404_before_computation(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["status"], "not_computed")

    def test_compute_stores_levels_and_api_returns_them(self):
        summary = compute_support_resistance()
        self.assertEqual(summary["ok"], 1)
        sr_set = SupportResistanceSet.objects.get(company=self.company)
        self.assertEqual(sr_set.status, "ok")
        self.assertEqual(sr_set.params["tolerance_pct"], 1.5)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        kinds = {level["kind"] for level in response.data["levels"]}
        self.assertEqual(kinds, {"support", "resistance"})
        self.assertTrue(all(level["touches"] >= 2 for level in response.data["levels"]))

    def test_recompute_replaces_levels(self):
        compute_support_resistance()
        first = SupportResistanceSet.objects.get(company=self.company).levels.count()
        compute_support_resistance()
        sr_set = SupportResistanceSet.objects.get(company=self.company)
        self.assertEqual(sr_set.levels.count(), first)
        self.assertEqual(SupportResistanceSet.objects.count(), 1)
