from rest_framework.exceptions import ValidationError

from apps.market_data.models import DailyPrice

VALID_SOURCES = {value for value, _ in DailyPrice.SOURCE_CHOICES}


def requested_price_source(request, default="crawled"):
    """Return the ?source= query parameter, rejecting values that are not a DailyPrice source."""
    source = request.query_params.get("source", default)
    if source not in VALID_SOURCES:
        raise ValidationError({"source": f"Must be one of: {', '.join(sorted(VALID_SOURCES))}."})
    return source


def with_crawled_price(queryset):
    """
    Keep only DailyAnalysis-style rows (``company`` + ``date``) that have a
    crawled DailyPrice for the same company and date.

    DailyAnalysis has no source column; rows built from the synthetic
    ``unverified`` / ``seeded`` prices must never reach dashboards or exports.
    Nothing is deleted -- they are only filtered out of reads.
    """
    from django.db.models import Exists, OuterRef

    return queryset.filter(
        Exists(
            DailyPrice.objects.filter(
                company=OuterRef("company"),
                date=OuterRef("date"),
                source="crawled",
            )
        )
    )
