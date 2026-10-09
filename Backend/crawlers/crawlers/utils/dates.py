import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import nepali_datetime
from dateutil import parser as date_parser

from django.utils import timezone


NEPAL_TZ = ZoneInfo("Asia/Kathmandu")

# A published date further ahead than this is a parsing error, never real.
MAX_FUTURE_SKEW = timedelta(days=1)

_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

_BS_MONTHS = {
    "बैशाख": 1, "बैसाख": 1,
    "जेठ": 2,
    "असार": 3,
    "श्रावण": 4, "साउन": 4,
    "भाद्र": 5, "भदौ": 5, "भाद्रपद": 5,
    "आश्विन": 6, "असोज": 6,
    "कार्तिक": 7,
    "मंसिर": 8, "मङ्सिर": 8,
    "पौष": 9, "पुस": 9,
    "माघ": 10,
    "फाल्गुण": 11, "फाल्गुन": 11, "फागुन": 11,
    "चैत्र": 12, "चैत": 12,
}

# "12 श्रावण 2083", "१२ श्रावण २०८३, मंगलवार १५:५०" (digits already converted)
_BS_PATTERN = re.compile(
    r"(?P<day>\d{1,2})\s*(?P<month>" + "|".join(sorted(_BS_MONTHS, key=len, reverse=True)) + r")\s*,?\s*(?P<year>\d{4})"
    r"(?:[^0-9]*?(?P<hour>\d{1,2}):(?P<minute>\d{2}))?"
)


def parse_bikram_sambat(value):
    """
    A Bikram Sambat (Nepali calendar) date such as "१२ श्रावण २०८३, मंगलवार १५:५०"
    converted to an aware datetime in Asia/Kathmandu, or None when ``value``
    contains no BS date.

    Nepali news portals (e.g. Arthakhabar) publish BS dates.  Handing them to a
    Gregorian parser turns BS year 2083 into AD 2083, which is how future-dated
    articles were stored before this was handled.
    """
    if not value:
        return None

    match = _BS_PATTERN.search(str(value).translate(_DEVANAGARI_DIGITS))
    if not match:
        return None

    try:
        ad_date = nepali_datetime.date(
            int(match.group("year")),
            _BS_MONTHS[match.group("month")],
            int(match.group("day")),
        ).to_datetime_date()
    except (ValueError, OverflowError, KeyError):
        return None

    hour = int(match.group("hour")) if match.group("hour") else 0
    minute = int(match.group("minute")) if match.group("minute") else 0
    if hour > 23 or minute > 59:
        hour = minute = 0

    return datetime(ad_date.year, ad_date.month, ad_date.day, hour, minute, tzinfo=NEPAL_TZ)


def parse_datetime(value, now=None):
    """
    Convert almost any normal news date representation
    into a Django timezone-aware datetime.

    Bikram Sambat dates are converted to AD first.  A result more than a day
    in the future is rejected (None) instead of being stored.
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

    dt = parse_bikram_sambat(value)

    if dt is None:
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

    if dt > (now or timezone.now()) + MAX_FUTURE_SKEW:
        return None

    return dt
