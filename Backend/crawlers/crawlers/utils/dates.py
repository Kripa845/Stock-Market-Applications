from datetime import datetime
from dateutil import parser as date_parser

from django.utils import timezone


def parse_datetime(value):
    """
    Convert almost any normal news date representation
    into a Django timezone-aware datetime.
    """

    if not value:
        return None

    if isinstance(value, datetime):

        if timezone.is_naive(value):
            return timezone.make_aware(value)

        return value

    value = str(value).strip()

    if not value:
        return None

    # Remove common separator characters
    value = value.replace("|", " ").strip()

    try:
        dt = date_parser.parse(
            value,
            fuzzy=True,
        )
    except (ValueError, TypeError, OverflowError):
        return None

    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)

    return dt