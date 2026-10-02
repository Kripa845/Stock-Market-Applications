"""Shared building blocks for the indicator library.

Every series is a plain list (oldest first) the same length as the input.
``None`` marks "not enough data yet" and is never replaced by 0. Helpers
propagate ``None``: a window or combination that touches a ``None`` yields
``None``. Smoothed series (EMA, Wilder/RMA) are seeded with the simple average
of their first N values, skip leading ``None`` values, and restart seeding if a
``None`` appears later.
"""

from math import sqrt


def to_floats(values):
    return [None if v is None else float(v) for v in values]


def check_period(n, minimum=1):
    if n is None or int(n) != n or n < minimum:
        raise ValueError(f"period must be an integer >= {minimum}, got {n!r}")
    return int(n)


def combine(fn, *series):
    """Element-wise ``fn`` over aligned series; None if any input is None or fn divides by zero."""
    out = []
    for values in zip(*series):
        if any(v is None for v in values):
            out.append(None)
            continue
        try:
            out.append(fn(*values))
        except ZeroDivisionError:
            out.append(None)
    return out


def rolling(values, n, fn):
    """``fn(window)`` for each full window of ``n`` values containing no None."""
    n = check_period(n)
    out = [None] * len(values)
    for i in range(n - 1, len(values)):
        window = values[i - n + 1:i + 1]
        if None not in window:
            try:
                out[i] = fn(window)
            except ZeroDivisionError:
                pass
    return out


def rolling_multi(series, n, fn):
    """Like ``rolling`` but ``fn`` receives one window per input series."""
    n = check_period(n)
    length = len(series[0]) if series else 0
    out = [None] * length
    for i in range(n - 1, length):
        windows = [s[i - n + 1:i + 1] for s in series]
        if all(None not in w for w in windows):
            try:
                out[i] = fn(*windows)
            except ZeroDivisionError:
                pass
    return out


def seeded(values, n, step):
    """Recursive smoother seeded with the SMA of the first ``n`` values: new = step(prev, value)."""
    n = check_period(n)
    out = [None] * len(values)
    seed, previous = [], None
    for i, value in enumerate(values):
        if value is None:
            seed, previous = [], None
            continue
        if previous is None:
            seed.append(value)
            if len(seed) == n:
                previous = sum(seed) / n
                out[i] = previous
            continue
        previous = step(previous, value)
        out[i] = previous
    return out


def sma(values, n):
    return rolling(values, n, lambda w: sum(w) / len(w))


def ema(values, n):
    n = check_period(n)
    k = 2 / (n + 1)
    return seeded(values, n, lambda prev, x: x * k + prev * (1 - k))


def rma(values, n):
    """Wilder smoothing (also called SMMA / RMA)."""
    n = check_period(n)
    return seeded(values, n, lambda prev, x: (prev * (n - 1) + x) / n)


def wma(values, n):
    """Linearly weighted: newest weight n, oldest 1."""
    n = check_period(n)
    denominator = n * (n + 1) / 2
    return rolling(values, n, lambda w: sum(x * (j + 1) for j, x in enumerate(w)) / denominator)


def highest(values, n):
    return rolling(values, n, max)


def lowest(values, n):
    return rolling(values, n, min)


def rolling_sum(values, n):
    return rolling(values, n, sum)


def population_std(window):
    mean = sum(window) / len(window)
    return sqrt(sum((x - mean) ** 2 for x in window) / len(window))


def pstdev(values, n):
    return rolling(values, n, population_std)


def lag(values, k):
    """Value from ``k`` bars ago (k > 0) or ``-k`` bars ahead (k < 0); None outside the series."""
    out = [None] * len(values)
    for i in range(len(values)):
        j = i - k
        if 0 <= j < len(values):
            out[i] = values[j]
    return out


def change(values, k=1):
    return combine(lambda a, b: a - b, values, lag(values, k))


def true_range(high, low, close):
    """max(H - L, |H - prevC|, |L - prevC|); the first bar has no previous close, so None."""
    return combine(lambda h, l, pc: max(h - l, abs(h - pc), abs(l - pc)), high, low, lag(close, 1))


def atr(high, low, close, n=14):
    return rma(true_range(high, low, close), n)


def linear_fit(window):
    """Least-squares line through the window with x = 1..N; returns (intercept a, slope b)."""
    n = len(window)
    sx = n * (n + 1) / 2
    sxx = n * (n + 1) * (2 * n + 1) / 6
    sy = sum(window)
    sxy = sum((j + 1) * y for j, y in enumerate(window))
    slope = (n * sxy - sx * sy) / (n * sxx - sx * sx)
    return (sy - slope * sx) / n, slope


def pearson(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    return sxy / sqrt(sxx * syy)


def cross_markers(fast, slow):
    """Marker series at the fast line's value on the bar where it crosses above (up) / below (down)."""
    up, down = [None] * len(fast), [None] * len(fast)
    for i in range(1, len(fast)):
        f0, s0, f1, s1 = fast[i - 1], slow[i - 1], fast[i], slow[i]
        if None in (f0, s0, f1, s1):
            continue
        if f0 <= s0 and f1 > s1:
            up[i] = f1
        elif f0 >= s0 and f1 < s1:
            down[i] = f1
    return up, down
