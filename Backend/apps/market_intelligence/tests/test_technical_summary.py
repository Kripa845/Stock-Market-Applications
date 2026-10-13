"""Tests for services.technical_summary: signal rules, short history and corporate-action handling."""

from datetime import date, timedelta
from decimal import Decimal

from django.test import SimpleTestCase

from apps.market_intelligence.services import technical_summary as ts


def bars(closes, spread=1, source_pcts=None):
    start = date(2025, 1, 1)
    out = []
    for i, close in enumerate(closes):
        out.append({
            "date": start + timedelta(days=i), "open": close, "high": close + spread, "low": close - spread,
            "close": close, "source_change_pct": None if source_pcts is None else source_pcts[i],
        })
    return out


def by_key(result):
    return {item["key"]: item for item in result["indicators"]}


class SignalRuleTests(SimpleTestCase):

    def test_level_signal(self):
        self.assertEqual(ts.level_signal(25, 30, 70), ts.BUY)
        self.assertEqual(ts.level_signal(75, 30, 70), ts.SELL)
        self.assertEqual(ts.level_signal(30, 30, 70), ts.NEUTRAL)       # boundary is neutral
        self.assertIsNone(ts.level_signal(None, 30, 70))

    def test_above_below_signal(self):
        self.assertEqual(ts.above_below_signal(105, 100), ts.BUY)
        self.assertEqual(ts.above_below_signal(95, 100), ts.SELL)
        self.assertEqual(ts.above_below_signal(100, 100), ts.NEUTRAL)
        self.assertIsNone(ts.above_below_signal(100, None))

    def test_band_signal(self):
        self.assertEqual(ts.band_signal(89, 90, 110), ts.BUY)
        self.assertEqual(ts.band_signal(111, 90, 110), ts.SELL)
        self.assertEqual(ts.band_signal(100, 90, 110), ts.NEUTRAL)
        self.assertIsNone(ts.band_signal(100, None, 110))

    def test_overall_signal_thresholds(self):
        self.assertEqual(ts.overall_signal(buy=5, sell=0, neutral=5), "Strong Buy")   # +0.5
        self.assertEqual(ts.overall_signal(buy=3, sell=2, neutral=5), ts.BUY)         # +0.1
        self.assertEqual(ts.overall_signal(buy=1, sell=1, neutral=8), ts.NEUTRAL)
        self.assertEqual(ts.overall_signal(buy=2, sell=3, neutral=5), ts.SELL)
        self.assertEqual(ts.overall_signal(buy=0, sell=9, neutral=1), "Strong Sell")
        self.assertIsNone(ts.overall_signal(0, 0, 0))


class TechnicalSummaryTests(SimpleTestCase):

    def test_short_history_is_null_not_a_crash(self):
        result = ts.technical_summary(bars([100, 101, 102, 101, 103]))
        indicators = by_key(result)
        for key in ("rsi_14", "macd", "stoch", "bollinger", "atr_14", "sma_20", "sma_200", "ema_50"):
            self.assertIsNone(indicators[key]["value"], key)
            self.assertIsNone(indicators[key]["signal"], key)
        self.assertEqual(result["summary"], {"buy": 0, "neutral": 0, "sell": 0, "total": 0, "signal": None})
        self.assertIsNotNone(result["pivots"])                       # pivots only need two sessions

    def test_empty_history(self):
        result = ts.technical_summary([])
        self.assertIsNone(result["close"])
        self.assertIsNone(result["pivots"])
        self.assertIsNone(result["summary"]["signal"])

    def test_steady_uptrend(self):
        result = ts.technical_summary(bars([100 + i for i in range(250)]))
        indicators = by_key(result)
        for key in ("sma_20", "sma_50", "sma_200", "ema_20", "ema_50"):
            self.assertEqual(indicators[key]["signal"], ts.BUY, key)   # close above every average
        self.assertEqual(indicators["rsi_14"]["value"], 100)            # no losses at all
        self.assertEqual(indicators["rsi_14"]["signal"], ts.SELL)       # overbought
        self.assertEqual(indicators["atr_14"]["signal"], ts.NEUTRAL)
        self.assertFalse(indicators["atr_14"]["votes"])                 # volatility does not vote
        self.assertEqual(result["summary"]["total"], 9)
        self.assertEqual(result["summary"]["buy"] + result["summary"]["sell"] + result["summary"]["neutral"], 9)

    def test_sma_200_needs_200_sessions(self):
        self.assertIsNone(by_key(ts.technical_summary(bars([100] * 199)))["sma_200"]["value"])
        self.assertEqual(by_key(ts.technical_summary(bars([100] * 200)))["sma_200"]["value"], 100)

    def test_classic_pivots_from_previous_session(self):
        result = ts.technical_summary(bars([100, 110], spread=5))
        h, l, c = 105, 95, 100                                        # the session before the last
        p = (h + l + c) / 3
        self.assertEqual(result["pivots"]["levels"]["p"], round(p, 2))
        self.assertEqual(result["pivots"]["levels"]["r1"], round(2 * p - l, 2))
        self.assertEqual(result["pivots"]["levels"]["s1"], round(2 * p - h, 2))
        self.assertEqual(result["pivots"]["based_on"], date(2025, 1, 1))


class CorporateActionTests(SimpleTestCase):

    def test_bonus_back_adjusts_earlier_prices(self):
        # 100% bonus: price halves, but the exchange's adjusted change is +1%.
        data = bars([100, 100, 50.5], source_pcts=[None, Decimal("0"), Decimal("1")])
        adjusted, cutoff, dates = ts.adjust_for_corporate_actions(data)
        self.assertEqual(cutoff, 0)
        self.assertEqual(dates, [data[2]["date"]])
        self.assertEqual([float(b["close"]) for b in adjusted], [50.0, 50.0, 50.5])
        self.assertEqual(float(adjusted[0]["high"]), 50.5)            # whole bar scaled, not just close
        self.assertEqual(data[0]["close"], 100)                       # input untouched

    def test_ordinary_sessions_are_left_alone(self):
        data = bars([100, 102, 101], source_pcts=[None, Decimal("2"), Decimal("-0.98")])
        adjusted, cutoff, dates = ts.adjust_for_corporate_actions(data)
        self.assertEqual(([float(b["close"]) for b in adjusted], cutoff, dates), ([100, 102, 101], 0, []))

    def test_unexplained_jump_without_source_pct_cuts_history(self):
        data = bars([100, 100, 70, 71])                               # -30%, no adjusted % stored
        adjusted, cutoff, dates = ts.adjust_for_corporate_actions(data)
        self.assertEqual(cutoff, 2)
        self.assertEqual([float(b["close"]) for b in adjusted], [70, 71])
