"""Exploratory forward market comparisons for categorized company news."""

from datetime import timedelta
import logging
import warnings

from scipy import stats

logger = logging.getLogger(__name__)
CONFIDENCE_FLOOR = 0.5
POSITIVE_SENTIMENT_FLOOR = 0.05


def _pearson(rows, metric):
    pairs = [
        (row["avg_sentiment"], row[metric])
        for row in rows
        if row["avg_sentiment"] is not None and row[metric] is not None
    ]
    result = {"coefficient": None, "observations": len(pairs)}
    if len(pairs) < 3 or len({x for x, _ in pairs}) < 2 or len({y for _, y in pairs}) < 2:
        return result
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            coefficient = float(stats.pearsonr(*zip(*pairs)).statistic)
        result["coefficient"] = round(coefficient, 4) if coefficient == coefficient else None
    except (ValueError, TypeError, FloatingPointError) as exc:
        logger.warning("Could not calculate forward news correlation: %s", exc)
    return result


def build_news_sentiment_forward_series(price_rows, news_rows, start_date=None, end_date=None):
    """Aggregate news by publication day and attach next two trading-session moves.

    Each news date uses the latest price session on or before that date as its
    baseline. Future sessions are the first two observed sessions strictly
    after the news date. Missing sentiment and missing future sessions stay null.
    """
    prices = sorted(price_rows, key=lambda row: row["date"])
    news_by_date = {}
    for item in news_rows:
        day = item["date"]
        if (start_date and day < start_date) or (end_date and day > end_date):
            continue
        aggregate = news_by_date.setdefault(day, {"sentiments": [], "positive_count": 0, "negative_count": 0, "article_count": 0, "news_items": []})
        aggregate["article_count"] += 1
        score = item["sentiment"]
        category = item.get("category")
        if score is not None:
            score = float(score)
            aggregate["sentiments"].append(score)
            if category not in {"Positive", "Neutral", "Negative"}:
                category = "Positive" if score >= POSITIVE_SENTIMENT_FLOOR else "Negative" if score <= -POSITIVE_SENTIMENT_FLOOR else "Neutral"
            if score >= POSITIVE_SENTIMENT_FLOOR:
                aggregate["positive_count"] += 1
            elif score <= -POSITIVE_SENTIMENT_FLOOR:
                aggregate["negative_count"] += 1
        else:
            category = category if category in {"Positive", "Neutral", "Negative"} else "Unscored"
        aggregate["news_items"].append({
            "headline": item.get("headline", ""),
            "category": category,
            "sentiment_score": score,
        })

    daily_data = []
    for day in sorted(news_by_date):
        aggregate = news_by_date[day]
        baseline_index = next((i for i in range(len(prices) - 1, -1, -1) if prices[i]["date"] <= day), None)
        baseline = prices[baseline_index] if baseline_index is not None else None
        future = prices[baseline_index + 1:baseline_index + 3] if baseline_index is not None else []
        sentiments = aggregate["sentiments"]
        entry = {
            "date": day,
            "article_count": aggregate["article_count"],
            "avg_sentiment": sum(sentiments) / len(sentiments) if sentiments else None,
            "news_items": aggregate["news_items"],
            "positive_count": aggregate["positive_count"],
            "negative_count": aggregate["negative_count"],
            "t1_date": future[0]["date"] if len(future) >= 1 else None,
            "t2_date": future[1]["date"] if len(future) >= 2 else None,
            "return_t1_pct": None,
            "return_t2_pct": None,
            "volume_change_t1_pct": None,
            "volume_change_t2_pct": None,
        }
        if baseline:
            base_close = float(baseline["close"])
            base_volume = float(baseline["volume"])
            for index, suffix in ((0, "t1"), (1, "t2")):
                if len(future) <= index:
                    continue
                target = future[index]
                if base_close:
                    entry[f"return_{suffix}_pct"] = (float(target["close"]) / base_close - 1) * 100
                if base_volume:
                    entry[f"volume_change_{suffix}_pct"] = (float(target["volume"]) / base_volume - 1) * 100
        daily_data.append(entry)

    summary = {
        "observations": sum(row["avg_sentiment"] is not None for row in daily_data),
        "sentiment_return_t1": _pearson(daily_data, "return_t1_pct"),
        "sentiment_return_t2": _pearson(daily_data, "return_t2_pct"),
        "sentiment_volume_change_t1": _pearson(daily_data, "volume_change_t1_pct"),
        "sentiment_volume_change_t2": _pearson(daily_data, "volume_change_t2_pct"),
    }
    return {"daily_data": daily_data, "correlation_summary": summary}


def get_company_news_sentiment_forward(company, start_date=None, end_date=None):
    """Load crawled categorized articles and OHLCV, then build the response."""
    from django.utils import timezone
    from apps.market_data.models import DailyPrice
    from apps.news.models import ArticleCompanyTag

    prices_query = DailyPrice.objects.filter(company=company, source="crawled")
    if start_date:
        baseline = prices_query.filter(date__lte=start_date).order_by("-date").values("date", "close", "volume")[:1]
        after_start = prices_query.filter(date__gt=start_date)
        if end_date:
            after_start = after_start.filter(date__lte=end_date + timedelta(days=14))
        price_rows = list(baseline) + list(after_start.order_by("date").values("date", "close", "volume"))
    else:
        after_end = prices_query.filter(date__lte=end_date + timedelta(days=14)) if end_date else prices_query
        price_rows = list(after_end.order_by("date").values("date", "close", "volume"))

    tags = ArticleCompanyTag.objects.filter(
        company=company,
        confidence__gte=CONFIDENCE_FLOOR,
        article__data_provenance="crawled",
        article__published_at__isnull=False,
    ).select_related("article").order_by("article__published_at")
    news_rows = []
    for tag in tags:
        published_at = tag.article.published_at
        day = timezone.localtime(published_at).date() if timezone.is_aware(published_at) else published_at.date()
        score = tag.article.sentiment
        category = tag.article.sentiment_label
        if category not in {"Positive", "Neutral", "Negative"}:
            category = category.capitalize() if category.lower() in {"positive", "neutral", "negative"} else None
        news_rows.append({
            "date": day,
            "sentiment": score,
            "category": category,
            "headline": tag.article.headline,
        })

    return build_news_sentiment_forward_series(price_rows, news_rows, start_date, end_date)
