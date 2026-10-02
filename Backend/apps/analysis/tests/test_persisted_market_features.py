from datetime import date, timedelta
from unittest import TestCase

from apps.analysis.services.volume_anomaly import detect_volume_anomalies
from apps.analysis.services.news_price_correlation import calculate_news_price_correlations


class VolumeAnomalyTests(TestCase):
    def test_spike_uses_only_full_preceding_window_and_records_reason(self):
        start = date(2025, 1, 1)
        rows = [(start + timedelta(days=i), 100) for i in range(20)]
        rows.append((start + timedelta(days=20), 250))
        result = detect_volume_anomalies(rows)

        self.assertTrue(all(row["insufficient_data"] for row in result[:20]))
        self.assertFalse(any(row["is_anomaly"] for row in result[:20]))
        self.assertTrue(result[-1]["is_anomaly"])
        self.assertEqual(result[-1]["reason"], "multiplier")
        self.assertIsNone(result[-1]["z_score"])

    def test_only_the_multiplier_rule_flags(self):
        # A spike that is many standard deviations out but under 2.5x the mean is not flagged:
        # detect_volume_anomalies implements the multiplier rule only.
        start = date(2025, 2, 1)
        baseline = [90 + (i % 5) * 5 for i in range(20)]
        below = detect_volume_anomalies([(start + timedelta(days=i), v) for i, v in enumerate(baseline + [140])])[-1]
        above = detect_volume_anomalies([(start + timedelta(days=i), v) for i, v in enumerate(baseline + [500])])[-1]
        self.assertGreater(below["z_score"], 3)
        self.assertFalse(below["is_anomaly"])
        self.assertEqual(below["reason"], "")
        self.assertTrue(above["is_anomaly"])
        self.assertEqual(above["reason"], "multiplier")


class NewsPriceCorrelationTests(TestCase):
    def make_prices(self, size):
        start = date(2025, 3, 1)
        return [{"date": start + timedelta(days=i), "close": 100 + i, "volume": 1000 + i * 10} for i in range(size)]

    def test_reports_both_correlations_p_values_and_reliability_per_lag(self):
        prices = self.make_prices(10)
        news = [{"date": row["date"], "confidence": (i + 1) / 10} for i, row in enumerate(prices)]
        result = calculate_news_price_correlations(prices, news, 7)
        self.assertEqual(result["company_id"], 7)
        for lag, expected_n in (("1d", 9), ("2d", 8)):
            values = result["by_lag"][lag]
            self.assertEqual(len(values), 3)
            for correlation in values.values():
                self.assertEqual(correlation["n"], expected_n)
                self.assertIsNotNone(correlation["pearson_r"])
                self.assertIsNotNone(correlation["pearson_p"])
                self.assertIsNotNone(correlation["spearman_rho"])
                self.assertIsNotNone(correlation["spearman_p"])
                self.assertTrue(correlation["reliable"])

    def test_small_panel_is_returned_as_unreliable(self):
        prices = self.make_prices(3)
        result = calculate_news_price_correlations(prices, [], 9)
        correlation = result["by_lag"]["2d"]["news_intensity_vs_signed_return"]
        self.assertEqual(correlation["n"], 1)
        self.assertFalse(correlation["reliable"])
        self.assertIsNone(correlation["pearson_r"])
