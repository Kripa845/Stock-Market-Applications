"""Calculation helpers for company volume anomaly history."""

import pandas as pd

from apps.market_data.models import DailyPrice


LOOKBACK_TRADING_DAYS = 20
ANOMALY_RVOL_THRESHOLD = 2.5


def get_volume_anomalies(company, start_date=None, end_date=None, lookback=LOOKBACK_TRADING_DAYS):
    """Return daily volume and its 20-period, prior-only SMA anomaly result.

    The current session is excluded from its baseline. A session is anomalous
    when its volume is at least 2.5 times the mean of the prior lookback
    sessions. Incomplete or zero baselines yield null RVOL and anomaly flags.
    """
    # The crawler currently keeps only about one calendar month of rows as
    # ``crawled``. Older imported rows are ``unverified`` but are already part
    # of the application's RVOL history, so use them as historical baseline
    # observations. Only return crawled rows for the requested output period.
    queryset = DailyPrice.objects.filter(
        company=company,
        source__in=("crawled", "unverified"),
    )
    if start_date:
        warmup = list(
            queryset.filter(date__lt=start_date)
            .order_by("-date")
            .values("date", "close", "volume", "source")[:lookback]
        )
        requested = queryset.filter(date__gte=start_date)
        if end_date:
            requested = requested.filter(date__lte=end_date)
        rows = list(reversed(warmup)) + list(
            requested.order_by("date").values("date", "close", "volume", "source")
        )
    else:
        requested = queryset.filter(date__lte=end_date) if end_date else queryset
        rows = list(requested.order_by("date").values("date", "close", "volume", "source"))
    if not rows:
        return []

    frame = pd.DataFrame.from_records(rows)
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce")
    frame["rolling_mean"] = frame["volume"].shift(1).rolling(
        lookback, min_periods=lookback
    ).mean()
    frame["rvol"] = frame["volume"] / frame["rolling_mean"].where(frame["rolling_mean"] > 0)
    frame["price_change_pct"] = frame["close"].pct_change() * 100
    frame["is_anomaly"] = frame["rvol"] >= ANOMALY_RVOL_THRESHOLD

    if start_date:
        frame = frame[frame["date"] >= start_date]
    if end_date:
        frame = frame[frame["date"] <= end_date]
    frame = frame[frame["source"] == "crawled"]

    results = []
    for row in frame.itertuples(index=False):
        results.append({
            "date": row.date,
            "volume": int(row.volume),
            "rolling_mean": None if pd.isna(row.rolling_mean) else float(row.rolling_mean),
            "average_volume_20d": None if pd.isna(row.rolling_mean) else float(row.rolling_mean),
            "rvol": None if pd.isna(row.rvol) else float(row.rvol),
            "anomaly_flag": None if pd.isna(row.rvol) else "Anomaly" if row.rvol >= ANOMALY_RVOL_THRESHOLD else "Normal",
            "is_anomaly": None if pd.isna(row.rvol) else bool(row.is_anomaly),
            "price_change_pct": None if pd.isna(row.price_change_pct) else float(row.price_change_pct),
        })
    return results
