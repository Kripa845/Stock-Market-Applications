"""Indicator library tests.

Every registry indicator has a ``test_<id>`` method. Most compare against an independent pandas
reference (rolling windows, SMA-seeded ``ewm``, ``numpy.polyfit``) on an 80-row dataset with a
0.01 tolerance, and check that warm-up bars are None exactly where the reference has NaN.
Recursive state machines (PSAR, SuperTrend, Zig Zag, ...) are checked against small hand-worked
cases and their defining rules instead. ``VERIFIED_BY`` records which method applies.
"""

import math
from datetime import date, timedelta

import numpy as np
import pandas as pd
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.companies.models import Company
from apps.market_data.models import DailyPrice, FloorsheetTransaction
from apps.market_intelligence.indicators import REGISTRY, compute, registry_payload, resolve_params
from apps.market_intelligence.indicators import core, custom, market, momentum
from apps.market_intelligence.indicators import moving_averages as ma
from apps.market_intelligence.indicators import price, trend, volatility, volume
from apps.market_intelligence.models import ProxyIndexSnapshot
from apps.users.models import User

TOL = 0.01
ROWS = 80

# Deterministic NEPSE-like daily bars: a wave on a gentle uptrend. Bar 30 has zero volume.
CLOSE = [round(100 + 8 * math.sin(i / 6) + 0.15 * i + ((i % 5) - 2) * 0.4, 2) for i in range(ROWS)]
OPEN = [CLOSE[0]] + [round(CLOSE[i - 1] + ((i % 3) - 1) * 0.3, 2) for i in range(1, ROWS)]
HIGH = [round(max(o, c) + 0.5 + (i % 4) * 0.25, 2) for i, (o, c) in enumerate(zip(OPEN, CLOSE))]
LOW = [round(min(o, c) - 0.4 - (i % 3) * 0.3, 2) for i, (o, c) in enumerate(zip(OPEN, CLOSE))]
VOLUME = [1000 + (i * 137) % 900 for i in range(ROWS)]
VOLUME[30] = 0
DATES = []
_day = date(2025, 1, 5)
while len(DATES) < ROWS:
    if _day.weekday() not in (4, 5):  # NEPSE trades Sunday-Thursday
        DATES.append(_day)
    _day += timedelta(days=1)

C, O, H, L = (pd.Series(x, dtype=float) for x in (CLOSE, OPEN, HIGH, LOW))
V = pd.Series(VOLUME, dtype=float)
DATA = {"open": OPEN, "high": HIGH, "low": LOW, "close": CLOSE, "volume": VOLUME, "date": DATES}


# ── pandas reference helpers ───────────────────────────────────────────────────────────
def seeded(series, n, alpha):
    """SMA-seeded exponential smoothing: replace the first n valid values by their mean, then ewm."""
    s = pd.Series(series, dtype=float).reset_index(drop=True)
    valid = s.dropna()
    out = pd.Series(np.nan, index=s.index)
    if len(valid) < n:
        return out
    head = pd.Series([valid.iloc[:n].mean()], index=[valid.index[n - 1]])
    chain = pd.concat([head, valid.iloc[n:]])
    out.loc[chain.index] = chain.ewm(alpha=alpha, adjust=False).mean()
    return out


def r_ema(s, n):
    return seeded(s, n, 2 / (n + 1))


def r_rma(s, n):
    return seeded(s, n, 1 / n)


def r_wma(s, n):
    w = np.arange(1, n + 1)
    return pd.Series(s, dtype=float).rolling(n).apply(lambda x: np.dot(x, w) / w.sum(), raw=True)


def r_tr():
    return pd.concat([H - L, (H - C.shift()).abs(), (L - C.shift()).abs()], axis=1).max(axis=1, skipna=False)


def r_rsi(s, n):
    d = pd.Series(s, dtype=float).diff()
    g, lo = r_rma(d.clip(lower=0), n), r_rma((-d).clip(lower=0), n)
    return (100 - 100 / (1 + g / lo)).where(lo != 0, 100.0).where(g.notna())


def r_linfit(n):
    x = np.arange(1, n + 1)
    return lambda w: np.polyfit(x, w, 1)


def out(indicator_id, key=None, data=DATA, **params):
    result = compute(indicator_id, data, params)["outputs"]
    return result[key] if key else next(iter(result.values()))


class IndicatorAssertions:
    def assertSeries(self, actual, expected, tol=TOL):
        expected = pd.Series(expected, dtype=float).reset_index(drop=True)
        self.assertEqual(len(actual), len(expected))
        for i, (a, e) in enumerate(zip(actual, expected)):
            if pd.isna(e):
                self.assertIsNone(a, f"bar {i}: expected warm-up None, got {a}")
            else:
                self.assertIsNotNone(a, f"bar {i}: expected {e}, got None")
                self.assertAlmostEqual(a, e, delta=tol, msg=f"bar {i}")


