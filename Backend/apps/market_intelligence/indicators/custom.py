"""Standard versions of indicators NepseAlpha offers under its own names.

NepseAlpha's exact formulas are unpublished; these follow the commonly published definitions
and are labelled "standard version" in the registry.
"""

from .core import atr as _atr, check_period, combine, ema, lag, pstdev, sma
from .momentum import rsi


def inside_bar(high, low):
    """Marker at the bar's high when H < prevH and L > prevL."""
    return [
        high[i] if i and high[i] < high[i - 1] and low[i] > low[i - 1] else None for i in range(len(high))
    ]


def ut_bot(high, low, close, key=1, atr_period=10):
    """ATR trailing stop (key * ATR) that flips when the close crosses it; buy/sell markers on flips."""
    atr_values = _atr(high, low, close, atr_period)
    stop, buy, sell = [None] * len(close), [None] * len(close), [None] * len(close)
    prev_stop = None
    for i, c in enumerate(close):
        if atr_values[i] is None:
            prev_stop = None
            continue
        loss = key * atr_values[i]
        if prev_stop is None:
            current = c - loss
        else:
            prev_close = close[i - 1]
            if c > prev_stop and prev_close > prev_stop:
                current = max(prev_stop, c - loss)
            elif c < prev_stop and prev_close < prev_stop:
                current = min(prev_stop, c + loss)
            elif c > prev_stop:
                current = c - loss
            else:
                current = c + loss
            if prev_close <= prev_stop and c > prev_stop:
                buy[i] = current
            elif prev_close >= prev_stop and c < prev_stop:
                sell[i] = current
        stop[i] = prev_stop = current
    return {"stop": stop, "buy": buy, "sell": sell}


def zero_lag_ema(values, period):
    lag_bars = (check_period(period) - 1) // 2
    adjusted = combine(lambda x, old: x + (x - old), values, lag(values, lag_bars))
    return ema(adjusted, period)


def zero_lag_macd(close, fast=12, slow=26, signal=9):
    line = combine(lambda f, s: f - s, zero_lag_ema(close, fast), zero_lag_ema(close, slow))
    signal_line = zero_lag_ema(line, signal)
    return {"macd": line, "signal": signal_line, "histogram": combine(lambda m, s: m - s, line, signal_line)}


def tdi(close, rsi_period=13, price_period=2, signal_period=7, base_period=34, band_multiplier=1.6185):
    """Traders Dynamic Index: smoothed RSI lines with volatility bands (population stdev of RSI)."""
    r = rsi(close, rsi_period)
    base, deviation = sma(r, base_period), pstdev(r, base_period)
    return {
        "price": sma(r, price_period),
        "signal": sma(r, signal_period),
        "base": base,
        "upper": combine(lambda b, d: b + band_multiplier * d, base, deviation),
        "lower": combine(lambda b, d: b - band_multiplier * d, base, deviation),
    }


def weinstein_stage(close, ma_period=150, slope_period=5, flat_pct=0.5):
    """Stage 1-4 from close vs the ~30-week MA (150 daily bars) and that MA's slope.

    Rising MA with close above -> 2; falling MA with close below -> 4. Otherwise the stage is
    a base (1) after a decline or a top (3) after an advance; mixed signals keep the last stage.
    """
    ma = sma(close, ma_period)
    slope = combine(lambda cur, prev: (cur - prev) / prev * 100, ma, lag(ma, slope_period))
    out, last = [None] * len(close), None
    for i, (c, m, s) in enumerate(zip(close, ma, slope)):
        if m is None or s is None:
            continue
        if s > flat_pct and c > m:
            stage = 2
        elif s < -flat_pct and c < m:
            stage = 4
        elif abs(s) <= flat_pct:
            stage = 1 if last in (4, 1, None) else 3
        else:
            stage = last or (2 if c > m else 4)
        out[i] = last = float(stage)
    return out
