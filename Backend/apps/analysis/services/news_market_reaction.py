"""News-event reactions aligned to the company's observed trading sessions."""

from bisect import bisect_right
from math import sqrt
from bisect import bisect_left


MIN_CORRELATION_OBSERVATIONS = 3


def _pearson(pairs):
    """Return Pearson r and its usable sample size; require three observations."""
    if len(pairs) < MIN_CORRELATION_OBSERVATIONS:
        return None, len(pairs)

    xs, ys = zip(*pairs)
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    covariance = sum((x - mean_x) * (y - mean_y) for x, y in pairs)
    variance_x = sum((x - mean_x) ** 2 for x in xs)
    variance_y = sum((y - mean_y) ** 2 for y in ys)
    denominator = sqrt(variance_x * variance_y)
    if not denominator:
        return None, len(pairs)
    return round(covariance / denominator, 2), len(pairs)


def _sentiment_bucket(label, score):
    normalized = (label or "").strip().lower()
    if normalized in {"positive", "neutral", "negative"}:
        return normalized
    if score is None:
        return "neutral"
    if score >= 0.05:
        return "positive"
    if score <= -0.05:
        return "negative"
    return "neutral"


def _pct_change(current, baseline):
    current = float(current or 0)
    baseline = float(baseline or 0)
    if baseline <= 0:
        return None
    return round((current - baseline) / baseline * 100, 2)


def build_exploratory_news_reaction(company, window="t1", mode="per_article", start_date=None, end_date=None, include_seeded=False):
    """Correlate confident crawled news against subsequent observed sessions.

    Publication dates anchor to the first available price session on or after
    publication, naturally skipping weekends/holidays. T+1/T+2 compare that
    anchor close/volume with the following one/two stored sessions. This is
    exploratory association, not a validated predictive signal.
    """
    from apps.market_data.models import DailyPrice
    from apps.news.models import ArticleCompanyTag
    from django.conf import settings
    from django.utils import timezone

    offset = 1 if window == "t1" else 2
    sources = ["crawled"] + (["seeded"] if include_seeded else [])
    prices = list(DailyPrice.objects.filter(company=company, source__in=sources).order_by("date"))
    dates = [p.date for p in prices]
    threshold = float(getattr(settings, "CATEGORIZATION_THRESHOLD", 0.65))
    tags = ArticleCompanyTag.objects.filter(company=company, confidence__gte=threshold,
        article__data_provenance__in=sources, article__sentiment__isnull=False,
        article__sentiment_status__in=["ok", "no_lexicon_match"], article__published_at__isnull=False
    ).select_related("article").order_by("article__published_at", "article_id")
    grouped = {}
    articles = []
    for tag in tags:
        article = tag.article
        published = timezone.localtime(article.published_at).date() if timezone.is_aware(article.published_at) else article.published_at.date()
        if start_date and published < start_date or end_date and published > end_date:
            continue
        anchor_idx = bisect_left(dates, published)
        if anchor_idx >= len(prices) or anchor_idx + offset >= len(prices):
            continue
        anchor, future = prices[anchor_idx], prices[anchor_idx + offset]
        point = {"date": published.isoformat(), "session_date": anchor.date.isoformat(), "future_date": future.date.isoformat(),
                 "headline": article.headline, "sentiment": float(article.sentiment), "article_count": 1,
                 "price_change_pct": _pct_change(future.close, anchor.close),
                 "volume_change_pct": _pct_change(future.volume, anchor.volume)}
        articles.append(point)
        row = grouped.setdefault(anchor.date.isoformat(), {"date": published.isoformat(), "session_date": anchor.date.isoformat(), "sentiments": [], "article_count": 0, "price_change_pct": point["price_change_pct"], "volume_change_pct": point["volume_change_pct"], "headline": "Daily aggregate"})
        row["sentiments"].append(point["sentiment"])
        row["article_count"] += 1
    daily = [{**row, "sentiment": sum(row.pop("sentiments")) / len(row["sentiments"])} for row in grouped.values()]
    points = articles if mode == "per_article" else daily
    pairs = [(p["sentiment"] if mode == "per_article" else p["article_count"], p["price_change_pct"]) for p in points]
    r, n = _pearson(pairs)
    return {"company_id": company.pk, "window": "T+1" if offset == 1 else "T+2", "mode": mode,
        "n_observations": n, "pearson_r": r, "reason": "insufficient_data" if n < MIN_CORRELATION_OBSERVATIONS or r is None else None,
        "minimum_observations": MIN_CORRELATION_OBSERVATIONS,
        "date_range": {"start": min((p["date"] for p in points), default=None), "end": max((p["date"] for p in points), default=None)},
        "caveat": f"Exploratory correlation based on {n} observations. Not a validated predictive signal.",
        "provenance": "crawled_only" if not include_seeded else "crawled_and_seeded",
        "data_points": points}


