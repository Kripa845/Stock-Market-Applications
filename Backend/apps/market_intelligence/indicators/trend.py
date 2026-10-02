"""Trend indicators."""

from math import log10

from .core import (
    atr as _atr, check_period, combine, highest, lag, lowest, pearson, rma, rolling, rolling_multi, rolling_sum,
    ema, true_range,
)


def adx(high, low, close, period=14):
    n = check_period(period)
    plus_dm, minus_dm = [None] * len(high), [None] * len(high)
    for i in range(1, len(high)):
        up, down = high[i] - high[i - 1], low[i - 1] - low[i]
        plus_dm[i] = up if up > down and up > 0 else 0.0
        minus_dm[i] = down if down > up and down > 0 else 0.0
    tr = rma(true_range(high, low, close), n)
    plus_di = combine(lambda dm, t: 100 * dm / t, rma(plus_dm, n), tr)
    minus_di = combine(lambda dm, t: 100 * dm / t, rma(minus_dm, n), tr)
    dx = combine(lambda p, m: 100 * abs(p - m) / (p + m), plus_di, minus_di)
    return {"plus_di": plus_di, "minus_di": minus_di, "adx": rma(dx, n)}


def aroon(high, low, period=25):
    """Bars since the (most recent) highest high / lowest low over the last N+1 bars, so values span 0-100."""
    n = check_period(period)

    def since(window, best):
        return len(window) - 1 - max(j for j, x in enumerate(window) if x == best(window))

    up = rolling(high, n + 1, lambda w: 100 * (n - since(w, max)) / n)
    down = rolling(low, n + 1, lambda w: 100 * (n - since(w, min)) / n)
    return {"up": up, "down": down}


def parabolic_sar(high, low, step=0.02, max_step=0.2):
    """Wilder's Parabolic SAR. The first trend is up if bar 1's midpoint is not below bar 0's."""
    out = [None] * len(high)
    if len(high) < 2:
        return out
    up = (high[1] + low[1]) >= (high[0] + low[0])
    sar = low[0] if up else high[0]
    ep = high[1] if up else low[1]
    af = step
    out[1] = sar
    for i in range(2, len(high)):
        sar = sar + af * (ep - sar)
        if up:
            sar = min(sar, low[i - 1], low[i - 2])
            if low[i] < sar:
                up, sar, ep, af = False, ep, low[i], step
            elif high[i] > ep:
                ep, af = high[i], min(af + step, max_step)
        else:
            sar = max(sar, high[i - 1], high[i - 2])
            if high[i] > sar:
                up, sar, ep, af = True, ep, high[i], step
            elif low[i] < ep:
                ep, af = low[i], min(af + step, max_step)
        out[i] = sar
    return out


def supertrend(high, low, close, period=10, multiplier=3):
    """Returns the lower band while trending up and the upper band while trending down, as two lines."""
    atr_values = _atr(high, low, close, period)
    upper_line, lower_line, direction = [None] * len(close), [None] * len(close), [None] * len(close)
    final_upper = final_lower = trend = None
    for i in range(len(close)):
        if atr_values[i] is None:
            final_upper = final_lower = trend = None
            continue
        median = (high[i] + low[i]) / 2
        basic_upper, basic_lower = median + multiplier * atr_values[i], median - multiplier * atr_values[i]
        if trend is None:
            final_upper, final_lower = basic_upper, basic_lower
            trend = 1 if close[i] >= median else -1
        else:
            prev_close = close[i - 1]
            final_upper = basic_upper if basic_upper < final_upper or prev_close > final_upper else final_upper
            final_lower = basic_lower if basic_lower > final_lower or prev_close < final_lower else final_lower
            if trend == -1 and close[i] > final_upper:
                trend = 1
            elif trend == 1 and close[i] < final_lower:
                trend = -1
        direction[i] = trend
        if trend == 1:
            lower_line[i] = final_lower
        else:
            upper_line[i] = final_upper
    return {"up": lower_line, "down": upper_line, "direction": direction}


def vortex(high, low, close, period=14):
    prev_high, prev_low = lag(high, 1), lag(low, 1)
    vm_plus = combine(lambda h, pl: abs(h - pl), high, prev_low)
    vm_minus = combine(lambda l, ph: abs(l - ph), low, prev_high)
    tr = true_range(high, low, close)
    ratio = lambda vm, t: sum(vm) / sum(t)  # noqa: E731
    return {
        "plus": rolling_multi([vm_plus, tr], period, ratio),
        "minus": rolling_multi([vm_minus, tr], period, ratio),
    }


def _midpoint(high, low, n):
    return combine(lambda hh, ll: (hh + ll) / 2, highest(high, n), lowest(low, n))


