"""Persisted exploratory correlations between categorized news and future moves."""

import logging
from math import isfinite
import warnings
from collections import defaultdict
from datetime import timedelta

from scipy import stats

logger = logging.getLogger(__name__)
CONFIDENCE_FLOOR = 0.5
MIN_RELIABLE_N = 8
LAGS = (1, 2)
WINDOW_DAYS = 31
CAVEAT = "Exploratory only — roughly one month of data; small samples are possible, and this is not a validated trading signal."


def _correlate(x_values, y_values):
    paired = [(float(x), float(y)) for x, y in zip(x_values, y_values) if x is not None and y is not None]
    n = len(paired)
    result = {"n": n, "pearson_r": None, "pearson_p": None,
              "spearman_rho": None, "spearman_p": None, "reliable": n >= MIN_RELIABLE_N}
    if n < 3 or len({x for x, _ in paired}) < 2 or len({y for _, y in paired}) < 2:
        return result
    xs, ys = zip(*paired)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            pearson_r, pearson_p = stats.pearsonr(xs, ys)
            spearman_rho, spearman_p = stats.spearmanr(xs, ys)
        for key, value, places in (
            ("pearson_r", pearson_r, 3), ("pearson_p", pearson_p, 4),
            ("spearman_rho", spearman_rho, 3), ("spearman_p", spearman_p, 4),
        ):
            numeric_value = float(value) if value is not None else None
            result[key] = round(numeric_value, places) if numeric_value is not None and isfinite(numeric_value) else None
    except (ValueError, TypeError, FloatingPointError) as exc:
        logger.warning("Could not calculate news-price correlation: %s", exc)
    return result


def calculate_news_price_correlations(price_rows, news_rows, company_id):
    """Build a daily trading-session panel and calculate six forward correlations."""
    ordered_prices = sorted(price_rows, key=lambda row: row["date"])
    window_start = ordered_prices[-1]["date"] - timedelta(days=WINDOW_DAYS - 1) if ordered_prices else None
    daily_news = defaultdict(lambda: {"news_count": 0, "news_intensity": 0.0})
    for row in news_rows:
        if row["confidence"] < CONFIDENCE_FLOOR:
            continue
        day = row["date"]
        daily_news[day]["news_count"] += 1
        daily_news[day]["news_intensity"] += float(row["confidence"])

    by_lag = {}
    for lag in LAGS:
        intensity = []
        signed_return = []
        abs_return = []
        volume_change = []
        for index, price in enumerate(ordered_prices):
            if window_start is not None and price["date"] < window_start:
                continue
            future_index = index + lag
            if future_index >= len(ordered_prices):
                continue
            future = ordered_prices[future_index]
            close, volume = float(price["close"]), float(price["volume"])
            if close == 0 or volume == 0:
                continue
            change = (float(future["close"]) - close) / close * 100
            volume_pct = (float(future["volume"]) - volume) / volume * 100
            intensity.append(daily_news[price["date"]]["news_intensity"])
            signed_return.append(change)
            abs_return.append(abs(change))
            volume_change.append(volume_pct)
        by_lag[f"{lag}d"] = {
            "news_intensity_vs_signed_return": _correlate(intensity, signed_return),
            "news_intensity_vs_abs_return": _correlate(intensity, abs_return),
            "news_intensity_vs_volume_change": _correlate(intensity, volume_change),
        }
    return {
        "company_id": company_id,
        "method": "Pearson r and Spearman rho with p-values: daily news intensity vs forward trading-session changes",
        "confidence_floor": CONFIDENCE_FLOOR,
        "min_n_for_reliable": MIN_RELIABLE_N,
        "lags_days": list(LAGS),
        "window_start": window_start.isoformat() if window_start else None,
        "window_end": ordered_prices[-1]["date"].isoformat() if ordered_prices else None,
        "caveat": CAVEAT,
        "by_lag": by_lag,
    }


def rebuild_company_news_price_correlation(company):
    """Calculate from crawled records and persist latest per-company results."""
    from django.utils import timezone
    from apps.analysis.models import NewsPriceCorrelation
    from apps.market_data.models import DailyPrice
    from apps.news.models import ArticleCompanyTag

    prices = list(DailyPrice.objects.filter(company=company, source="crawled").order_by("date").values("date", "close", "volume"))
    tags = ArticleCompanyTag.objects.filter(
        company=company,
        confidence__gte=CONFIDENCE_FLOOR,
        article__data_provenance="crawled",
        article__published_at__isnull=False,
    ).select_related("article")
    news = []
    for tag in tags:
        published_at = tag.article.published_at
        day = timezone.localtime(published_at).date() if timezone.is_aware(published_at) else published_at.date()
        news.append({"date": day, "confidence": tag.confidence})
    results = calculate_news_price_correlations(prices, news, company.pk)
    results["computed_at"] = timezone.now().isoformat()
    NewsPriceCorrelation.objects.update_or_create(company=company, defaults={"results": results})
    return results
