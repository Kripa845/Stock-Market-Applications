"""Moving averages (drawn over the price)."""

from math import cos, exp, pi, sqrt

from .core import (
    check_period, combine, cross_markers, ema as _ema, linear_fit, rma, rolling, rolling_multi, sma as _sma,
    wma as _wma,
)


def sma(close, period=20):
    return _sma(close, period)


def ema(close, period=20):
    return _ema(close, period)


def wma(close, period=20):
    return _wma(close, period)


def dema(close, period=20):
    e1 = _ema(close, period)
    return combine(lambda a, b: 2 * a - b, e1, _ema(e1, period))


def tema(close, period=20):
    e1 = _ema(close, period)
    e2 = _ema(e1, period)
    return combine(lambda a, b, c: 3 * a - 3 * b + c, e1, e2, _ema(e2, period))


def hull_ma(close, period=9):
    period = check_period(period, 2)
    raw = combine(lambda half, full: 2 * half - full, _wma(close, period // 2), _wma(close, period))
    return _wma(raw, int(sqrt(period)))


def smma(close, period=7):
    return rma(close, period)


def vwma(close, volume, period=20):
    return rolling_multi(
        [close, volume], period,
        lambda c, v: sum(x * y for x, y in zip(c, v)) / sum(v),
    )


def mcginley(close, period=14):
    """MD = prevMD + (C - prevMD) / (0.6 * N * (C / prevMD)^4), seeded with the SMA of the first N closes."""
    n = check_period(period)
    out = [None] * len(close)
    seed, previous = [], None
    for i, c in enumerate(close):
        if c is None:
            seed, previous = [], None
            continue
        if previous is None:
            seed.append(c)
            if len(seed) == n:
                previous = sum(seed) / n
                out[i] = previous
            continue
        if previous == 0:
            seed, previous = [], None
            continue
        previous = previous + (c - previous) / (0.6 * n * (c / previous) ** 4)
        out[i] = previous
    return out


def alma(close, period=9, offset=0.85, sigma=6):
    n = check_period(period)
    m = offset * (n - 1)
    s = n / sigma
    weights = [exp(-((i - m) ** 2) / (2 * s * s)) for i in range(n)]
    total = sum(weights)
    return rolling(close, n, lambda w: sum(wi * x for wi, x in zip(weights, w)) / total)


def lsma(close, period=25):
    """Linear regression curve: the fitted line's value at the newest bar (x = N)."""
    n = check_period(period, 2)
    return rolling(close, n, lambda w: (lambda a, b: a + b * n)(*linear_fit(w)))


def linreg_slope(close, period=25):
    return rolling(close, check_period(period, 2), lambda w: linear_fit(w)[1])


def kama(close, period=10, fast=2, slow=30):
    """Kaufman AMA. ER = |C - C[N ago]| / sum|C - prevC| over N; SC = (ER*(fast_sc - slow_sc) + slow_sc)^2."""
    n = check_period(period)
    fast_sc, slow_sc = 2 / (fast + 1), 2 / (slow + 1)
    out = [None] * len(close)
    if len(close) < n or any(c is None for c in close):
        return out
    out[n - 1] = sum(close[:n]) / n
    for i in range(n, len(close)):
        volatility = sum(abs(close[j] - close[j - 1]) for j in range(i - n + 1, i + 1))
        er = abs(close[i] - close[i - n]) / volatility if volatility else 0.0
        sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2
        out[i] = out[i - 1] + sc * (close[i] - out[i - 1])
    return out


def hamming_ma(close, period=20):
    n = check_period(period, 2)
    weights = [0.54 - 0.46 * cos(2 * pi * i / (n - 1)) for i in range(n)]
    total = sum(weights)
    return rolling(close, n, lambda w: sum(wi * x for wi, x in zip(weights, w)) / total)


def ma_channel(high, low, period=20):
    return {"upper": _sma(high, period), "lower": _sma(low, period)}


def ma_double(close, fast=10, slow=30):
    return {"ma1": _sma(close, fast), "ma2": _sma(close, slow)}


def ma_triple(close, ma1=10, ma2=20, ma3=50):
    return {"ma1": _sma(close, ma1), "ma2": _sma(close, ma2), "ma3": _sma(close, ma3)}


def ma_multiple(close, ma1=5, ma2=10, ma3=20, ma4=50, ma5=100, ma6=200):
    periods = {"ma1": ma1, "ma2": ma2, "ma3": ma3, "ma4": ma4, "ma5": ma5, "ma6": ma6}
    return {key: _sma(close, p) for key, p in periods.items()}


def _cross(fast_line, slow_line):
    up, down = cross_markers(fast_line, slow_line)
    return {"fast": fast_line, "slow": slow_line, "cross_up": up, "cross_down": down}


def ma_cross(close, fast=9, slow=21):
    return _cross(_sma(close, fast), _sma(close, slow))


def ema_cross(close, fast=9, slow=21):
    return _cross(_ema(close, fast), _ema(close, slow))


def ma_ema_cross(close, ma_period=10, ema_period=10):
    return _cross(_sma(close, ma_period), _ema(close, ema_period))


GUPPY_SHORT = (3, 5, 8, 10, 12, 15)
GUPPY_LONG = (30, 35, 40, 45, 50, 60)


def guppy(close, s1=3, s2=5, s3=8, s4=10, s5=12, s6=15, l1=30, l2=35, l3=40, l4=45, l5=50, l6=60):
    periods = {"s1": s1, "s2": s2, "s3": s3, "s4": s4, "s5": s5, "s6": s6,
               "l1": l1, "l2": l2, "l3": l3, "l4": l4, "l5": l5, "l6": l6}
    return {key: _ema(close, p) for key, p in periods.items()}
