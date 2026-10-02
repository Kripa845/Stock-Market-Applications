"""Volatility measures, bands and channels. "Standard deviation" is the population form throughout."""

from math import log, sqrt

from .core import (
    atr as _atr, check_period, combine, ema, highest, lag, linear_fit, lowest, pstdev, rolling, sma,
)
from .moving_averages import lsma


def atr(high, low, close, period=14):
    return _atr(high, low, close, period)


def bollinger(close, period=20, multiplier=2):
    middle, deviation = sma(close, period), pstdev(close, period)
    return {
        "upper": combine(lambda m, d: m + multiplier * d, middle, deviation),
        "middle": middle,
        "lower": combine(lambda m, d: m - multiplier * d, middle, deviation),
    }


def bollinger_percent_b(close, period=20, multiplier=2):
    bands = bollinger(close, period, multiplier)
    return combine(lambda c, u, l: (c - l) / (u - l), close, bands["upper"], bands["lower"])


def bollinger_width(close, period=20, multiplier=2):
    bands = bollinger(close, period, multiplier)
    return combine(lambda u, l, m: (u - l) / m, bands["upper"], bands["lower"], bands["middle"])


def keltner(high, low, close, ema_period=20, multiplier=2, atr_period=10):
    middle, atr_values = ema(close, ema_period), _atr(high, low, close, atr_period)
    return {
        "upper": combine(lambda m, a: m + multiplier * a, middle, atr_values),
        "middle": middle,
        "lower": combine(lambda m, a: m - multiplier * a, middle, atr_values),
    }


def donchian(high, low, period=20):
    upper, lower = highest(high, period), lowest(low, period)
    return {"upper": upper, "middle": combine(lambda u, l: (u + l) / 2, upper, lower), "lower": lower}


def envelopes(close, period=20, percent=5):
    middle = sma(close, period)
    return {
        "upper": [None if m is None else m * (1 + percent / 100) for m in middle],
        "middle": middle,
        "lower": [None if m is None else m * (1 - percent / 100) for m in middle],
    }


def std_dev(close, period=20):
    return pstdev(close, period)


def _standard_error(window):
    n = len(window)
    a, b = linear_fit(window)
    residuals = sum((y - (a + b * (j + 1))) ** 2 for j, y in enumerate(window))
    return sqrt(residuals / (n - 2))


def standard_error(close, period=20):
    return rolling(close, check_period(period, 3), _standard_error)


def standard_error_bands(close, period=21, multiplier=2):
    curve, se = lsma(close, period), standard_error(close, period)
    return {
        "upper": combine(lambda c, e: c + multiplier * e, curve, se),
        "middle": curve,
        "lower": combine(lambda c, e: c - multiplier * e, curve, se),
    }


def chaikin_volatility(high, low, ema_period=10, roc_period=10):
    smoothed = ema(combine(lambda h, l: h - l, high, low), ema_period)
    return combine(lambda cur, prev: 100 * (cur - prev) / prev, smoothed, lag(smoothed, roc_period))


def log_returns(close):
    return combine(lambda c, p: log(c / p) if c > 0 and p > 0 else None, close, lag(close, 1))


def historical_volatility(close, period=20, trading_days=240):
    """Annualised population standard deviation of ln(C / prevC)."""
    return [None if s is None else s * sqrt(trading_days) for s in pstdev(log_returns(close), period)]


def zero_trend_volatility(close, period=20, trading_days=240):
    """Close-to-close volatility assuming zero mean return: sqrt(mean(r^2)) annualised."""
    return rolling(log_returns(close), period, lambda w: sqrt(sum(r * r for r in w) / len(w)) * sqrt(trading_days))


def garman_klass(open_, high, low, close, period=20, trading_days=240):
    def term(o, h, l, c):
        if min(o, h, l, c) <= 0:
            return None
        return 0.5 * log(h / l) ** 2 - (2 * log(2) - 1) * log(c / o) ** 2

    terms = combine(term, open_, high, low, close)

    def value(window):
        variance = sum(window) / len(window)
        return sqrt(variance) * sqrt(trading_days) if variance >= 0 else None

    return rolling(terms, period, value)


def relative_volatility_index(close, std_period=10, smooth_period=14):
    deviation, prev_close = pstdev(close, std_period), lag(close, 1)
    up = combine(lambda s, c, p: s if c > p else 0.0, deviation, close, prev_close)
    down = combine(lambda s, c, p: s if c < p else 0.0, deviation, close, prev_close)
    return combine(lambda u, d: 100 * u / (u + d), ema(up, smooth_period), ema(down, smooth_period))
