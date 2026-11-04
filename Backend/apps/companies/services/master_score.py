from datetime import timedelta

import pandas as pd
from django.utils import timezone

from apps.market_data.models import DailyPrice

MIN_SESSIONS = 200

WEIGHTS = {"trend": 0.35, "momentum": 0.25, "macd": 0.20, "volume": 0.20}

BANDS = [
    (25, "Strong Avoid"),
    (50, "Neutral / Avoid"),
    (75, "Buy / Accumulate"),
    (101, "Strong Buy"),
]


def band_for(score: float) -> str:
    for upper, label in BANDS:
        if score < upper:
            return label
    return BANDS[-1][1]


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, float("nan"))
    return (100 - 100 / (1 + rs)).fillna(100)


def compute_master_score(company):
    # Same rule as the stock-detail quote: no same-day, still-open session.
    as_of_date = timezone.localdate() - timedelta(days=1)
    since = as_of_date - timedelta(days=420)

    rows = list(
        DailyPrice.objects.filter(
            company=company, source="crawled",
            date__gte=since, date__lte=as_of_date,
        )
        .order_by("date")
        .values("date", "close", "volume")
    )
    if len(rows) < MIN_SESSIONS:
        return None

    df = pd.DataFrame(rows)
    close = df["close"].astype(float)
    vol = df["volume"].astype(float)

    sma50 = close.rolling(50).mean().iloc[-1]
    sma200 = close.rolling(200).mean().iloc[-1]
    rsi = float(_rsi(close).iloc[-1])

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    macd_signal = macd_line.ewm(span=9, adjust=False).mean()

    avg_vol20 = vol.rolling(20).mean().iloc[-1]
    vol_ratio = float(vol.iloc[-1] / avg_vol20) if avg_vol20 else 1.0

    parts = {
        "trend": (50 if close.iloc[-1] > sma200 else 0) + (50 if sma50 > sma200 else 0),
        "momentum": rsi,
        "macd": 100 if macd_line.iloc[-1] > macd_signal.iloc[-1] else 0,
        "volume": min(vol_ratio * 50, 100),
    }
    score = round(sum(parts[k] * WEIGHTS[k] for k in WEIGHTS), 1)

    return {
        "score": score,
        "band": band_for(score),
        "as_of": df["date"].iloc[-1],
        "components": {k: round(float(v), 1) for k, v in parts.items()},
    }