def ichimoku(high, low, close, conversion=9, base=26, span_b=52, displacement=26):
    """Senkou spans are shifted forward and Chikou back by ``displacement`` bars.

    Only values that land on an existing bar are returned, so the cloud's last
    ``displacement`` bars into the future are not drawn.
    """
    tenkan, kijun = _midpoint(high, low, conversion), _midpoint(high, low, base)
    span_a = combine(lambda t, k: (t + k) / 2, tenkan, kijun)
    return {
        "tenkan": tenkan, "kijun": kijun,
        "senkou_a": lag(span_a, displacement), "senkou_b": lag(_midpoint(high, low, span_b), displacement),
        "chikou": lag(close, -displacement),
    }


def alligator(high, low, jaw=13, jaw_shift=8, teeth=8, teeth_shift=5, lips=5, lips_shift=3):
    median = combine(lambda h, l: (h + l) / 2, high, low)
    return {
        "jaw": lag(rma(median, jaw), jaw_shift),
        "teeth": lag(rma(median, teeth), teeth_shift),
        "lips": lag(rma(median, lips), lips_shift),
    }


def choppiness(high, low, close, period=14):
    n = check_period(period, 2)
    return rolling_multi(
        [true_range(high, low, close), high, low], n,
        lambda tr, h, l: 100 * log10(sum(tr) / (max(h) - min(l))) / log10(n),
    )


def trend_strength(close, period=14):
    """Pearson correlation between close and bar number over N bars (-1 to 1)."""
    n = check_period(period, 2)
    xs = list(range(1, n + 1))
    return rolling(close, n, lambda w: pearson(xs, w))


def mass_index(high, low, ema_period=9, sum_period=25):
    rng = combine(lambda h, l: h - l, high, low)
    single = ema(rng, ema_period)
    ratio = combine(lambda a, b: a / b, single, ema(single, ema_period))
    return rolling_sum(ratio, sum_period)


def chande_kroll(high, low, close, atr_period=10, multiplier=1, stop_period=9):
    atr_values = _atr(high, low, close, atr_period)
    first_high = combine(lambda hh, a: hh - multiplier * a, highest(high, atr_period), atr_values)
    first_low = combine(lambda ll, a: ll + multiplier * a, lowest(low, atr_period), atr_values)
    return {"short_stop": highest(first_high, stop_period), "long_stop": lowest(first_low, stop_period)}


def accumulative_swing_index(open_, high, low, close, limit_pct=10):
    """Wilder's ASI. T (limit move) = limit_pct % of the previous close. SI is 0 when R is 0."""
    out = [None] * len(close)
    total = 0.0
    for i in range(1, len(close)):
        pc, po = close[i - 1], open_[i - 1]
        a, b, c = abs(high[i] - pc), abs(low[i] - pc), abs(high[i] - low[i])
        d = abs(pc - po)
        if a >= b and a >= c:
            r = a - 0.5 * b + 0.25 * d
        elif b >= a and b >= c:
            r = b - 0.5 * a + 0.25 * d
        else:
            r = c + 0.25 * d
        t = limit_pct / 100 * pc
        if not t:
            out[i] = None
            continue
        k = max(a, b)
        si = 50 * ((close[i] - pc) + 0.5 * (close[i] - open_[i]) + 0.25 * (pc - po)) / r * k / t if r else 0.0
        total += si
        out[i] = total
    return out


def zigzag(high, low, deviation=5):
    """Swing points where price reverses more than ``deviation`` % from the last extreme, joined by lines.

    The last leg runs to the current extreme and can still move as new bars arrive.
    """
    n = len(high)
    out = [None] * n
    if n < 2:
        return out
    pct = deviation / 100
    pivots = []
    hi, lo, trend = (0, high[0]), (0, low[0]), 0
    for i in range(1, n):
        if trend >= 0 and high[i] > hi[1]:
            hi = (i, high[i])
            if trend == 1:
                lo = (i, low[i])
        if trend <= 0 and low[i] < lo[1]:
            lo = (i, low[i])
            if trend == -1:
                hi = (i, high[i])
        if trend == 0:
            if hi[1] >= lo[1] * (1 + pct) and hi[0] > lo[0]:
                pivots.append(lo)
                trend = 1
            elif lo[1] <= hi[1] * (1 - pct) and lo[0] > hi[0]:
                pivots.append(hi)
                trend = -1
        elif trend == 1 and low[i] <= hi[1] * (1 - pct):
            pivots.append(hi)
            trend, lo = -1, (i, low[i])
        elif trend == -1 and high[i] >= lo[1] * (1 + pct):
            pivots.append(lo)
            trend, hi = 1, (i, high[i])
    if trend == 1:
        pivots.append(hi)
    elif trend == -1:
        pivots.append(lo)
    for (i0, p0), (i1, p1) in zip(pivots, pivots[1:]):
        for j in range(i0, i1 + 1):
            out[j] = p0 + (p1 - p0) * (j - i0) / (i1 - i0) if i1 != i0 else p1
    return out