# ── Moving averages ────────────────────────────────────────────────────────────────────
class MovingAverageTests(IndicatorAssertions, SimpleTestCase):
    def test_sma(self):
        self.assertSeries(out("sma"), C.rolling(20).mean())

    def test_ema(self):
        self.assertSeries(out("ema"), r_ema(C, 20))
        self.assertEqual(ma.ema([2, 4, 6, 8, 10], 3), [None, None, 4.0, 6.0, 8.0])  # seed 4, k = 0.5

    def test_wma(self):
        self.assertSeries(out("wma"), r_wma(C, 20))

    def test_dema(self):
        e1 = r_ema(C, 20)
        self.assertSeries(out("dema"), 2 * e1 - r_ema(e1, 20))

    def test_tema(self):
        e1 = r_ema(C, 20)
        e2 = r_ema(e1, 20)
        self.assertSeries(out("tema"), 3 * e1 - 3 * e2 + r_ema(e2, 20))

    def test_hma(self):
        raw = 2 * r_wma(C, 4) - r_wma(C, 9)
        expected = pd.Series(np.nan, index=C.index)
        valid = raw.dropna()
        expected.loc[valid.index] = r_wma(valid.reset_index(drop=True), 3).values
        self.assertSeries(out("hma"), expected)

    def test_smma(self):
        self.assertSeries(out("smma"), r_rma(C, 7))

    def test_vwma(self):
        self.assertSeries(out("vwma"), (C * V).rolling(20).sum() / V.rolling(20).sum())

    def test_mcginley(self):
        # seed (10+10+10)/3 = 10; next = 10 + (12-10) / (0.6*3*(12/10)^4) = 10.53584
        result = ma.mcginley([10, 10, 10, 12], 3)
        self.assertEqual(result[:3], [None, None, 10.0])
        self.assertAlmostEqual(result[3], 10 + 2 / (1.8 * 1.2 ** 4), places=10)
        self.assertEqual(len(out("mcginley")), ROWS)

    def test_alma(self):
        n, m, s = 9, 0.85 * 8, 9 / 6
        w = np.exp(-((np.arange(n) - m) ** 2) / (2 * s * s))
        self.assertSeries(out("alma"), C.rolling(n).apply(lambda x: np.dot(x, w) / w.sum(), raw=True))

    def test_lsma(self):
        fit = r_linfit(25)
        self.assertSeries(out("lsma"), C.rolling(25).apply(lambda w: fit(w)[1] + fit(w)[0] * 25, raw=True))

    def test_linreg_slope(self):
        self.assertSeries(out("linreg_slope"), C.rolling(25).apply(lambda w: r_linfit(25)(w)[0], raw=True))

    def test_kama(self):
        # n=2: seed 1.5; ER=1 so SC=(2/3)^2: 1.5 + 4/9*(3-1.5) = 2.1667; then + 4/9*(4-2.1667) = 2.9815
        result = ma.kama([1, 2, 3, 4], 2, 2, 30)
        self.assertEqual(result[:2], [None, 1.5])
        self.assertAlmostEqual(result[2], 1.5 + 4 / 9 * 1.5, places=10)
        self.assertAlmostEqual(result[3], result[2] + 4 / 9 * (4 - result[2]), places=10)
        flat = ma.kama([5, 5, 5, 5, 5], 2)  # no movement: ER = 0, stays at the seed
        self.assertEqual(flat[1:], [5.0] * 4)

    def test_hamming(self):
        n = 20
        w = 0.54 - 0.46 * np.cos(2 * np.pi * np.arange(n) / (n - 1))
        self.assertSeries(out("hamming"), C.rolling(n).apply(lambda x: np.dot(x, w) / w.sum(), raw=True))

    def test_ma_channel(self):
        self.assertSeries(out("ma_channel", "upper"), H.rolling(20).mean())
        self.assertSeries(out("ma_channel", "lower"), L.rolling(20).mean())

    def test_ma_double(self):
        self.assertSeries(out("ma_double", "ma2"), C.rolling(30).mean())

    def test_ma_triple(self):
        self.assertSeries(out("ma_triple", "ma3"), C.rolling(50).mean())

    def test_ma_multiple(self):
        self.assertSeries(out("ma_multiple", "ma4"), C.rolling(50).mean())
        self.assertTrue(all(v is None for v in out("ma_multiple", "ma6")))  # 200 > 80 rows

    def test_ma_cross(self):
        fast, slow = [1, 1, 3, 1], [2, 2, 2, 2]
        up, down = core.cross_markers(fast, slow)
        self.assertEqual(up, [None, None, 3, None])
        self.assertEqual(down, [None, None, None, 1])
        result = compute("ma_cross", DATA)["outputs"]
        self.assertSeries(result["slow"], C.rolling(21).mean())
        f, s = C.rolling(9).mean(), C.rolling(21).mean()
        expected_up = f.where((f > s) & (f.shift() <= s.shift()))
        self.assertSeries(result["cross_up"], expected_up)

    def test_ema_cross(self):
        result = compute("ema_cross", DATA)["outputs"]
        self.assertSeries(result["fast"], r_ema(C, 9))
        f, s = r_ema(C, 9), r_ema(C, 21)
        self.assertSeries(result["cross_down"], f.where((f < s) & (f.shift() >= s.shift())))

    def test_ma_ema_cross(self):
        result = compute("ma_ema_cross", DATA)["outputs"]
        self.assertSeries(result["fast"], C.rolling(10).mean())
        self.assertSeries(result["slow"], r_ema(C, 10))

    def test_guppy(self):
        result = compute("guppy", DATA)["outputs"]
        self.assertSeries(result["s1"], r_ema(C, 3))
        self.assertSeries(result["l6"], r_ema(C, 60))


