from decimal import Decimal
from math import sqrt

from django.db.models import Count
from django.utils import timezone

from apps.market_data.models import DailyPrice
from apps.news.models import ArticleCompanyTag
from .models import DailyAnalysis


def _pressure(open_price, close_price):
    if close_price > open_price:
        return "buying"
    if close_price < open_price:
        return "selling"
    return "neutral"


def build_daily_analysis(company_id, date=None):
    date = date or timezone.localdate()

    price = (
        DailyPrice.objects.filter(company_id=company_id, date=date).first()
        or DailyPrice.objects.filter(company_id=company_id).order_by("-date").first()
    )

    if price is None:
        return None

    history = list(
        DailyPrice.objects.filter(
            company_id=company_id,
            date__lte=price.date,
        ).order_by("-date")[:20]
    )

    volumes = [Decimal(p.volume) for p in history]
    volume_average = (
        sum(volumes, Decimal("0")) / Decimal(len(volumes))
        if volumes else None
    )

    # Aggregate traded amount / aggregate quantity.
    vwap = price.turnover / Decimal(price.volume) if price.volume else None

    news_count = ArticleCompanyTag.objects.filter(
        company_id=company_id,
        article__published_at__date=price.date,
    ).count()

    anomaly = bool(
        volume_average
        and volume_average > 0
        and Decimal(price.volume) >= volume_average * Decimal("2")
    )

    analysis, _ = DailyAnalysis.objects.update_or_create(
        company_id=company_id,
        date=price.date,
        defaults={
            "vwap": vwap,
            "close_price": price.close,
            "volume": price.volume,
            "volume_average": volume_average,
            "volume_anomaly": anomaly,
            "pressure": _pressure(price.open, price.close),
            "news_count": news_count,
        },
    )

    return analysis


def news_price_correlation(company_id, days=30):
    rows = list(
        DailyPrice.objects.filter(company_id=company_id)
        .order_by("-date")[:days + 1]
    )
    rows.reverse()

    if len(rows) < 3:
        return 0.0

    counts = dict(
        ArticleCompanyTag.objects.filter(
            company_id=company_id,
            article__published_at__isnull=False,
            article__published_at__date__in=[r.date for r in rows],
        )
        .values("article__published_at__date")
        .annotate(n=Count("id"))
        .values_list("article__published_at__date", "n")
    )

    news, returns = [], []

    for previous, current in zip(rows, rows[1:]):
        if previous.close == 0:
            continue

        news.append(float(counts.get(current.date, 0)))
        returns.append(
            float((current.close - previous.close) / previous.close)
        )

    if len(news) < 2:
        return 0.0

    mean_x = sum(news) / len(news)
    mean_y = sum(returns) / len(returns)

    cov = sum(
        (x - mean_x) * (y - mean_y)
        for x, y in zip(news, returns)
    )
    var_x = sum((x - mean_x) ** 2 for x in news)
    var_y = sum((y - mean_y) ** 2 for y in returns)

    denominator = sqrt(var_x * var_y)
    return cov / denominator if denominator else 0.0