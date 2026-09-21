"""
OHLCV pressure proxy (method: OHLCV_PRICE_VOLUME).

    score = 50*D + vwap_weight*V + 20*D*C
    D = price direction, V = close vs daily VWAP, C = volume conviction
    vwap_weight = 30, halved to 15 when D == 0
    |score| >= 25 -> buying / selling, otherwise neutral
"""

from decimal import Decimal

from django.test import TestCase

from apps.analysis.services.daily_metrics import (
    PRESSURE_METHOD,
    calculate_pressure,
)


class PressureDirectionTests(TestCase):

    def test_price_up_high_volume(self):
        # D=+1, V=+1 (close 110 > vwap 105), C=1.0 (ratio 2.0 >= 1.5)
        # 50 + 30 + 20 = 100
        result = calculate_pressure(
            close=Decimal("110"),
            previous_close=Decimal("100"),
            vwap=Decimal("105"),
            volume_ratio=Decimal("2.0"),
        )

        self.assertEqual(result["pressure"], "buying")
        self.assertEqual(result["pressure_score"], Decimal("100.00"))
        self.assertEqual(result["pressure_method"], PRESSURE_METHOD)

    def test_price_up_low_volume(self):
        # D=+1, V=+1, C=0 (ratio 0.5 <= 1.0) -> 50 + 30 + 0 = 80
        result = calculate_pressure(
            close=Decimal("110"),
            previous_close=Decimal("100"),
            vwap=Decimal("105"),
            volume_ratio=Decimal("0.5"),
        )

        self.assertEqual(result["pressure"], "buying")
        self.assertEqual(result["pressure_score"], Decimal("80.00"))

    def test_price_down_high_volume(self):
        # D=-1, V=-1, C=1.0 -> -50 - 30 - 20 = -100
        result = calculate_pressure(
            close=Decimal("90"),
            previous_close=Decimal("100"),
            vwap=Decimal("95"),
            volume_ratio=Decimal("2.0"),
        )

        self.assertEqual(result["pressure"], "selling")
        self.assertEqual(result["pressure_score"], Decimal("-100.00"))

    def test_price_down_low_volume(self):
        # D=-1, V=-1, C=0 -> -80
        result = calculate_pressure(
            close=Decimal("90"),
            previous_close=Decimal("100"),
            vwap=Decimal("95"),
            volume_ratio=Decimal("0.5"),
        )

        self.assertEqual(result["pressure"], "selling")
        self.assertEqual(result["pressure_score"], Decimal("-80.00"))

    def test_high_volume_strengthens_the_same_direction(self):
        weak = calculate_pressure(
            Decimal("110"), Decimal("100"), Decimal("105"), Decimal("1.0"),
        )
        strong = calculate_pressure(
            Decimal("110"), Decimal("100"), Decimal("105"), Decimal("1.5"),
        )

        self.assertGreater(
            strong["pressure_score"],
            weak["pressure_score"],
        )

    def test_price_unchanged_is_neutral(self):
        # D=0 -> vwap term is halved to 15, below the 25 band.
        result = calculate_pressure(
            close=Decimal("100"),
            previous_close=Decimal("100"),
            vwap=Decimal("95"),
            volume_ratio=Decimal("2.0"),
        )

        self.assertEqual(result["pressure"], "neutral")
        self.assertEqual(result["pressure_score"], Decimal("15.00"))

    def test_price_unchanged_and_at_vwap_scores_zero(self):
        result = calculate_pressure(
            close=Decimal("100"),
            previous_close=Decimal("100"),
            vwap=Decimal("100"),
            volume_ratio=Decimal("1.0"),
        )

        self.assertEqual(result["pressure_score"], Decimal("0.00"))
        self.assertEqual(result["pressure"], "neutral")

    def test_conflicting_signals_land_near_neutral(self):
        # Price up but closing BELOW vwap on no extra volume: 50 - 30 = 20,
        # inside the +/-25 band, so it is reported as neutral rather than
        # being forced into a direction.
        result = calculate_pressure(
            close=Decimal("101"),
            previous_close=Decimal("100"),
            vwap=Decimal("105"),
            volume_ratio=Decimal("1.0"),
        )

        self.assertEqual(result["pressure_score"], Decimal("20.00"))
        self.assertEqual(result["pressure"], "neutral")