# ── Momentum ───────────────────────────────────────────────────────────────────────────
class MomentumTests(IndicatorAssertions, SimpleTestCase):
    def test_macd(self):
        line = r_ema(C, 12) - r_ema(C, 26)
        signal = r_ema(line, 9)
        result = compute("macd", DATA)["outputs"]
        self.assertSeries(result["macd"], line)
        self.assertSeries(result["signal"], signal)
        self.assertSeries(result["histogram"], line - signal)

    def test_rsi(self):
        self.assertSeries(out("rsi"), r_rsi(C, 14))
        # +1, -1, +2 with N=2: seed gain .5 / loss .5 -> 50; then 1.25 / .25 -> 100 - 100/6
        self.assertEqual(momentum.rsi([10, 11, 10, 12], 2), [None, None, 50.0, 100 - 100 / 6])
        self.assertEqual(momentum.rsi([1, 2, 3, 4], 2)[2:], [100.0, 100.0])

    def test_stochastic(self):
        hh, ll = H.rolling(14).max(), L.rolling(14).min()
        k = (C - ll) / (hh - ll) * 100
        result = compute("stochastic", DATA)["outputs"]
        self.assertSeries(result["k"], k)
        self.assertSeries(result["d"], k.rolling(3).mean())

    def test_stoch_rsi(self):
        r = r_rsi(C, 14)
        self.assertSeries(out("stoch_rsi"), (r - r.rolling(14).min()) / (r.rolling(14).max() - r.rolling(14).min()))

    def test_williams_r(self):
        hh, ll = H.rolling(14).max(), L.rolling(14).min()
        self.assertSeries(out("williams_r"), (hh - C) / (hh - ll) * -100)

    def test_cci(self):
        tp = (H + L + C) / 3
        mad = tp.rolling(20).apply(lambda w: np.mean(np.abs(w - w.mean())), raw=True)
        self.assertSeries(out("cci"), (tp - tp.rolling(20).mean()) / (0.015 * mad))

    def test_momentum(self):
        self.assertSeries(out("momentum"), C - C.shift(10))

    def test_roc(self):
        self.assertSeries(out("roc"), (C - C.shift(9)) / C.shift(9) * 100)

    def test_price_oscillator(self):
        f, s = r_ema(C, 12), r_ema(C, 26)
        result = compute("price_oscillator", DATA)["outputs"]
        self.assertSeries(result["po"], f - s)
        self.assertSeries(result["ppo"], (f - s) / s * 100)

    def test_awesome(self):
        med = (H + L) / 2
        self.assertSeries(out("awesome"), med.rolling(5).mean() - med.rolling(34).mean())

    def test_accelerator(self):
        med = (H + L) / 2
        ao = med.rolling(5).mean() - med.rolling(34).mean()
        self.assertSeries(out("accelerator"), ao - ao.rolling(5).mean())

    def test_bop(self):
        self.assertSeries(out("bop"), (C - O) / (H - L))
        self.assertEqual(momentum.balance_of_power([1], [2], [2], [2]), [None])  # H = L

    def test_cmo(self):
        d = C.diff()
        up, down = d.clip(lower=0).rolling(9).sum(), (-d).clip(lower=0).rolling(9).sum()
        self.assertSeries(out("cmo"), 100 * (up - down) / (up + down))

    def test_connors_rsi(self):
        streak, values = [0.0], CLOSE
        for i in range(1, ROWS):
            p = streak[-1]
            streak.append((p + 1 if p > 0 else 1.0) if values[i] > values[i - 1]
                          else (p - 1 if p < 0 else -1.0) if values[i] < values[i - 1] else 0.0)
        ret = C.pct_change() * 100
        rank = pd.Series([np.nan] * ROWS)
        for i in range(21, ROWS):
            rank[i] = 100 * (ret.iloc[i - 20:i] < ret.iloc[i]).sum() / 20
        expected = (r_rsi(C, 3) + r_rsi(streak, 2) + rank) / 3
        self.assertSeries(out("connors_rsi", rank_period=20), expected)
        self.assertEqual(momentum.streak([1, 2, 3, 3, 2, 1]), [0.0, 1.0, 2.0, 0.0, -1.0, -2.0])

    def test_coppock(self):
        roc = lambda n: (C - C.shift(n)) / C.shift(n) * 100  # noqa: E731
        self.assertSeries(out("coppock"), r_wma(roc(14) + roc(11), 10))

    def test_dpo(self):
        self.assertSeries(out("dpo"), C.shift(11) - C.rolling(20).mean())

    def test_fisher(self):
        # Constant median at the range midpoint -> x stays 0 -> Fisher 0.
        result = momentum.fisher([2, 2, 2], [0, 0, 0], 2)
        self.assertEqual(result["fisher"], [None, 0.0, 0.0])
        # Median at the top of the range (bar 1: H = L = 3, range 1-3): x = 0.66*0.5 = 0.33
        top = momentum.fisher([1, 3], [1, 3], 2)
        self.assertAlmostEqual(top["fisher"][1], 0.5 * math.log(1.33 / 0.67), places=10)
        self.assertEqual(top["trigger"][1], 0.0)
        values = out("fisher")
        self.assertTrue(all(v is None for v in values[:8]) and values[8] is not None)

    def test_kst(self):
        roc = lambda n: (C - C.shift(n)) / C.shift(n) * 100  # noqa: E731
        line = (roc(10).rolling(10).mean() + 2 * roc(15).rolling(10).mean()
                + 3 * roc(20).rolling(10).mean() + 4 * roc(30).rolling(15).mean())
        result = compute("kst", DATA)["outputs"]
        self.assertSeries(result["kst"], line)
        self.assertSeries(result["signal"], line.rolling(9).mean())

    def test_rvi(self):
        swma = lambda s: (s + 2 * s.shift(1) + 2 * s.shift(2) + s.shift(3)) / 6  # noqa: E731
        rvi = swma(C - O).rolling(10).mean() / swma(H - L).rolling(10).mean()
        result = compute("rvi", DATA)["outputs"]
        self.assertSeries(result["rvi"], rvi)
        self.assertSeries(result["signal"], swma(rvi))

    def test_trix(self):
        e3 = r_ema(r_ema(r_ema(C, 15), 15), 15)
        self.assertSeries(out("trix", period=15), (e3 - e3.shift()) / e3.shift() * 100)

    def test_tsi(self):
        d = C.diff()
        line = 100 * r_ema(r_ema(d, 25), 13) / r_ema(r_ema(d.abs(), 25), 13)
        result = compute("tsi", DATA)["outputs"]
        self.assertSeries(result["tsi"], line)
        self.assertSeries(result["signal"], r_ema(line, 13))

    def test_smi_ergodic(self):
        d = C.diff()
        line = 100 * r_ema(r_ema(d, 20), 5) / r_ema(r_ema(d.abs(), 20), 5)
        self.assertSeries(out("smi_ergodic", "smi"), line)

    def test_ultimate(self):
        pc = C.shift()
        bp = C - pd.concat([L, pc], axis=1).min(axis=1, skipna=False)
        tr = pd.concat([H, pc], axis=1).max(axis=1, skipna=False) - pd.concat([L, pc], axis=1).min(axis=1, skipna=False)
        avg = lambda n: bp.rolling(n).sum() / tr.rolling(n).sum()  # noqa: E731
        self.assertSeries(out("ultimate"), 100 * (4 * avg(7) + 2 * avg(14) + avg(28)) / 7)


