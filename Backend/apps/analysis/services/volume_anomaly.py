"""Persisted rolling volume anomaly calculations over crawled trading sessions."""

from statistics import mean, pstdev

WINDOW = 20
VOLUME_MULTIPLIER_THRESHOLD = 2.5


def detect_volume_anomalies(rows, window=WINDOW):
    """Flag volume at least 2.5x the SMA of the preceding 20 sessions.

    The current session is excluded from the baseline. Partial baselines
    remain unscored and are indicated by ``insufficient_data``.
    """
    ordered = sorted(rows, key=lambda row: row[0])
    results = []
    for index, (session_date, volume) in enumerate(ordered):
        prior = [float(item[1]) for item in ordered[max(0, index - window):index]]
        insufficient = len(prior) < window
        rolling_mean = mean(prior) if not insufficient else None
        rolling_std = pstdev(prior) if not insufficient else None
        z_score = (
            (float(volume) - rolling_mean) / rolling_std
            if rolling_std is not None and rolling_std > 0 else None
        )
        pct_of_avg = (
            float(volume) / rolling_mean
            if rolling_mean is not None and rolling_mean > 0 else None
        )
        is_anomaly = (
            not insufficient
            and rolling_mean is not None
            and rolling_mean > 0
            and float(volume) >= VOLUME_MULTIPLIER_THRESHOLD * rolling_mean
        )
        reason = "multiplier" if is_anomaly else ""
        results.append({
            "date": session_date,
            "volume": int(volume),
            "rolling_mean": rolling_mean,
            "rolling_std": rolling_std,
            "z_score": z_score,
            "pct_of_avg": pct_of_avg,
            "is_anomaly": is_anomaly,
            "insufficient_data": insufficient,
            "reason": reason,
        })
    return results


def rebuild_company_volume_anomalies(company):
    """Recalculate and upsert the company's crawled OHLCV anomaly history."""
    from apps.analysis.models import VolumeAnomaly
    from apps.market_data.models import DailyPrice

    prices = DailyPrice.objects.filter(company=company, source="crawled").order_by("date").values_list("date", "volume")
    rows = detect_volume_anomalies(list(prices))
    for row in rows:
        VolumeAnomaly.objects.update_or_create(
            company=company,
            date=row["date"],
            defaults={key: value for key, value in row.items() if key != "date"},
        )
    return len(rows)
