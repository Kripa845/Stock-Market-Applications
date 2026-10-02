"""Price transforms and levels."""

from datetime import timedelta

from .core import check_period


def average_price(open_, high, low, close):
    return [(o + h + l + c) / 4 for o, h, l, c in zip(open_, high, low, close)]


def median_price(high, low):
    return [(h + l) / 2 for h, l in zip(high, low)]


def typical_price(high, low, close):
    return [(h + l + c) / 3 for h, l, c in zip(high, low, close)]


def _period_key(day, timeframe):
    if timeframe == "D":
        return day
    if timeframe == "W":
        year, week, _ = day.isocalendar()
        return (year, week)
    if timeframe == "M":
        return (day.year, day.month)
    raise ValueError("timeframe must be D, W or M")


def pivot_points(high, low, close, dates, timeframe="W"):
    """Standard pivots from the previous completed period's H, L, C (D = previous bar's day)."""
    keys = [_period_key(d, timeframe) for d in dates]
    groups = {}
    for key, h, l, c in zip(keys, high, low, close):
        if key in groups:
            g = groups[key]
            g["h"], g["l"], g["c"] = max(g["h"], h), min(g["l"], l), c
        else:
            groups[key] = {"h": h, "l": l, "c": c}
    order = list(groups)
    previous = {order[i]: groups[order[i - 1]] for i in range(1, len(order))}
    names = ("p", "r1", "s1", "r2", "s2", "r3", "s3")
    out = {name: [None] * len(dates) for name in names}
    for i, key in enumerate(keys):
        g = previous.get(key)
        if g is None:
            continue
        h, l, c = g["h"], g["l"], g["c"]
        p = (h + l + c) / 3
        values = (p, 2 * p - l, 2 * p - h, p + (h - l), p - (h - l), h + 2 * (p - l), l - 2 * (h - p))
        for name, value in zip(names, values):
            out[name][i] = value
    return out


def week_52_high_low(high, low, dates, weeks=52):
    """Highest high / lowest low over the last ``weeks`` calendar weeks; None until that much history exists."""
    weeks = check_period(weeks)
    span = timedelta(weeks=weeks)
    upper, lower = [None] * len(dates), [None] * len(dates)
    start = 0
    for i, day in enumerate(dates):
        if dates[0] > day - span:
            continue
        while dates[start] <= day - span:
            start += 1
        upper[i] = max(high[start:i + 1])
        lower[i] = min(low[start:i + 1])
    return {"high": upper, "low": lower}


def fractals(high, low, wing=2):
    """Williams fractals: a high (low) above (below) ``wing`` bars on each side. Needs ``wing`` later bars."""
    wing = check_period(wing)
    up, down = [None] * len(high), [None] * len(high)
    for i in range(wing, len(high) - wing):
        neighbours = [j for k in range(1, wing + 1) for j in (i - k, i + k)]
        if all(high[i] > high[j] for j in neighbours):
            up[i] = high[i]
        if all(low[i] < low[j] for j in neighbours):
            down[i] = low[i]
    return {"up": up, "down": down}
