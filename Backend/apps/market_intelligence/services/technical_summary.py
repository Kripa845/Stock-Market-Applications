"""
Technical summary for one instrument (the NEPSE index or a tracked company).

Indicator values come from the project's indicator library (apps.market_intelligence.indicators);
this module only picks the latest value of each and turns it into Buy / Sell / Neutral.
An indicator without enough history is returned with value None and signal None, never guessed.

Stored company prices are not adjusted for bonus / right shares.  Sessions where ShareSansar's
adjusted % differs from close-to-close (the services.movers rule) are corporate actions; the
prices before them are back-adjusted by the factor that adjusted % implies, so no artificial
drop reaches the indicators.  Where no adjusted % exists and close-to-close jumps beyond
movers.CORPORATE_ACTION_PCT, the factor is unknown and only later bars are used.
Not investment advice.
"""

from decimal import Decimal

from apps.market_data.models import DailyPrice
from apps.market_data.services import movers
from apps.market_intelligence.indicators import momentum, price, volatility
from apps.market_intelligence.indicators import moving_averages as ma
from apps.market_indices.models import IndexDaily

BUY, SELL, NEUTRAL = "Buy", "Sell", "Neutral"

RSI_OVERSOLD, RSI_OVERBOUGHT = 30, 70
STOCH_OVERSOLD, STOCH_OVERBOUGHT = 20, 80
# Overall signal from (buy - sell) / voting indicators.
STRONG_THRESHOLD, THRESHOLD = Decimal("0.5"), Decimal("0.1")

DISCLAIMER = "Computed from stored daily prices. Not investment advice."


# ----------------------------------------------------------------------
# History
# ----------------------------------------------------------------------

# A factor outside this range is not a bonus / right adjustment: treat it as unknown.
MIN_FACTOR, MAX_FACTOR = Decimal("0.2"), Decimal("5")


def adjust_for_corporate_actions(bars):
    """
    (adjusted bars, cutoff index, adjusted session dates) for daily company bars, oldest first.

    On a corporate-action session the exchange's previous close is close / (1 + adjusted % / 100);
    every earlier bar is multiplied by that previous close / stored previous close.  Bars before a
    session with no usable factor are dropped (cutoff).  Inputs are not modified.
    """
    factors, cutoff = [Decimal(1)] * len(bars), 0
    for i in range(1, len(bars)):
        previous, current = Decimal(str(bars[i - 1]["close"])), Decimal(str(bars[i]["close"]))
        if not previous:
            continue
        close_to_close = (current - previous) * 100 / previous
        source = bars[i].get("source_change_pct")
        if source is None:
            if abs(close_to_close) > movers.CORPORATE_ACTION_PCT:
                cutoff = i
            continue
        source = Decimal(str(source))
        if abs(source - close_to_close) <= movers.ADJUSTMENT_TOLERANCE_PCT:
            continue
        factor = current / (1 + source / 100) / previous
        if MIN_FACTOR <= factor <= MAX_FACTOR:
            factors[i] = factor
        else:
            cutoff = i

    adjusted, running = [], Decimal(1)
    for i in range(len(bars) - 1, cutoff - 1, -1):
        bar = bars[i]
        adjusted.append({**bar, **{k: Decimal(str(bar[k])) * running for k in ("open", "high", "low", "close")}})
        running *= factors[i]
    adjusted.reverse()
    adjusted_dates = [bars[i]["date"] for i in range(max(cutoff, 1), len(bars)) if factors[i] != 1]
    return adjusted, cutoff, adjusted_dates


def index_bars(code="NEPSE"):
    rows = (
        IndexDaily.objects.filter(index__code=code, source="crawled", open__isnull=False,
                                  high__isnull=False, low__isnull=False)
        .order_by("date").values("date", "open", "high", "low", "close")
    )
    return list(rows)


def company_bars(company):
    rows = (
        DailyPrice.objects.filter(company=company, source=movers.PRICE_SOURCE)
        .order_by("date").values("date", "open", "high", "low", "close", "source_change_pct")
    )
    return list(rows)


# ----------------------------------------------------------------------
# Signals (pure)
# ----------------------------------------------------------------------

def _last(series):
    return series[-1] if series else None


def _round(value, places=2):
    return None if value is None else round(value, places)


def level_signal(value, low, high):
    """Oscillator: below ``low`` = Buy (oversold), above ``high`` = Sell (overbought)."""
    if value is None:
        return None
    return BUY if value < low else SELL if value > high else NEUTRAL


