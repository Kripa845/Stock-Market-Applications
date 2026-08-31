from datetime import datetime
from dateutil import parser as date_parser

from django.utils import timezone
import nepali_datetime


# Nepali month names used by Arthakhabar
NEPALI_MONTHS = {
    "बैशाख": 1,
    "जेठ": 2,
    "असार": 3,
    "श्रावण": 4,
    "भाद्र": 5,
    "आश्विन": 6,
    "कार्तिक": 7,
    "मंसिर": 8,
    "पौष": 9,
    "माघ": 10,
    "फाल्गुण": 11,
    "चैत्र": 12,
}


def _normalize_nepali_digits(value):
    """
    Convert Nepali numerals into ASCII numerals.

    Example:
        १९ श्रावण २०८३
        ->
        19 श्रावण 2083
    """

    nepali_digits = "०१२३४५६७८९"
    english_digits = "0123456789"

    translation_table = str.maketrans(
        nepali_digits,
        english_digits,
    )

    return value.translate(translation_table)


def _parse_nepali_bs_datetime(value):
    """
    Parse Arthakhabar's Bikram Sambat date format.

    Example:
        १९ श्रावण २०८३, मंगलवार १२:१७

    Returns:
        timezone-aware Gregorian datetime
        or None if the value is not a BS date.
    """

    if not value:
        return None

    value = _normalize_nepali_digits(
        str(value).strip()
    )

    # Example after digit conversion:
    #
    # 19 श्रावण 2083, मंगलवार 12:17

    for nepali_month, month_number in NEPALI_MONTHS.items():

        if nepali_month not in value:
            continue

        try:
            # Take the part before the comma:
            #
            # 19 श्रावण 2083
            date_part = value.split(",", 1)[0].strip()

            parts = date_part.split()

            if len(parts) < 3:
                return None

            day = int(parts[0])
            year = int(parts[2])

            # Extract time if present
            hour = 0
            minute = 0
            second = 0

            if "," in value:
                time_part = value.split(",", 1)[1].strip()

                # Find something like:
                # मंगलवार 12:17
                for token in time_part.split():

                    if ":" in token:
                        time_parts = token.split(":")

                        hour = int(time_parts[0])
                        minute = int(time_parts[1])

                        if len(time_parts) >= 3:
                            second = int(time_parts[2])

                        break

            bs_datetime = nepali_datetime.datetime(
                year,
                month_number,
                day,
                hour,
                minute,
                second,
            )

            # Convert BS -> AD
            ad_datetime = bs_datetime.to_datetime()

            if timezone.is_naive(ad_datetime):
                ad_datetime = timezone.make_aware(
                    ad_datetime
                )

            return ad_datetime

        except (
            ValueError,
            TypeError,
            OverflowError,
        ):
            return None

    return None


def parse_datetime(value):
    """
    Convert news publication dates into
    Django timezone-aware datetime objects.

    Supports:
    - Python datetime
    - normal Gregorian dates
    - ISO dates
    - Arthakhabar Bikram Sambat dates
    """

    if not value:
        return None

    # Already a datetime
    if isinstance(value, datetime):

        if timezone.is_naive(value):
            return timezone.make_aware(value)

        return value

    value = str(value).strip()

    if not value:
        return None

    # Remove common separator characters
    value = value.replace("|", " ").strip()

    # --------------------------------------------------
    # 1. Try Nepali Bikram Sambat date
    # --------------------------------------------------

    nepali_dt = _parse_nepali_bs_datetime(
        value
    )

    if nepali_dt:
        return nepali_dt

    # --------------------------------------------------
    # 2. Try normal Gregorian date
    # --------------------------------------------------

    try:

        dt = date_parser.parse(
            value,
            fuzzy=True,
        )

    except (
        ValueError,
        TypeError,
        OverflowError,
    ):

        return None

    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)

    return dt