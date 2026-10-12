# """
# Trading-calendar helpers.

# NEPSE does not trade on weekends or public holidays, and the set of
# holidays is not derivable from a calendar rule.  Rather than guessing,
# this module treats the ``DailyPrice`` table as the authoritative record
# of which dates actually traded: a date exists in ``DailyPrice`` if and
# only if the market produced a price for it.

# That gives us weekend/holiday handling for free and keeps every
# "previous N trading sessions" calculation honest, because a session
# offset is an index into real observed dates and never a calendar-day
# subtraction.
# """

# from __future__ import annotations

# from datetime import date, timedelta

# from apps.market_data.models import DailyPrice


# # Session offsets used to build the deterministic floorsheet sample.
# # Offset 0 is the latest trading session, 5 is five sessions before it,
# # and so on.  These are TRADING-SESSION offsets, never calendar days.
# DEFAULT_SAMPLE_OFFSETS = (0, 5, 10, 15, 20, 25)


# def trading_dates(company=None, limit=None, since=None):
#     """
#     Return distinct trading dates, most recent first.

#     :param company: restrict to one company, or ``None`` for market-wide.
#     :param limit: maximum number of dates to return.
#     :param since: only include dates >= this date.
#     """
#     queryset = DailyPrice.objects.all()

#     if company is not None:
#         queryset = queryset.filter(company=company)

#     if since is not None:
#         queryset = queryset.filter(date__gte=since)

#     queryset = (
#         queryset
#         .order_by("-date")
#         .values_list("date", flat=True)
#         .distinct()
#     )

#     if limit is not None:
#         queryset = queryset[:limit]

#     return list(queryset)


# def latest_trading_date(company=None):
#     """
#     Latest trading date we actually hold data for, or ``None``.

#     Deliberately not ``date.today()``: if the market has been closed for
#     three days, the latest available trading date is three days old and
#     every downstream window must anchor to that, not to today.
#     """
#     dates = trading_dates(company=company, limit=1)
#     return dates[0] if dates else None


# def previous_trading_sessions(anchor_date, count, company=None):
#     """
#     Return the ``count`` trading dates strictly BEFORE ``anchor_date``,
#     most recent first.

#     Returns fewer than ``count`` entries when history is short; callers
#     are responsible for deciding what to do with a partial baseline.
#     """
#     if anchor_date is None or count <= 0:
#         return []

#     queryset = DailyPrice.objects.filter(date__lt=anchor_date)

#     if company is not None:
#         queryset = queryset.filter(company=company)

#     return list(
#         queryset
#         .order_by("-date")
#         .values_list("date", flat=True)
#         .distinct()[:count]
#     )


# def select_sample_dates(
#     offsets=DEFAULT_SAMPLE_OFFSETS,
#     company=None,
#     anchor_date=None,
# ):
#     """
#     Deterministically select trading dates by SESSION offset.

#     ``offsets=(0, 5, 10)`` means: the latest session, the session five
#     sessions earlier, and the session ten sessions earlier.  If history
#     is shorter than the largest offset, the unavailable offsets are
#     silently dropped rather than substituted with a calendar guess.

#     The result is sorted descending and de-duplicated, so the same
#     inputs always produce the same output — which is what makes the
#     floorsheet sample reproducible across companies and across runs.
#     """
#     ordered_offsets = sorted(set(int(offset) for offset in offsets))

#     if not ordered_offsets:
#         return []

#     needed = max(ordered_offsets) + 1

#     available = trading_dates(company=company, limit=None)

#     if anchor_date is not None:
#         available = [d for d in available if d <= anchor_date]

#     available = available[:needed]

#     if not available:
#         return []

#     selected = []

#     for offset in ordered_offsets:
#         if offset < len(available):
#             candidate = available[offset]
#             if candidate not in selected:
#                 selected.append(candidate)

#     return sorted(selected, reverse=True)


# def rolling_window_bounds(window_days=31, company=None, anchor_date=None):
#     """
#     Return ``(start_date, end_date)`` for the rolling analysis window.

#     ``end_date`` is the latest AVAILABLE trading date (or ``anchor_date``
#     when supplied), never today's date.  ``start_date`` is
#     ``end_date - window_days`` calendar days.

#     Returns ``(None, None)`` when no trading data exists at all.
#     """
#     end_date = anchor_date or latest_trading_date(company=company)

#     if end_date is None:
#         return None, None

#     return end_date - timedelta(days=int(window_days)), end_date


# def is_trading_date(value, company=None):
#     """True when ``value`` is a date the market actually traded on."""
#     if not isinstance(value, date):
#         return False

#     queryset = DailyPrice.objects.filter(date=value)

