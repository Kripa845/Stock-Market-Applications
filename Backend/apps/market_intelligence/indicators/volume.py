"""Volume-based indicators."""

from .core import check_period, combine, ema, lag, rolling_multi, sma


def volume_bars(open_, close, volume):
    """The volume histogram plus a direction series (1 up / -1 down) used to colour it."""
    return {
        "volume": [float(v) for v in volume],
        "direction": [1 if c >= o else -1 for o, c in zip(open_, close)],
    }


def volume_oscillator(volume, fast=5, slow=10):
    return combine(lambda f, s: (f - s) / s * 100, ema(volume, fast), ema(volume, slow))


def _signed_volume(close, volume):
    out = [None] * len(close)
    for i in range(1, len(close)):
        v = float(volume[i] or 0)
        out[i] = v if close[i] > close[i - 1] else -v if close[i] < close[i - 1] else 0.0
    return out


def obv(close, volume):
    if not close:
        return []
    out, total = [0.0], 0.0
    for v in _signed_volume(close, volume)[1:]:
        total += v
        out.append(total)
    return out


def net_volume(close, volume):
    return _signed_volume(close, volume)


def clv(high, low, close):
    """Close location value; 0 when the bar has no range."""
    return [((c - l) - (h - c)) / (h - l) if h != l else 0.0 for h, l, c in zip(high, low, close)]


def accumulation_distribution(high, low, close, volume):
    out, total = [], 0.0
    for value, v in zip(clv(high, low, close), volume):
        total += value * float(v or 0)
        out.append(total)
    return out


def chaikin_money_flow(high, low, close, volume, period=20):
    flow = [value * float(v or 0) for value, v in zip(clv(high, low, close), volume)]
    return rolling_multi([flow, [float(v or 0) for v in volume]], period, lambda f, v: sum(f) / sum(v))


def chaikin_oscillator(high, low, close, volume, fast=3, slow=10):
    ad = accumulation_distribution(high, low, close, volume)
    return combine(lambda f, s: f - s, ema(ad, fast), ema(ad, slow))


def money_flow_index(high, low, close, volume, period=14):
    """MFI = 100 - 100 / (1 + positive / negative); 100 when there is no negative flow."""
    n = check_period(period)
    tp = [(h + l + c) / 3 for h, l, c in zip(high, low, close)]
    positive, negative = [None] * len(tp), [None] * len(tp)
    for i in range(1, len(tp)):
        flow = tp[i] * float(volume[i] or 0)
        positive[i] = flow if tp[i] > tp[i - 1] else 0.0
        negative[i] = flow if tp[i] < tp[i - 1] else 0.0

    def value(pos, neg):
        p, q = sum(pos), sum(neg)
        if q == 0:
            return 100.0 if p > 0 else None
        return 100 - 100 / (1 + p / q)

    return rolling_multi([positive, negative], n, value)


def ease_of_movement(high, low, volume, period=14, scale=10000):
    """Distance / box ratio, smoothed with SMA(N). 0 for a bar with no range; None when volume is 0."""
    raw = [None] * len(high)
    for i in range(1, len(high)):
        distance = (high[i] + low[i]) / 2 - (high[i - 1] + low[i - 1]) / 2
        v = float(volume[i] or 0)
        span = high[i] - low[i]
        if span == 0:
            raw[i] = 0.0
        elif v:
            raw[i] = distance / ((v / scale) / span)
    return sma(raw, period)


def force_index(close, volume, period=13):
    raw = combine(lambda c, p, v: (c - p) * float(v), close, lag(close, 1), volume)
    return ema(raw, period)


def klinger(high, low, close, volume, fast=34, slow=55, signal=13):
    n = len(close)
    vf = [None] * n
    hlc = [h + l + c for h, l, c in zip(high, low, close)]
    prev_trend = prev_dm = cm = None
    for i in range(1, n):
        trend = 1 if hlc[i] > hlc[i - 1] else -1
        dm = high[i] - low[i]
        if prev_trend is None:
            cm = dm + (high[i - 1] - low[i - 1])
        elif trend == prev_trend:
            cm = cm + dm
        else:
            cm = prev_dm + dm
        vf[i] = float(volume[i] or 0) * abs(2 * (dm / cm - 1)) * trend * 100 if cm else 0.0
        prev_trend, prev_dm = trend, dm
    ko = combine(lambda f, s: f - s, ema(vf, fast), ema(vf, slow))
    return {"ko": ko, "signal": ema(ko, signal)}


def price_volume_trend(close, volume):
    if not close:
        return []
    out = [0.0]
    for i in range(1, len(close)):
        prev = close[i - 1]
        out.append(out[-1] + (float(volume[i] or 0) * (close[i] - prev) / prev if prev else 0.0))
    return out


def vwap_anchored(high, low, close, volume):
    """Cumulative sum(TP * V) / sum(V) from the first bar given (the start of the selected range)."""
    out, pv, vol = [], 0.0, 0.0
    for h, l, c, v in zip(high, low, close, volume):
        v = float(v or 0)
        pv += (h + l + c) / 3 * v
        vol += v
        out.append(pv / vol if vol else None)
    return out


def vwap_rolling(high, low, close, volume, period=20):
    tp = [(h + l + c) / 3 for h, l, c in zip(high, low, close)]
    vols = [float(v or 0) for v in volume]
    return rolling_multi([tp, vols], period, lambda t, v: sum(a * b for a, b in zip(t, v)) / sum(v))


def volume_profile(high, low, volume, rows=24, value_area=70):
    """Spread each bar's volume across price rows between its low and high.

    Returns constant POC / value-area lines over the range, plus the row histogram
    under ``extra``. With daily bars this is coarse; it is designed for intraday data.
    """
    rows = check_period(rows, 2)
    n = len(high)
    empty = {"poc": [None] * n, "vah": [None] * n, "val": [None] * n, "extra": {"rows": []}}
    if not n:
        return empty
    top, bottom = max(high), min(low)
    if top == bottom:
        return empty
    size = (top - bottom) / rows
    bins = [0.0] * rows
    for h, l, v in zip(high, low, volume):
        v = float(v or 0)
        if not v:
            continue
        if h == l:
            bins[min(int((h - bottom) / size), rows - 1)] += v
            continue
        for r in range(rows):
            lo, hi = bottom + r * size, bottom + (r + 1) * size
            overlap = min(hi, h) - max(lo, l)
            if overlap > 0:
                bins[r] += v * overlap / (h - l)
    total = sum(bins)
    if not total:
        return empty
    poc = max(range(rows), key=lambda r: bins[r])
    low_row = high_row = poc
    covered = bins[poc]
    while covered < total * value_area / 100 and (low_row > 0 or high_row < rows - 1):
        below = bins[low_row - 1] if low_row > 0 else -1
        above = bins[high_row + 1] if high_row < rows - 1 else -1
        if above >= below:
            high_row += 1
            covered += bins[high_row]
        else:
            low_row -= 1
            covered += bins[low_row]
    center = bottom + (poc + 0.5) * size
    return {
        "poc": [center] * n,
        "vah": [bottom + (high_row + 1) * size] * n,
        "val": [bottom + low_row * size] * n,
        "extra": {"rows": [
            {"low": bottom + r * size, "high": bottom + (r + 1) * size, "volume": bins[r]} for r in range(rows)
        ]},
    }