# ── Trend ──────────────────────────────────────────────────────────────────────────────
class TrendTests(IndicatorAssertions, SimpleTestCase):
    def test_adx(self):
        up, down = H.diff(), -L.diff()
        pdm = up.where((up > down) & (up > 0), 0.0).where(up.notna())
        mdm = down.where((down > up) & (down > 0), 0.0).where(down.notna())
        tr = r_rma(r_tr(), 14)
        pdi, mdi = 100 * r_rma(pdm, 14) / tr, 100 * r_rma(mdm, 14) / tr
        dx = 100 * (pdi - mdi).abs() / (pdi + mdi)
        result = compute("adx", DATA)["outputs"]
        self.assertSeries(result["plus_di"], pdi)
        self.assertSeries(result["minus_di"], mdi)
        self.assertSeries(result["adx"], r_rma(dx, 14))

    def test_aroon(self):
        n = 25
        # bars since the most recent extreme = position of the extreme counted from the newest bar
        up = H.rolling(n + 1).apply(lambda w: 100 * (n - np.argmax(w[::-1])) / n, raw=True)
        down = L.rolling(n + 1).apply(lambda w: 100 * (n - np.argmin(w[::-1])) / n, raw=True)
        result = compute("aroon", DATA)["outputs"]
        self.assertSeries(result["up"], up)
        self.assertSeries(result["down"], down)

    def test_psar(self):
        # Rising bars: SAR starts at bar 0's low, accelerates toward new highs, stays below lows.
        highs, lows = [10, 11, 12, 13, 14], [9, 10, 11, 12, 13]
        sar = trend.parabolic_sar(highs, lows)
        self.assertEqual(sar[:2], [None, 9])
        self.assertEqual(sar[2], 9)  # 9 + 0.02*(11-9) = 9.04, clamped to the prior two lows (10, 9)
        self.assertAlmostEqual(sar[3], 9 + 0.04 * (12 - 9), places=10)  # AF stepped to 0.04 at the new high
        # A drop below SAR flips the trend: SAR jumps to the prior extreme point.
        flipped = trend.parabolic_sar([10, 11, 12, 13, 9], [9, 10, 11, 12, 5])
        self.assertEqual(flipped[4], 13)
        # On the dataset: whenever the trend holds, SAR stays on the correct side of the bar.
        values = out("psar")
        for i in range(3, ROWS):
            prev, cur = values[i - 1], values[i]
            if (prev < LOW[i - 1]) == (cur < LOW[i]) and cur < LOW[i]:
                self.assertLessEqual(cur, min(LOW[i - 1], LOW[i - 2]) + 1e-9)

    def test_supertrend(self):
        result = compute("supertrend", DATA)["outputs"]
        atr = r_rma(r_tr(), 10)
        for i in range(ROWS):
            up, down, direction = result["up"][i], result["down"][i], result["direction"][i]
            if pd.isna(atr[i]):
                self.assertTrue(up is None and down is None)
                continue
            self.assertEqual((up is None) + (down is None), 1)  # exactly one band is drawn
            if direction == 1:
                self.assertLessEqual(up, CLOSE[i])
            else:
                self.assertGreaterEqual(down, CLOSE[i])
        # An upward break of the upper band turns the trend up.
        st = trend.supertrend([10, 10, 10, 20], [9, 9, 9, 19], [9.2, 9.1, 9.0, 20], 2, 1)
        self.assertEqual(st["direction"][2:], [-1, 1])

    def test_vortex(self):
        tr = r_tr()
        result = compute("vortex", DATA)["outputs"]
        self.assertSeries(result["plus"], (H - L.shift()).abs().rolling(14).sum() / tr.rolling(14).sum())
        self.assertSeries(result["minus"], (L - H.shift()).abs().rolling(14).sum() / tr.rolling(14).sum())

    def test_ichimoku(self):
        mid = lambda n: (H.rolling(n).max() + L.rolling(n).min()) / 2  # noqa: E731
        result = compute("ichimoku", DATA)["outputs"]
        self.assertSeries(result["tenkan"], mid(9))
        self.assertSeries(result["senkou_a"], ((mid(9) + mid(26)) / 2).shift(26))
        self.assertSeries(result["senkou_b"], mid(52).shift(26))
        self.assertSeries(result["chikou"], C.shift(-26))

    def test_alligator(self):
        med = (H + L) / 2
        result = compute("alligator", DATA)["outputs"]
        self.assertSeries(result["jaw"], r_rma(med, 13).shift(8))
        self.assertSeries(result["lips"], r_rma(med, 5).shift(3))

    def test_choppiness(self):
        rng = H.rolling(14).max() - L.rolling(14).min()
        self.assertSeries(out("choppiness"), 100 * np.log10(r_tr().rolling(14).sum() / rng) / np.log10(14))

    def test_trend_strength(self):
        x = pd.Series(np.arange(ROWS), dtype=float)
        self.assertSeries(out("trend_strength"), C.rolling(14).corr(x))

    def test_mass_index(self):
        e1 = r_ema(H - L, 9)
        self.assertSeries(out("mass_index"), (e1 / r_ema(e1, 9)).rolling(25).sum())

    def test_chande_kroll(self):
        atr = r_rma(r_tr(), 10)
        result = compute("chande_kroll", DATA)["outputs"]
        self.assertSeries(result["short_stop"], (H.rolling(10).max() - atr).rolling(9).max())
        self.assertSeries(result["long_stop"], (L.rolling(10).min() + atr).rolling(9).min())

    def test_asi(self):
        # Bar 1: pc=10, po=9.5; H=11, L=9.8, C=10.8, O=10.1. |H-L|=1.2 beats |H-pc|=1 and |L-pc|=0.2,
        # so R = 1.2 + 0.25*0.5; K = max(1, 0.2) = 1; T = 10% of 10 = 1
        r = 1.2 + 0.25 * 0.5
        si = 50 * ((10.8 - 10) + 0.5 * (10.8 - 10.1) + 0.25 * (10 - 9.5)) / r * 1 / 1.0
        result = trend.accumulative_swing_index([9.5, 10.1], [10.2, 11], [9.4, 9.8], [10, 10.8], 10)
        self.assertIsNone(result[0])
        self.assertAlmostEqual(result[1], si, places=10)

    def test_zigzag(self):
        # Up 10 -> 20 (+100%), down to 15 (-25%), back to 22: swings at bars 0, 2, 4 then a provisional leg.
        highs = [10, 15, 20, 17, 15, 18, 22]
        lows = [10, 15, 20, 17, 15, 18, 22]
        z = trend.zigzag(highs, lows, 5)
        self.assertEqual(z[0], 10)
        self.assertEqual(z[2], 20)
        self.assertEqual(z[4], 15)
        self.assertEqual(z[6], 22)
        self.assertAlmostEqual(z[1], 15)   # interpolated between swing points
        self.assertAlmostEqual(z[3], 17.5)