#     if company is not None:
#         queryset = queryset.filter(company=company)

#     return queryset.exists()
"""
Trading-calendar helpers.

NEPSE does not trade on weekends or public holidays, and the set of
holidays is not derivable from a calendar rule.  Rather than guessing,
this module treats the ``DailyPrice`` table as the authoritative record
of which dates actually traded: a date exists in ``DailyPrice`` if and
only if the market produced a price for it.

That gives us weekend/holiday handling for free and keeps every
"previous N trading sessions" calculation honest, because a session
offset is an index into real observed dates and never a calendar-day
subtraction.
"""

from __future__ import annotations

from datetime import date, timedelta

from apps.market_data.models import DailyPrice


# Session offsets used to build the deterministic floorsheet sample.
# Offset 0 is the latest trading session, 5 is five sessions before it,
# and so on.  These are TRADING-SESSION offsets, never calendar days.
DEFAULT_SAMPLE_OFFSETS = (0, 5, 10, 15, 20, 25)


def trading_dates(company=None, limit=None, since=None, source="crawled"):
    """
    Return distinct trading dates, most recent first.

    :param company: restrict to one company, or ``None`` for market-wide.
    :param limit: maximum number of dates to return.
    :param since: only include dates >= this date.
    """
    queryset = DailyPrice.objects.filter(source=source)

    if company is not None:
        queryset = queryset.filter(company=company)

    if since is not None:
        queryset = queryset.filter(date__gte=since)

    queryset = (
        queryset
        .order_by("-date")
        .values_list("date", flat=True)
        .distinct()
    )

    if limit is not None:
        queryset = queryset[:limit]

    return list(queryset)


def latest_trading_date(company=None, source="crawled"):
    """
    Latest trading date we actually hold data for, or ``None``.

    Deliberately not ``date.today()``: if the market has been closed for
    three days, the latest available trading date is three days old and
    every downstream window must anchor to that, not to today.
    """
    dates = trading_dates(company=company, limit=1, source=source)
    return dates[0] if dates else None


def previous_trading_sessions(anchor_date, count, company=None, source="crawled"):
    """
    Return the ``count`` trading dates strictly BEFORE ``anchor_date``,
    most recent first.

    Returns fewer than ``count`` entries when history is short; callers
    are responsible for deciding what to do with a partial baseline.
    """
    if anchor_date is None or count <= 0:
        return []

    queryset = DailyPrice.objects.filter(source=source, date__lt=anchor_date)

    if company is not None:
        queryset = queryset.filter(company=company)

    return list(
        queryset
        .order_by("-date")
        .values_list("date", flat=True)
        .distinct()[:count]
    )


def select_sample_dates(
    offsets=DEFAULT_SAMPLE_OFFSETS,
    company=None,
    anchor_date=None,
    source="crawled",
):
    """
    Deterministically select trading dates by SESSION offset.

    ``offsets=(0, 5, 10)`` means: the latest session, the session five
    sessions earlier, and the session ten sessions earlier.  If history
    is shorter than the largest offset, the unavailable offsets are
    silently dropped rather than substituted with a calendar guess.

    The result is sorted descending and de-duplicated, so the same
    inputs always produce the same output — which is what makes the
    floorsheet sample reproducible across companies and across runs.
    """
    ordered_offsets = sorted(set(int(offset) for offset in offsets))

    if not ordered_offsets:
        return []

    needed = max(ordered_offsets) + 1

    available = trading_dates(company=company, limit=None, source=source)

    if anchor_date is not None:
        available = [d for d in available if d <= anchor_date]

    available = available[:needed]

    if not available:
        return []

    selected = []

    for offset in ordered_offsets:
        if offset < len(available):
            candidate = available[offset]
            if candidate not in selected:
                selected.append(candidate)

    return sorted(selected, reverse=True)


def rolling_window_bounds(window_days=31, company=None, anchor_date=None, source="crawled"):
    """
    Return ``(start_date, end_date)`` for the rolling analysis window.

    ``end_date`` is the latest AVAILABLE trading date (or ``anchor_date``
    when supplied), never today's date.  ``start_date`` is
    ``end_date - window_days`` calendar days.

    Returns ``(None, None)`` when no trading data exists at all.
    """
    end_date = anchor_date or latest_trading_date(company=company, source=source)

    if end_date is None:
        return None, None

    return end_date - timedelta(days=int(window_days)), end_date


def is_trading_date(value, company=None, source="crawled"):
    """True when ``value`` is a date the market actually traded on."""
    if not isinstance(value, date):
        return False

    queryset = DailyPrice.objects.filter(source=source, date=value)

    if company is not None:
        queryset = queryset.filter(company=company)

    return queryset.exists()