class PressureMissingInputTests(TestCase):

    def test_missing_previous_close(self):
        result = calculate_pressure(
            close=Decimal("110"),
            previous_close=None,
            vwap=Decimal("105"),
            volume_ratio=Decimal("2.0"),
        )

        # D=0 so the vwap term is halved: 15 -> neutral.
        self.assertEqual(result["pressure_score"], Decimal("15.00"))
        self.assertEqual(result["pressure"], "neutral")
        self.assertIn("previous_close", result["missing_inputs"])
        self.assertFalse(result["is_complete"])

    def test_missing_vwap(self):
        # D=+1, V=0, C=1.0 -> 50 + 0 + 20 = 70
        result = calculate_pressure(
            close=Decimal("110"),
            previous_close=Decimal("100"),
            vwap=None,
            volume_ratio=Decimal("2.0"),
        )

        self.assertEqual(result["pressure_score"], Decimal("70.00"))
        self.assertEqual(result["pressure"], "buying")
        self.assertIn("vwap", result["missing_inputs"])

    def test_missing_volume_ratio_insufficient_history(self):
        # D=+1, V=+1, C=0 -> 80
        result = calculate_pressure(
            close=Decimal("110"),
            previous_close=Decimal("100"),
            vwap=Decimal("105"),
            volume_ratio=None,
        )

        self.assertEqual(result["pressure_score"], Decimal("80.00"))
        self.assertIn("volume_ratio", result["missing_inputs"])

    def test_all_inputs_missing_scores_zero(self):
        result = calculate_pressure(
            close=Decimal("100"),
            previous_close=None,
            vwap=None,
            volume_ratio=None,
        )

        self.assertEqual(result["pressure_score"], Decimal("0.00"))
        self.assertEqual(result["pressure"], "neutral")
        self.assertEqual(len(result["missing_inputs"]), 3)

    def test_zero_volume_day_has_no_vwap_and_does_not_crash(self):
        # A zero-volume day yields vwap=None upstream; pressure must
        # still produce a usable answer.
        result = calculate_pressure(
            close=Decimal("100"),
            previous_close=Decimal("100"),
            vwap=None,
            volume_ratio=Decimal("0"),
        )

        self.assertEqual(result["pressure"], "neutral")
        self.assertEqual(result["pressure_score"], Decimal("0.00"))

    def test_zero_vwap_treated_as_unavailable(self):
        result = calculate_pressure(
            close=Decimal("100"),
            previous_close=Decimal("100"),
            vwap=Decimal("0"),
            volume_ratio=Decimal("1.0"),
        )

        self.assertIn("vwap", result["missing_inputs"])


class PressureContractTests(TestCase):

    def test_score_never_exceeds_the_declared_range(self):
        extreme = calculate_pressure(
            close=Decimal("500"),
            previous_close=Decimal("1"),
            vwap=Decimal("2"),
            volume_ratio=Decimal("9999"),
        )

        self.assertLessEqual(extreme["pressure_score"], Decimal("100"))
        self.assertGreaterEqual(extreme["pressure_score"], Decimal("-100"))

    def test_method_identifier_is_stamped(self):
        result = calculate_pressure(
            Decimal("110"), Decimal("100"), Decimal("105"), Decimal("2.0"),
        )
        self.assertEqual(result["pressure_method"], "OHLCV_PRICE_VOLUME")

    def test_components_are_returned_for_the_frontend(self):
        result = calculate_pressure(
            Decimal("110"), Decimal("100"), Decimal("105"), Decimal("2.0"),
        )

        components = result["components"]
        self.assertEqual(components["price_direction"], 1)
        self.assertEqual(components["vwap_position"], 1)
        self.assertEqual(components["volume_conviction"], Decimal("1.00"))

    def test_deterministic_across_repeated_calls(self):
        args = (Decimal("110"), Decimal("100"), Decimal("105"), Decimal("1.3"))
        self.assertEqual(
            calculate_pressure(*args),
            calculate_pressure(*args),
        )

    def test_conviction_scales_linearly_between_1_0_and_1_5(self):
        midpoint = calculate_pressure(
            close=Decimal("110"),
            previous_close=Decimal("100"),
            vwap=Decimal("105"),
            volume_ratio=Decimal("1.25"),
        )
        # C = (1.25 - 1.0) / 0.5 = 0.5 -> 50 + 30 + 10 = 90
        self.assertEqual(midpoint["pressure_score"], Decimal("90.00"))