# ── Volatility ─────────────────────────────────────────────────────────────────────────
class VolatilityTests(IndicatorAssertions, SimpleTestCase):
    def test_atr(self):
        self.assertSeries(out("atr"), r_rma(r_tr(), 14))
        tr = core.true_range([10, 12, 11, 15], [8, 9, 7, 12], [9, 11, 8, 14])
        self.assertEqual(tr, [None, 3, 4, 7])
        self.assertEqual(core.atr([10, 12, 11, 15], [8, 9, 7, 12], [9, 11, 8, 14], 2), [None, None, 3.5, 5.25])

    def test_bollinger(self):
        mid, sd = C.rolling(20).mean(), C.rolling(20).std(ddof=0)
        result = compute("bollinger", DATA)["outputs"]
        self.assertSeries(result["upper"], mid + 2 * sd)
        self.assertSeries(result["lower"], mid - 2 * sd)
        bands = volatility.bollinger([1, 2, 3, 4], 4, 2)  # population variance 1.25
        self.assertAlmostEqual(bands["upper"][3], 2.5 + 2 * 1.25 ** 0.5, places=10)

    def test_bollinger_b(self):
        mid, sd = C.rolling(20).mean(), C.rolling(20).std(ddof=0)
        self.assertSeries(out("bollinger_b"), (C - (mid - 2 * sd)) / (4 * sd))

    def test_bollinger_width(self):
        mid, sd = C.rolling(20).mean(), C.rolling(20).std(ddof=0)
        self.assertSeries(out("bollinger_width"), 4 * sd / mid)

    def test_keltner(self):
        mid, atr = r_ema(C, 20), r_rma(r_tr(), 10)
        self.assertSeries(out("keltner", "upper"), mid + 2 * atr)

    def test_donchian(self):
        self.assertSeries(out("donchian", "middle"), (H.rolling(20).max() + L.rolling(20).min()) / 2)

    def test_envelopes(self):
        self.assertSeries(out("envelopes", "lower"), C.rolling(20).mean() * 0.95)

    def test_std_dev(self):
        self.assertSeries(out("std_dev"), C.rolling(20).std(ddof=0))

    def test_std_error(self):
        x = np.arange(1, 21)

        def se(w):
            b, a = np.polyfit(x, w, 1)
            return math.sqrt(((w - (a + b * x)) ** 2).sum() / 18)

        self.assertSeries(out("std_error"), C.rolling(20).apply(se, raw=True))

    def test_std_error_bands(self):
        x = np.arange(1, 22)

        def band(w):
            b, a = np.polyfit(x, w, 1)
            return a + b * 21 + 2 * math.sqrt(((w - (a + b * x)) ** 2).sum() / 19)

        self.assertSeries(out("std_error_bands", "upper"), C.rolling(21).apply(band, raw=True))

    def test_chaikin_volatility(self):
        e = r_ema(H - L, 10)
        self.assertSeries(out("chaikin_volatility"), 100 * (e - e.shift(10)) / e.shift(10))

    def test_hist_vol(self):
        r = np.log(C / C.shift())
        self.assertSeries(out("hist_vol"), r.rolling(20).std(ddof=0) * math.sqrt(240))

    def test_zero_trend_vol(self):
        r = np.log(C / C.shift())
        self.assertSeries(out("zero_trend_vol"), np.sqrt((r ** 2).rolling(20).mean()) * math.sqrt(240))

    def test_garman_klass(self):
        term = 0.5 * np.log(H / L) ** 2 - (2 * math.log(2) - 1) * np.log(C / O) ** 2
        self.assertSeries(out("garman_klass"), np.sqrt(term.rolling(20).mean()) * math.sqrt(240))

    def test_rvi_volatility(self):
        sd = C.rolling(10).std(ddof=0)
        up = sd.where(C > C.shift(), 0.0).where(sd.notna() & C.shift().notna())
        down = sd.where(C < C.shift(), 0.0).where(sd.notna() & C.shift().notna())
        eu, ed = r_ema(up, 14), r_ema(down, 14)
        self.assertSeries(out("rvi_volatility"), 100 * eu / (eu + ed))


# ── Volume ─────────────────────────────────────────────────────────────────────────────
class VolumeTests(IndicatorAssertions, SimpleTestCase):
    def test_volume(self):
        result = compute("volume", DATA)["outputs"]
        self.assertSeries(result["volume"], V)
        self.assertEqual(result["direction"][:3], [1 if c >= o else -1 for o, c in zip(OPEN[:3], CLOSE[:3])])

    def test_volume_oscillator(self):
        f, s = r_ema(V, 5), r_ema(V, 10)
        self.assertSeries(out("volume_oscillator"), (f - s) / s * 100)

    def test_obv(self):
        self.assertSeries(out("obv"), (np.sign(C.diff()).fillna(0) * V).cumsum())
        self.assertEqual(volume.obv([10, 11, 11, 9, 12], [5, 7, 3, 4, 0]), [0.0, 7.0, 7.0, 3.0, 3.0])

    def test_net_volume(self):
        self.assertSeries(out("net_volume"), np.sign(C.diff()) * V)

    def test_ad(self):
        clv = ((C - L) - (H - C)) / (H - L)
        self.assertSeries(out("ad"), (clv * V).cumsum())
        self.assertEqual(volume.clv([5], [5], [5]), [0.0])  # H = L

    def test_cmf(self):
        clv = ((C - L) - (H - C)) / (H - L)
        self.assertSeries(out("cmf"), (clv * V).rolling(20).sum() / V.rolling(20).sum())

    def test_chaikin_osc(self):
        ad = (((C - L) - (H - C)) / (H - L) * V).cumsum()
        self.assertSeries(out("chaikin_osc"), r_ema(ad, 3) - r_ema(ad, 10))

    def test_mfi(self):
        tp = (H + L + C) / 3
        flow = tp * V
        pos = flow.where(tp > tp.shift(), 0.0).where(tp.shift().notna())
        neg = flow.where(tp < tp.shift(), 0.0).where(tp.shift().notna())
        ratio = pos.rolling(14).sum() / neg.rolling(14).sum()
        self.assertSeries(out("mfi"), (100 - 100 / (1 + ratio)).where(neg.rolling(14).sum() != 0, 100.0)
                          .where(ratio.notna() | (neg.rolling(14).sum() == 0)).where(pos.rolling(14).sum().notna()))

    def test_eom(self):
        dist = (H + L) / 2 - (H.shift() + L.shift()) / 2
        raw = dist / ((V / 10000) / (H - L))
        raw = raw.where(V != 0)
        self.assertSeries(out("eom"), raw.rolling(14).mean())

    def test_force_index(self):
        self.assertSeries(out("force_index"), r_ema((C - C.shift()) * V, 13))

    def test_klinger(self):
        # Bar 1 trends up (HLC 9 > 4.5); cm = dm + prev dm = 2 + 1 = 3; VF = 100 * |2*(2/3 - 1)| * 1 * 100.
        # With EMA periods of 1, KO = VF - VF = 0 and EMA(1) of VF is VF itself.
        result = volume.klinger([2, 4], [1, 2], [1.5, 3], [0, 100], 1, 1, 1)
        self.assertAlmostEqual(result["ko"][1], 0.0)
        self.assertAlmostEqual(core.ema([None, 100 * abs(2 * (2 / 3 - 1)) * 100], 1)[1], 6666.6667, places=3)
        down = volume.klinger([2, 4, 3], [1, 2, 1], [1.5, 3, 1.5], [0, 100, 50], 1, 2, 1)
        self.assertIsNotNone(down["ko"][2])
        line = compute("klinger", DATA)["outputs"]
        self.assertTrue(all(v is None for v in line["ko"][:55]))
        self.assertIsNotNone(line["ko"][55])

    def test_pvt(self):
        self.assertSeries(out("pvt"), (V * C.diff() / C.shift()).fillna(0).cumsum())

    def test_vwap(self):
        tp = (H + L + C) / 3
        self.assertSeries(out("vwap"), (tp * V).cumsum() / V.cumsum())

    def test_vwap_rolling(self):
        tp = (H + L + C) / 3
        self.assertSeries(out("vwap_rolling"), (tp * V).rolling(20).sum() / V.rolling(20).sum())

    def test_volume_profile(self):
        # Two bars over 10-20 split into 2 rows: bar A 10-15 (100) all in row 0; bar B 10-20 (50) half each.
        result = volume.volume_profile([15, 20], [10, 10], [100, 50], rows=2, value_area=70)
        rows = result["extra"]["rows"]
        self.assertEqual([r["volume"] for r in rows], [125.0, 25.0])
        self.assertEqual(result["poc"], [12.5, 12.5])
        self.assertEqual(result["val"][0], 10)
        self.assertEqual(result["vah"][0], 15)  # 125/150 = 83% >= 70%, so the value area is the POC row


