from rest_framework.exceptions import ValidationError

from apps.market_data.models import DailyPrice

VALID_SOURCES = {value for value, _ in DailyPrice.SOURCE_CHOICES}


def requested_price_source(request, default="crawled"):
    """Return the ?source= query parameter, rejecting values that are not a DailyPrice source."""
    source = request.query_params.get("source", default)
    if source not in VALID_SOURCES:
        raise ValidationError({"source": f"Must be one of: {', '.join(sorted(VALID_SOURCES))}."})
    return source