def above_below_signal(value, reference):
    """Price / line above the reference = Buy, below = Sell."""
    if value is None or reference is None:
        return None
    return BUY if value > reference else SELL if value < reference else NEUTRAL


def band_signal(close, lower, upper):
    """Close below the lower band = Buy, above the upper band = Sell."""
    if None in (close, lower, upper):
        return None
    return BUY if close < lower else SELL if close > upper else NEUTRAL


def overall_signal(buy, sell, neutral):
    total = buy + sell + neutral
    if total == 0:
        return None
    score = Decimal(buy - sell) / total
    if score >= STRONG_THRESHOLD:
        return "Strong Buy"
    if score >= THRESHOLD:
        return BUY
    if score <= -STRONG_THRESHOLD:
        return "Strong Sell"
    if score <= -THRESHOLD:
        return SELL
    return NEUTRAL


def technical_summary(bars):
    """Indicators, pivots and the summary for daily ``bars`` (oldest first)."""
    closes = [float(b["close"]) for b in bars]
    highs = [float(b["high"]) for b in bars]
    lows = [float(b["low"]) for b in bars]
    dates = [b["date"] for b in bars]
    close = _last(closes)

    indicators = []

    def add(key, name, value, verdict, votes=True, **values):
        indicators.append({
            "key": key, "name": name, "value": _round(value), "signal": verdict,
            "votes": votes, "values": {k: _round(v) for k, v in values.items()},
        })

    rsi = _last(momentum.rsi(closes, 14))
    add("rsi_14", "RSI (14)", rsi, level_signal(rsi, RSI_OVERSOLD, RSI_OVERBOUGHT))

    macd = momentum.macd(closes, 12, 26, 9)
    line, signal_line = _last(macd["macd"]), _last(macd["signal"])
    add("macd", "MACD (12,26,9)", line, above_below_signal(line, signal_line),
        signal=signal_line, histogram=_last(macd["histogram"]))

    stoch = momentum.stochastic(highs, lows, closes, 14, 3, smooth_k=3)
    k = _last(stoch["k"])
    add("stoch", "Stochastic (14,3,3)", k, level_signal(k, STOCH_OVERSOLD, STOCH_OVERBOUGHT), d=_last(stoch["d"]))

    bands = volatility.bollinger(closes, 20, 2)
    upper, middle, lower = _last(bands["upper"]), _last(bands["middle"]), _last(bands["lower"])
    add("bollinger", "Bollinger Bands (20,2)", middle, band_signal(close, lower, upper),
        upper=upper, lower=lower)

    atr = _last(volatility.atr(highs, lows, closes, 14))
    # Volatility has no direction: shown, but not counted in the summary.
    add("atr_14", "ATR (14)", atr, None if atr is None else NEUTRAL, votes=False)

    for period in (20, 50, 200):
        value = _last(ma.sma(closes, period))
        add(f"sma_{period}", f"SMA ({period})", value, above_below_signal(close, value))
    for period in (20, 50):
        value = _last(ma.ema(closes, period))
        add(f"ema_{period}", f"EMA ({period})", value, above_below_signal(close, value))

    voting = [i["signal"] for i in indicators if i["votes"] and i["signal"] is not None]
    counts = {name: voting.count(label) for name, label in (("buy", BUY), ("neutral", NEUTRAL), ("sell", SELL))}

    pivots = None
    if len(bars) >= 2:
        levels = price.pivot_points(highs, lows, closes, dates, "D")
        pivots = {
            "session": dates[-1], "based_on": dates[-2], "method": "classic",
            "levels": {name: _round(series[-1]) for name, series in levels.items()},
        }

    return {
        "close": _round(close),
        "indicators": indicators,
        "pivots": pivots,
        "summary": {**counts, "total": len(voting), "signal": overall_signal(counts["buy"], counts["sell"], counts["neutral"])},
    }


def instrument_technicals(company=None):
    """technical_summary for the NEPSE index (``company`` None) or a tracked company."""
    if company is None:
        used, cutoff_date, adjusted_dates = index_bars(), None, []
    else:
        bars = company_bars(company)
        used, cutoff, adjusted_dates = adjust_for_corporate_actions(bars)
        cutoff_date = bars[cutoff]["date"] if cutoff else None
    return {
        "symbol": "NEPSE" if company is None else company.symbol,
        "kind": "index" if company is None else "company",
        "as_of": used[-1]["date"] if used else None,
        "sessions_used": len(used),
        "history_start": used[0]["date"] if used else None,
        "adjusted_sessions": adjusted_dates,
        "corporate_action_cutoff": cutoff_date,
        **technical_summary(used),
        "disclaimer": DISCLAIMER,
    }
