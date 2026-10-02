"""Momentum indicators and oscillators (drawn in panels)."""

from math import log

from .core import (
    change, check_period, combine, ema, highest, lag, lowest, rma, rolling, rolling_multi, sma, wma,
)


def macd(close, fast=12, slow=26, signal=9):
    line = combine(lambda f, s: f - s, ema(close, fast), ema(close, slow))
    signal_line = ema(line, signal)
    return {
        "macd": line,
        "signal": signal_line,
        "histogram": combine(lambda m, s: m - s, line, signal_line),
    }


def rsi(close, period=14):
    """Wilder RSI; 100 when the average loss is 0."""
    changes = change(close)
    gains = [None if c is None else max(c, 0.0) for c in changes]
    losses = [None if c is None else max(-c, 0.0) for c in changes]
    avg_gain, avg_loss = rma(gains, period), rma(losses, period)
    return [
        None if g is None or l is None else (100.0 if l == 0 else 100 - 100 / (1 + g / l))
        for g, l in zip(avg_gain, avg_loss)
    ]


def stochastic(high, low, close, k_period=14, d_period=3):
    k = combine(lambda c, hh, ll: (c - ll) / (hh - ll) * 100, close, highest(high, k_period), lowest(low, k_period))
    return {"k": k, "d": sma(k, d_period)}


def stoch_rsi(close, rsi_period=14, stoch_period=14):
    """(RSI - lowest RSI) / (highest RSI - lowest RSI), on a 0-1 scale as specified."""
    r = rsi(close, rsi_period)
    return combine(lambda x, hh, ll: (x - ll) / (hh - ll), r, highest(r, stoch_period), lowest(r, stoch_period))


def williams_r(high, low, close, period=14):
    return combine(lambda c, hh, ll: (hh - c) / (hh - ll) * -100, close, highest(high, period), lowest(low, period))


def typical(high, low, close):
    return combine(lambda h, l, c: (h + l + c) / 3, high, low, close)


def cci(high, low, close, period=20):
    def value(window):
        mean = sum(window) / len(window)
        mad = sum(abs(x - mean) for x in window) / len(window)
        return (window[-1] - mean) / (0.015 * mad)
    return rolling(typical(high, low, close), period, value)


def momentum(close, period=10):
    return change(close, check_period(period))


def roc(close, period=9):
    return combine(lambda c, p: (c - p) / p * 100, close, lag(close, check_period(period)))


def price_oscillator(close, fast=12, slow=26):
    f, s = ema(close, fast), ema(close, slow)
    return {
        "po": combine(lambda a, b: a - b, f, s),
        "ppo": combine(lambda a, b: (a - b) / b * 100, f, s),
    }


def _median(high, low):
    return combine(lambda h, l: (h + l) / 2, high, low)


def awesome(high, low, fast=5, slow=34):
    median = _median(high, low)
    return combine(lambda a, b: a - b, sma(median, fast), sma(median, slow))


def accelerator(high, low, fast=5, slow=34, signal=5):
    ao = awesome(high, low, fast, slow)
    return combine(lambda a, b: a - b, ao, sma(ao, signal))


def balance_of_power(open_, high, low, close):
    return combine(lambda o, h, l, c: (c - o) / (h - l), open_, high, low, close)


def cmo(close, period=9):
    def value(window):
        up = sum(x for x in window if x > 0)
        down = -sum(x for x in window if x < 0)
        return 100 * (up - down) / (up + down)
    return rolling(change(close), period, value)


def streak(close):
    """Consecutive up (+1, +2, ...) or down (-1, -2, ...) closes; 0 when unchanged."""
    out = [0.0] if close else []
    for i in range(1, len(close)):
        prev = out[-1]
        if close[i] > close[i - 1]:
            out.append(prev + 1 if prev > 0 else 1.0)
        elif close[i] < close[i - 1]:
            out.append(prev - 1 if prev < 0 else -1.0)
        else:
            out.append(0.0)
    return out


def percent_rank(values, period):
    """Percent of the previous ``period`` values strictly below the current one (Connors' definition)."""
    n = check_period(period)
    out = [None] * len(values)
    for i in range(n, len(values)):
        window = values[i - n:i]
        if values[i] is None or None in window:
            continue
        out[i] = 100 * sum(1 for x in window if x < values[i]) / n
    return out