def build_news_market_reaction(company, window_start, prices=None):
    """Build recent event details and full-history T+1/T+2 correlations.

    News dates map to the latest observed trading session on or before the
    publication date. T+1 and T+2 are subsequent rows in that company's
    DailyPrice history, so weekends and holidays are skipped automatically.
    """
    from apps.market_data.models import DailyPrice
    from apps.news.models import ArticleCompanyTag
    from django.utils import timezone

    price_rows = prices if prices is not None else list(
        DailyPrice.objects.filter(company=company, source="crawled").order_by("date")
    )
    price_dates = [row.date for row in price_rows]
    tags = list(
        ArticleCompanyTag.objects.filter(
            company=company,
            article__published_at__isnull=False,
        ).select_related("article").order_by("article__published_at", "article_id")
    )

    grouped = {}
    for tag in tags:
        published_at = tag.article.published_at
        if timezone.is_aware(published_at):
            news_date = timezone.localtime(published_at).date()
        else:
            news_date = published_at.date()
        event = grouped.setdefault(news_date, {
            "news_date": news_date,
            "article_count": 0,
            "positive_count": 0,
            "neutral_count": 0,
            "negative_count": 0,
            "sentiments": [],
        })
        event["article_count"] += 1
        sentiment = tag.article.sentiment
        event[f"{_sentiment_bucket(tag.article.sentiment_label, sentiment)}_count"] += 1
        if sentiment is not None:
            event["sentiments"].append(float(sentiment))

    historical_events = []
    recent_events = []
    for news_date, event in sorted(grouped.items()):
        baseline_index = bisect_right(price_dates, news_date) - 1
        baseline = price_rows[baseline_index] if baseline_index >= 0 else None
        next_one = price_rows[baseline_index + 1] if baseline_index >= 0 and baseline_index + 1 < len(price_rows) else None
        next_two = price_rows[baseline_index + 2] if baseline_index >= 0 and baseline_index + 2 < len(price_rows) else None

        sentiment_values = event["sentiments"]
        sentiment_score = round(sum(sentiment_values) / len(sentiment_values), 2) if sentiment_values else None
        baseline_close = float(baseline.close) if baseline else None
        baseline_volume = int(baseline.volume) if baseline else None

        def session_row(row, label):
            if row is None:
                return None
            close = float(row.close)
            volume = int(row.volume)
            return {
                "label": label,
                "date": row.date.isoformat(),
                "close": close,
                "volume": volume,
                "price_return_pct": None if label == "News Day" else _pct_change(close, baseline_close),
                "volume_change_pct": None if label == "News Day" else _pct_change(volume, baseline_volume),
            }

        t1_return = _pct_change(next_one.close, baseline_close) if next_one and baseline_close is not None else None
        t2_return = _pct_change(next_two.close, baseline_close) if next_two and baseline_close is not None else None
        t1_volume_change = _pct_change(next_one.volume, baseline_volume) if next_one and baseline_volume is not None else None
        t2_volume_change = _pct_change(next_two.volume, baseline_volume) if next_two and baseline_volume is not None else None

        row = {
            "news_date": news_date.isoformat(),
            "article_count": event["article_count"],
            "positive_count": event["positive_count"],
            "neutral_count": event["neutral_count"],
            "negative_count": event["negative_count"],
            "sentiment_score": sentiment_score,
            "baseline_date": baseline.date.isoformat() if baseline else None,
            "sessions": [
                session_row(baseline, "News Day"),
                session_row(next_one, "T+1"),
                session_row(next_two, "T+2"),
            ],
        }
        historical_events.append({
            "sentiment_score": sentiment_score,
            "article_count": event["article_count"],
            "t1_return": t1_return,
            "t2_return": t2_return,
            "t1_volume_change": t1_volume_change,
            "t2_volume_change": t2_volume_change,
        })
        if news_date >= window_start:
            recent_events.append(row)

    correlations = {}
    definitions = {
        "sentiment_t1_return": ("sentiment_score", "t1_return"),
        "sentiment_t2_return": ("sentiment_score", "t2_return"),
        "news_volume_t1_change": ("article_count", "t1_volume_change"),
        "news_volume_t2_change": ("article_count", "t2_volume_change"),
    }
    for key, (x_field, y_field) in definitions.items():
        pairs = [
            (event[x_field], event[y_field])
            for event in historical_events
            if event[x_field] is not None and event[y_field] is not None
        ]
        coefficient, observations = _pearson(pairs)
        correlations[key] = {"coefficient": coefficient, "observations": observations}

    complete_observations = sum(
        event["sentiment_score"] is not None
        and event["t1_return"] is not None
        and event["t2_return"] is not None
        and event["t1_volume_change"] is not None
        and event["t2_volume_change"] is not None
        for event in historical_events
    )

    return {
        "minimum_observations": MIN_CORRELATION_OBSERVATIONS,
        "observations": complete_observations,
        "events": list(reversed(recent_events)),
        "correlations": correlations,
        "baseline_note": "News Day is the latest stored trading session on or before the publication date; T+1 and T+2 are the next two stored sessions.",
        "disclaimer": "Correlation indicates association, not causation, and is not a validated trading signal.",
    }