# ── Price and levels ───────────────────────────────────────────────────────────────────
class PriceTests(IndicatorAssertions, SimpleTestCase):
    def test_avg_price(self):
        self.assertSeries(out("avg_price"), (O + H + L + C) / 4)

    def test_median_price(self):
        self.assertSeries(out("median_price"), (H + L) / 2)

    def test_typical_price(self):
        self.assertSeries(out("typical_price"), (H + L + C) / 3)

    def test_pivots(self):
        days = [date(2025, 1, 6), date(2025, 1, 7), date(2025, 1, 13)]  # Mon, Tue, next Mon
        result = price.pivot_points([12, 14, 20], [8, 9, 15], [10, 13, 18], days, "W")
        p = (14 + 8 + 13) / 3
        self.assertEqual(result["p"][:2], [None, None])
        self.assertAlmostEqual(result["p"][2], p)
        self.assertAlmostEqual(result["r1"][2], 2 * p - 8)
        self.assertAlmostEqual(result["s3"][2], 8 - 2 * (14 - p))

    def test_week52(self):
        days = [date(2024, 1, 1) + timedelta(days=7 * i) for i in range(54)]
        highs = list(range(54))
        result = price.week_52_high_low(highs, highs, days, 52)
        self.assertIsNone(result["high"][51])         # not yet 52 weeks of history
        self.assertEqual(result["high"][52], 52)
        self.assertEqual(result["low"][53], 2)          # window covers the last 52 weeks only

    def test_fractals(self):
        result = price.fractals([1, 2, 5, 2, 1, 3], [5, 4, 1, 4, 5, 6], 2)
        self.assertEqual(result["up"], [None, None, 5, None, None, None])
        self.assertEqual(result["down"], [None, None, 1, None, None, None])


# ── Market-wide and relative ───────────────────────────────────────────────────────────
D1, D2, D3 = date(2025, 1, 5), date(2025, 1, 6), date(2025, 1, 7)
UNIVERSE = [
    {D1: (10, 100, 10, 10), D2: (11, 200, 11, 11), D3: (12, 300, 12, 12)},
    {D1: (20, 100, 20, 20), D2: (19, 50, 19, 19), D3: (19, 60, 19, 19)},
    {D2: (5, 10, 5, 5), D3: (4, 20, 4, 4)},
]


class MarketTests(IndicatorAssertions, SimpleTestCase):
    def test_advance_decline(self):
        result = market.advance_decline(UNIVERSE, [D1, D2, D3])
        # D2: 1 up, 1 down (the third stock has no previous bar); D3: 1 up, 1 flat, 1 down
        self.assertEqual(result["net"], [None, 0.0, 0.0])
        self.assertEqual(result["line"], [None, 0.0, 0.0])

    def test_ad_volume(self):
        # D2: +200 (up) - 50 (down) = 150; D3: +300 - 20 = 280 (the flat stock adds 0) -> 430
        self.assertEqual(market.ad_volume_line(UNIVERSE, [D1, D2, D3]), [None, 150.0, 430.0])

    def test_pct_above_ma(self):
        result = market.percent_above_ma(UNIVERSE, [D1, D2, D3], 2, 2, 3)
        # D3 SMA2: 11.5 / 19 / 4.5 vs closes 12 / 19 / 4 -> only the first is above: 1 of 3
        self.assertEqual(result["above_fast"][:2], [None, 50.0])
        self.assertAlmostEqual(result["above_fast"][2], 100 / 3)
        self.assertEqual(result["above_slow"], [None, None, 50.0])

    def test_net_highs_lows(self):
        days = [date(2024, 1, 1) + timedelta(days=7 * i) for i in range(4)]
        universe = [{d: (i, 1, i, i) for i, d in enumerate(days)}]
        self.assertEqual(market.net_new_highs_lows(universe, days, 2), [None, None, 1.0, 1.0])

    def test_ratio(self):
        self.assertEqual(market.ratio([10, 12], [5, None]), [2.0, None])

    def test_spread(self):
        self.assertEqual(market.spread([10, 12], [5, 4]), [5, 8])

    def test_relative_strength(self):
        self.assertEqual(market.relative_strength([10], [5]), [200.0])

    def test_mansfield_rs(self):
        bench = (C * 0.5 + 3).tolist()
        rs = C / (C * 0.5 + 3) * 100
        self.assertSeries(market.mansfield_rs(CLOSE, bench, 20), (rs / rs.rolling(20).mean() - 1) * 100)

    def test_correlation(self):
        bench = pd.Series([c * 0.5 + ((i % 7) - 3) for i, c in enumerate(CLOSE)])
        self.assertSeries(market.correlation(CLOSE, bench.tolist(), 20), C.rolling(20).corr(bench))

    def test_log_correlation(self):
        bench = pd.Series([c * 0.5 + ((i % 7) - 3) for i, c in enumerate(CLOSE)])
        ra, rb = np.log(C / C.shift()), np.log(bench / bench.shift())
        self.assertSeries(market.log_correlation(CLOSE, bench.tolist(), 20), ra.rolling(20).corr(rb))

    def test_tick_volume(self):
        trades = [(D1, 1, 100, 10), (D1, 2, 101, 5), (D1, 3, 101, 7), (D1, 4, 99, 3), (D2, 1, 99, 4)]
        result = market.tick_buy_sell(trades, [D1, D2, D3])
        self.assertEqual(result["buy"], [12.0, 0.0, None])   # 101 up-tick, 101 zero-tick keeps "buy"
        self.assertEqual(result["sell"], [3.0, 4.0, None])   # 99 down-tick, next-day 99 keeps "sell"