def connors_rsi(close, rsi_period=3, streak_period=2, rank_period=100):
    one_day = combine(lambda c, p: (c - p) / p * 100, close, lag(close, 1))
    return combine(
        lambda a, b, c: (a + b + c) / 3,
        rsi(close, rsi_period), rsi(streak(close), streak_period), percent_rank(one_day, rank_period),
    )


def coppock(close, wma_period=10, long_roc=14, short_roc=11):
    return wma(combine(lambda a, b: a + b, roc(close, long_roc), roc(close, short_roc)), wma_period)


def dpo(close, period=20):
    """Close shifted back (N/2 + 1) bars minus SMA(N)."""
    n = check_period(period)
    return combine(lambda shifted, avg: shifted - avg, lag(close, n // 2 + 1), sma(close, n))


def fisher(high, low, period=9):
    """Ehlers Fisher Transform using the median price and HH/LL of highs/lows over N."""
    n = check_period(period)
    median = _median(high, low)
    hh, ll = highest(high, n), lowest(low, n)
    fish, trigger = [None] * len(high), [None] * len(high)
    prev_x = prev_f = 0.0
    for i in range(len(high)):
        if None in (median[i], hh[i], ll[i]):
            continue
        span = hh[i] - ll[i]
        ratio = (median[i] - ll[i]) / span if span else 0.5
        x = max(-0.999, min(0.999, 0.66 * (ratio - 0.5) + 0.67 * prev_x))
        f = 0.5 * log((1 + x) / (1 - x)) + 0.5 * prev_f
        fish[i], trigger[i] = f, prev_f
        prev_x, prev_f = x, f
    return {"fisher": fish, "trigger": trigger}


def kst(close, roc1=10, roc2=15, roc3=20, roc4=30, sma1=10, sma2=10, sma3=10, sma4=15, signal=9):
    parts = [sma(roc(close, r), s) for r, s in ((roc1, sma1), (roc2, sma2), (roc3, sma3), (roc4, sma4))]
    line = combine(lambda a, b, c, d: a + 2 * b + 3 * c + 4 * d, *parts)
    return {"kst": line, "signal": sma(line, signal)}


def _swma(values):
    """(x + 2*x[1] + 2*x[2] + x[3]) / 6 over the last four bars."""
    return combine(lambda a, b, c, d: (a + 2 * b + 2 * c + d) / 6, values, lag(values, 1), lag(values, 2), lag(values, 3))


def rvi(open_, high, low, close, period=10):
    """Relative Vigor Index; the signal line is the standard 4-bar weighted average of RVI."""
    num = _swma(combine(lambda c, o: c - o, close, open_))
    den = _swma(combine(lambda h, l: h - l, high, low))
    line = combine(lambda a, b: a / b, sma(num, period), sma(den, period))
    return {"rvi": line, "signal": _swma(line)}


def trix(close, period=15):
    e3 = ema(ema(ema(close, period), period), period)
    return combine(lambda cur, prev: (cur - prev) / prev * 100, e3, lag(e3, 1))


def tsi(close, long=25, short=13, signal=13):
    """True Strength Index; the signal line (EMA of TSI) is the usual companion line."""
    dc = change(close)
    num = ema(ema(dc, long), short)
    den = ema(ema([None if x is None else abs(x) for x in dc], long), short)
    line = combine(lambda a, b: 100 * a / b, num, den)
    return {"tsi": line, "signal": ema(line, signal)}


def smi_ergodic(close, long=20, short=5, signal=5):
    result = tsi(close, long, short, signal)
    return {"smi": result["tsi"], "signal": result["signal"]}


def ultimate(high, low, close, p1=7, p2=14, p3=28):
    prev_close = lag(close, 1)
    bp = combine(lambda c, l, pc: c - min(l, pc), close, low, prev_close)
    tr = combine(lambda h, l, pc: max(h, pc) - min(l, pc), high, low, prev_close)
    avg = [rolling_multi([bp, tr], p, lambda b, t: sum(b) / sum(t)) for p in (p1, p2, p3)]
    return combine(lambda a, b, c: 100 * (4 * a + 2 * b + c) / 7, *avg)
