"""Relative volume calculations for crawled company trading history."""

import pandas as pd


def calculate_rvol(rows, ma_length=21, ma_type="SMA", threshold=2.0, start_date=None, end_date=None):
    """Calculate volume / moving average in one vectorized pandas pass.

    Rows must be ordered or sortable by date and contain OHLCV values. For an
    EMA, callers should provide all available history before the requested
    output range so the recursive average starts with the full data series.
    """
    if ma_length < 1:
        raise ValueError("ma_length must be at least 1")
    normalized_type = ma_type.upper()
    if normalized_type not in {"SMA", "EMA"}:
        raise ValueError("ma_type must be SMA or EMA")

    frame = pd.DataFrame.from_records(rows)
    if frame.empty:
        return []
    frame = frame.sort_values("date").reset_index(drop=True)
    for field in ("open", "high", "low", "close", "volume"):
        frame[field] = pd.to_numeric(frame[field], errors="coerce")

    volumes = frame["volume"]
    if normalized_type == "SMA":
        average = volumes.rolling(ma_length, min_periods=ma_length).mean()
    else:
        average = volumes.ewm(span=ma_length, adjust=False, min_periods=ma_length).mean()
    # Benchmark each bar against completed prior bars only.
    frame["rolling_avg"] = average.shift(1)
    frame["rolling_std"] = volumes.rolling(ma_length, min_periods=ma_length).std()
    frame["rvol"] = volumes.div(frame["rolling_avg"].where(frame["rolling_avg"] > 0))
    frame["is_above_threshold"] = frame["rvol"].gt(threshold).fillna(False)

    if start_date is not None:
        frame = frame[frame["date"] >= start_date]
    if end_date is not None:
        frame = frame[frame["date"] <= end_date]

    output = []
    for row in frame.itertuples(index=False):
        output.append({
            "date": row.date,
            "open": None if pd.isna(row.open) else float(row.open),
            "high": None if pd.isna(row.high) else float(row.high),
            "low": None if pd.isna(row.low) else float(row.low),
            "close": None if pd.isna(row.close) else float(row.close),
            "volume": int(row.volume),
            "rolling_avg": None if pd.isna(row.rolling_avg) else float(row.rolling_avg),
            "rolling_std": None if pd.isna(row.rolling_std) else float(row.rolling_std),
            "rvol": None if pd.isna(row.rvol) else float(row.rvol),
            "is_above_threshold": bool(row.is_above_threshold),
        })
    return output


def get_company_rvol(company, start_date=None, end_date=None, ma_length=21, ma_type="SMA", threshold=2.0):
    """Fetch OHLCV once, retaining enough warm-up history for indicators."""
    from apps.market_data.models import DailyPrice

    queryset = DailyPrice.objects.filter(
        company=company,
        source__in=("crawled", "unverified"),
    )
    if start_date is not None:
        before = queryset.filter(date__lt=start_date)
        if ma_type == "EMA":
            # EMA depends on all earlier observations; a short warm-up truncates it.
            warmup = list(before.order_by("date").values("date", "open", "high", "low", "close", "volume"))
        else:
            warmup = list(before.order_by("-date").values("date", "open", "high", "low", "close", "volume")[:ma_length])
            warmup.reverse()
        requested = queryset.filter(date__gte=start_date)
        if end_date is not None:
            requested = requested.filter(date__lte=end_date)
        rows = warmup + list(requested.order_by("date").values("date", "open", "high", "low", "close", "volume"))
    else:
        requested = queryset.filter(date__lte=end_date) if end_date is not None else queryset
        rows = list(requested.order_by("date").values("date", "open", "high", "low", "close", "volume"))

    return calculate_rvol(rows, ma_length, ma_type, threshold, start_date, end_date)