# ── Standard versions ──────────────────────────────────────────────────────────────────
class StandardVersionTests(IndicatorAssertions, SimpleTestCase):
    def test_inside_bar(self):
        self.assertEqual(custom.inside_bar([10, 9, 11], [5, 6, 4]), [None, 9, None])

    def test_ut_bot(self):
        result = compute("ut_bot", DATA)["outputs"]
        for i in range(1, ROWS):
            stop = result["stop"][i]
            if stop is None:
                continue
            if result["buy"][i] is not None:
                self.assertGreater(CLOSE[i], result["stop"][i - 1])
            if result["sell"][i] is not None:
                self.assertLess(CLOSE[i], result["stop"][i - 1])
        self.assertTrue(any(v is not None for v in result["buy"] + result["sell"]))

    def test_zero_lag_macd(self):
        zl = lambda s, n: r_ema(s + (s - s.shift((n - 1) // 2)), n)  # noqa: E731
        line = zl(C, 12) - zl(C, 26)
        self.assertSeries(out("zero_lag_macd", "macd"), line)
        self.assertSeries(out("zero_lag_macd", "signal"), zl(line, 9))

    def test_tdi(self):
        r = r_rsi(C, 13)
        result = compute("tdi", DATA)["outputs"]
        self.assertSeries(result["price"], r.rolling(2).mean())
        self.assertSeries(result["upper"], r.rolling(34).mean() + 1.6185 * r.rolling(34).std(ddof=0))

    def test_weinstein(self):
        rising = [float(i) for i in range(1, 30)]
        stages = custom.weinstein_stage(rising, 10, 5, 0.5)
        self.assertIsNone(stages[13])
        self.assertEqual(stages[-1], 2.0)
        falling = list(reversed(rising))
        self.assertEqual(custom.weinstein_stage(falling, 10, 5, 0.5)[-1], 4.0)
        flat_after_rise = rising + [29.0] * 20
        self.assertEqual(custom.weinstein_stage(flat_after_rise, 10, 5, 0.5)[-1], 3.0)


# ── Every indicator: registry contract and edge cases ──────────────────────────────────
def _edge_data(close, high=None, low=None, open_=None, vol=None):
    n = len(close)
    high = high or [c + 1 for c in close]
    low = low or [c - 1 for c in close]
    open_ = open_ or list(close)
    vol = vol if vol is not None else [100] * n
    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(n)]
    universe = [{d: (c, v, h, lo) for d, c, v, h, lo in zip(dates, close, vol, high, low)}]
    return {"open": open_, "high": high, "low": low, "close": close, "volume": vol, "date": dates,
            "universe": universe, "benchmark": [c * 2 for c in close],
            "trades": [(d, i, c, 10) for i, (d, c) in enumerate(zip(dates, close))]}


EDGE_CASES = {
    "five_rows": _edge_data([10.0, 11, 12, 11, 13]),
    "constant_prices": _edge_data([10.0] * 60, [10.0] * 60, [10.0] * 60, [10.0] * 60),
    "high_equals_low": _edge_data([10.0 + (i % 3) for i in range(60)], [10.0 + (i % 3) for i in range(60)],
                                  [10.0 + (i % 3) for i in range(60)]),
    "zero_volume": _edge_data([10.0 + (i % 5) for i in range(60)], vol=[0] * 60),
    "empty": _edge_data([]),
}


class RegistryAndEdgeCaseTests(SimpleTestCase):
    def test_every_indicator_survives_edge_cases(self):
        for name, data in EDGE_CASES.items():
            for indicator_id in REGISTRY:
                with self.subTest(case=name, indicator=indicator_id):
                    outputs = compute(indicator_id, data)["outputs"]
                    for key, series in outputs.items():
                        self.assertEqual(len(series), len(data["close"]), key)
                        for value in series:
                            self.assertFalse(isinstance(value, float) and (math.isnan(value) or math.isinf(value)))

    def test_short_series_is_warm_up_not_zero(self):
        data = EDGE_CASES["five_rows"]
        for indicator_id in ("sma", "ema", "rsi", "macd", "bollinger", "atr", "adx", "stochastic", "cci", "mfi",
                             "ichimoku", "kst", "supertrend", "aroon", "tsi", "trix", "keltner", "hist_vol"):
            for key, series in compute(indicator_id, data)["outputs"].items():
                if key == "direction":
                    continue
                self.assertTrue(all(v is None for v in series), f"{indicator_id}.{key}: {series}")

    def test_registry_entries_are_complete(self):
        payload = registry_payload()
        self.assertEqual(len(payload["indicators"]), len(REGISTRY))
        for entry in payload["indicators"]:
            self.assertIn(entry["display"], ("overlay", "panel"))
            self.assertTrue(entry["outputs"])
            for param in entry["params"]:
                self.assertIn(param["kind"], ("int", "float", "choice"))
        self.assertEqual(len(payload["not_implemented"]), 8)

    def test_params_are_validated(self):
        rsi = REGISTRY["rsi"]
        self.assertEqual(resolve_params(rsi, {}), {"period": 14})
        self.assertEqual(resolve_params(rsi, {"period": "7"}), {"period": 7})
        for bad in ({"period": 0}, {"period": 2.5}, {"period": "x"}, {"length": 5}):
            with self.assertRaises(ValueError):
                resolve_params(rsi, bad)
        with self.assertRaises(ValueError):
            resolve_params(REGISTRY["pivots"], {"timeframe": "Y"})

    def test_every_registry_id_has_a_named_test(self):
        tested = {name[5:] for cls in (MovingAverageTests, MomentumTests, TrendTests, VolatilityTests,
                                       VolumeTests, PriceTests, MarketTests, StandardVersionTests)
                  for name in dir(cls) if name.startswith("test_")}
        self.assertEqual(set(REGISTRY) - tested, set())


VERIFIED_BY_HAND = {
    "mcginley", "kama", "fisher", "psar", "supertrend", "asi", "zigzag", "klinger", "volume_profile", "pivots",
    "week52", "fractals", "advance_decline", "ad_volume", "pct_above_ma", "net_highs_lows", "ratio", "spread",
    "relative_strength", "tick_volume", "inside_bar", "ut_bot", "weinstein",
}


# ── API ────────────────────────────────────────────────────────────────────────────────
class IndicatorApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(symbol="IND", name="Indicator Co", sector="Banking")
        self.other = Company.objects.create(symbol="OTH", name="Other Co", sector="Hydropower")
        self.admin = User.objects.create_user(username="ind-admin", email="ind-admin@example.test",
                                              password="unused-test-password", role=User.Role.ADMIN)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        for i, day in enumerate(DATES):
            source = "unverified" if i < 20 else "crawled"
            for company, scale in ((self.company, 1), (self.other, 0.5)):
                DailyPrice.objects.create(
                    company=company, source=source, date=day,
                    open=round(OPEN[i] * scale, 2), high=round(HIGH[i] * scale, 2), low=round(LOW[i] * scale, 2),
                    close=round(CLOSE[i] * scale, 2), volume=VOLUME[i], turnover=0,
                )
            ProxyIndexSnapshot.objects.create(date=day, level=1000 + i)
        FloorsheetTransaction.objects.create(company=self.company, date=DATES[-1], transaction_id="1",
                                             buyer_broker="1", seller_broker="2", quantity=10, rate=100, amount=1000)
        FloorsheetTransaction.objects.create(company=self.company, date=DATES[-1], transaction_id="2",
                                             buyer_broker="1", seller_broker="2", quantity=5, rate=101, amount=505)
        self.url = f"/api/market-intelligence/companies/{self.company.pk}/indicators/"

    def get(self, specs, **params):
        import json
        return self.client.get(self.url, {"specs": json.dumps(specs), **params})

    def test_registry_endpoint(self):
        response = self.client.get("/api/market-intelligence/indicators/registry/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["indicators"]), len(REGISTRY))
        self.assertEqual(len(response.data["not_implemented"]), 8)

    def test_series_use_crawled_history_by_default(self):
        response = self.get([{"id": "sma", "params": {"period": 5}}])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["dates"]), ROWS - 20)
        values = response.data["results"][0]["outputs"]["value"]
        self.assertEqual(values[:4], [None] * 4)
        self.assertAlmostEqual(values[4], sum(CLOSE[20:25]) / 5, places=4)

    def test_unverified_rows_never_feed_indicators(self):
        # The first 20 rows are "unverified"; asking for them is ignored, the series starts at the crawled rows.
        response = self.get([{"id": "sma", "params": {"period": 5}}], history="all", start_date=DATES[0].isoformat())
        self.assertEqual(response.data["dates"][0], DATES[20])
        self.assertEqual(response.data["results"][0]["outputs"]["value"][:4], [None] * 4)

    def test_range_scoped_vwap_anchors_at_start_date(self):
        response = self.get([{"id": "vwap"}], start_date=DATES[40].isoformat())
        first = response.data["results"][0]["outputs"]["value"][0]
        self.assertAlmostEqual(first, (HIGH[40] + LOW[40] + CLOSE[40]) / 3, places=4)

    def test_market_benchmark_and_floorsheet_scopes(self):
        response = self.get([{"id": "advance_decline"}, {"id": "ratio"}, {"id": "tick_volume"}])
        self.assertEqual(response.status_code, 200)
        ratio = response.data["results"][1]["outputs"]["value"]
        self.assertAlmostEqual(ratio[0], CLOSE[20] / 1020, places=4)
        self.assertIn("not official NEPSE", response.data["benchmark"])
        self.assertEqual(response.data["results"][2]["outputs"]["buy"][-1], 5.0)
        other = self.get([{"id": "ratio"}], benchmark=str(self.other.pk))
        self.assertAlmostEqual(other.data["results"][0]["outputs"]["value"][0], 2.0, places=2)

    def test_errors(self):
        self.assertEqual(self.get([{"id": "nope"}]).status_code, 400)
        self.assertEqual(self.client.get(self.url, {"specs": "not json"}).status_code, 400)
        self.assertEqual(self.get([{"id": "rsi"}], start_date="2025-13-01").status_code, 400)
        bad_param = self.get([{"id": "rsi", "params": {"period": 0}}])
        self.assertEqual(bad_param.status_code, 200)
        self.assertIn("period", bad_param.data["results"][0]["error"])

    def test_requires_company_access_and_view_analysis(self):
        from apps.users.models import CustomRole

        viewer = User.objects.create_user(username="ind-viewer", email="ind-viewer@example.test",
                                          password="unused-test-password", role=User.Role.VIEWER)
        self.client.force_authenticate(viewer)
        self.assertEqual(self.get([{"id": "rsi"}]).status_code, 403)  # no access to this company

        no_analysis = User.objects.create_user(
            username="ind-none", email="ind-none@example.test", password="unused-test-password",
            role=User.Role.VIEWER, custom_role=CustomRole.objects.create(name="No analysis", permissions=[]),
        )
        self.client.force_authenticate(no_analysis)
        self.assertEqual(self.client.get("/api/market-intelligence/indicators/registry/").status_code, 403)
