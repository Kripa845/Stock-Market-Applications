"""
Bikram Sambat (BS) month view of NEPSE sessions.

Every BS date comes from ``nepali_datetime`` (month lengths, Nepali names and digits);
nothing here hardcodes a month table.  Index figures are the stored NEPSE rows only:
today's row is not stored until the close, so today reads "pending" until then.

Dividend events cover the tracked companies the user may access.  Public-issue events
(IPO, FPO, right share ...) are market-wide: the issuer is usually not listed or tracked yet.
"""

from collections import defaultdict
from datetime import timedelta

import nepali_datetime
from django.db.models import Q
from django.utils import timezone

from apps.companies.services.selection import tracked_active_companies
from apps.market_data.models import TradingHoliday
from apps.market_data.services.trading_days import is_trading_weekday
from apps.market_indices.models import MarketIndex
from apps.market_indices.services.aggregates import index_daily_changes
from apps.reports.models import DividendAnnouncement, IpoIssue
from apps.users.company_access import filter_company_queryset

INDEX_CODE = "NEPSE"

TRADED = "traded"
HOLIDAY = "holiday"
WEEKEND = "weekend"
PENDING = "pending"
NO_DATA = "no_data"
NO_SESSION = "no_session"
FUTURE = "future"

# The month cell only needs these; the day view sends the whole row.
MONTH_INDEX_FIELDS = ("close", "change", "change_pct", "previous_date", "source")
MONTH_EVENT_FIELDS = ("type", "symbol", "label")

# DividendAnnouncement date field -> (event type, short cell label), in display order.
DIVIDEND_EVENTS = {
    "book_closure_date": ("book_closure", "BC"),
    "bonus_listing_date": ("bonus_listed", "Bonus"),
    "distribution_date": ("cash_distributed", "Cash"),
    "announcement_date": ("dividend_announced", "Div"),
}
# IpoIssue date field -> (event type, verb).  The close event uses the earliest closing date.
ISSUE_EVENTS = {
    "open_date": ("ipo_open", "open"),
    "close_date": ("ipo_close", "close"),
}
ISSUE_SHORT = {
    IpoIssue.IssueType.IPO: "IPO",
    IpoIssue.IssueType.IPO_LOCAL: "IPO-Local",
    IpoIssue.IssueType.IPO_MIGRANT: "IPO-Migrant",
    IpoIssue.IssueType.IPO_QII: "IPO-QII",
    IpoIssue.IssueType.FPO: "FPO",
    IpoIssue.IssueType.RIGHT: "Right",
    IpoIssue.IssueType.MUTUAL_FUND: "MF",
    IpoIssue.IssueType.DEBENTURE: "Debenture",
}
_EVENT_ORDER = {event: rank for rank, event in enumerate((
    "book_closure", "ipo_open", "ipo_close", "bonus_listed", "cash_distributed", "dividend_announced",
))}


class CalendarError(ValueError):
    """Invalid BS year / month or AD date (the view answers 400)."""


class IndexNotFound(LookupError):
    """The NEPSE index is not in the catalogue (run seed_market_indices)."""


def _nepse():
    index = MarketIndex.objects.filter(code=INDEX_CODE).first()
    if index is None:
        raise IndexNotFound(f"Index {INDEX_CODE} is not in the catalogue.")
    return index


def _bs_month_start(bs_year, bs_month):
    try:
        return nepali_datetime.date(int(bs_year), int(bs_month), 1)
    except (TypeError, ValueError, OverflowError) as exc:
        raise CalendarError(f"No BS month {bs_year}/{bs_month}: {exc}") from None


def _ym(bs_date):
    return {"bs_year": bs_date.year, "bs_month": bs_date.month}


def _shift(bs_date, days):
    """``bs_date`` moved by ``days``, or None outside the library's range."""
    try:
        return bs_date + timedelta(days=days)
    except OverflowError:
        return None


def _np_day(bs_date):
    # %D is zero-padded ("०९").
    return bs_date.strftime("%D").lstrip("०")


def day_status(day, today, row, holiday, history_from):
    # A stored session wins over a holiday entry: NEPSE did trade (the name is still shown).
    if day > today:
        return FUTURE
    if row is not None:
        return TRADED
    if holiday:
        return HOLIDAY
    if not is_trading_weekday(day):
        return WEEKEND
    if day == today:
        return PENDING
    if history_from is None or day < history_from:
        return NO_DATA
    return NO_SESSION


def dividend_events(start, end, user):
    """
    {date: [event, ...]} for dividend dates of tracked companies ``user`` may access,
    from ``start`` to ``end``.  One announcement can give up to four events on four days.
    """
    in_range = Q()
    for field in DIVIDEND_EVENTS:
        in_range |= Q(**{f"{field}__range": (start, end)})
    rows = filter_company_queryset(
        DividendAnnouncement.objects.filter(in_range, company__in=tracked_active_companies()),
        user,
    ).select_related("company")

    events = defaultdict(list)
    for row in rows:
        for field, (event_type, short) in DIVIDEND_EVENTS.items():
            day = getattr(row, field)
            if day is None or not start <= day <= end:
                continue
            events[day].append({
                "category": "dividend",
                "type": event_type,
                "symbol": row.symbol,
                "label": f"{short} {row.symbol}",
                "company_name": row.company.name,
                "logo_url": row.company.logo_url,
                "fiscal_year": row.fiscal_year,
                "bonus_pct": str(row.bonus_pct),
                "cash_pct": str(row.cash_pct),
                "status": row.status,
            })
    return events


def issue_events(start, end):
    """{date: [event, ...]} for public issues opening or closing from ``start`` to ``end`` (whole market)."""
    rows = IpoIssue.objects.filter(
        Q(open_date__range=(start, end)) | Q(close_date__range=(start, end))
    ).select_related("company")

    events = defaultdict(list)
    for row in rows:
        name = row.symbol or row.company_name
        for field, (event_type, verb) in ISSUE_EVENTS.items():
            day = getattr(row, field)
            if day is None or not start <= day <= end:
                continue
            events[day].append({
                "category": "issue",
                "type": event_type,
                "symbol": row.symbol,
                "label": f"{ISSUE_SHORT[row.issue_type]} {verb} {name}",
                "company_name": row.company_name,
                "logo_url": row.company.logo_url if row.company else None,
                "issue_type": row.issue_type,
                "issue_type_label": row.get_issue_type_display(),
                "units": row.units,
                "price": None if row.price is None else str(row.price),
                "ratio": row.ratio,
                "issue_manager": row.issue_manager,
                "open_date": row.open_date,
                "close_date": row.close_date,
                "final_date": row.final_date,
            })
    return events


def day_events(start, end, user):
    """Dividend and issue events from ``start`` to ``end``, each day in display order."""
    events = dividend_events(start, end, user)
    for day, issues in issue_events(start, end).items():
        events[day].extend(issues)
    for listed in events.values():
        listed.sort(key=lambda event: (_EVENT_ORDER[event["type"]], event["symbol"], event["label"]))
    return events


def _data_notes():
    return [] if IpoIssue.objects.exists() else ["ipo_not_crawled"]


def _day(bs, today, row, holiday, history_from, events):
    ad = bs.to_datetime_date()
    return {
        "date": ad,
        "bs_day": bs.day,
        "bs_day_np": _np_day(bs),
        "weekday": (ad.weekday() + 1) % 7,          # 0 = Sunday
        "status": day_status(ad, today, row, holiday, history_from),
        "is_today": ad == today,
        "holiday": holiday,
        "index": row,
        "events": events,
    }


def day_view(ad_date=None, *, user=None, today=None):
    """
    One day with the full index row (OHLC, turnover, volume, trades) and full event detail.
    ``ad_date`` defaults to today.
    """
    today = today or timezone.localdate()
    ad_date = ad_date or today
    try:
        bs = nepali_datetime.date.from_datetime_date(ad_date)
    except (ValueError, OverflowError) as exc:
        raise CalendarError(f"{ad_date} is outside the BS calendar range: {exc}") from None

    index = _nepse()
    history_from = index.daily.order_by("date").values_list("date", flat=True).first()
    row = index_daily_changes(index, ad_date, ad_date).get(ad_date) if ad_date <= today else None
    holiday = TradingHoliday.objects.filter(date=ad_date).values_list("name", flat=True).first()

    return {
        "scope": "tracked_companies",
        "index_code": INDEX_CODE,
        "today": today,
        "bs": {
            "year": bs.year,
            "month": bs.month,
            "day": bs.day,
            "month_name": bs.strftime("%B"),
            "label_np": f"{_np_day(bs)} {bs.strftime('%N %K')}",
            "weekday_np": bs.strftime("%G"),
        },
        **_day(bs, today, row, holiday, history_from, day_events(ad_date, ad_date, user).get(ad_date, [])),
        "data_notes": _data_notes(),
    }


def month_view(bs_year=None, bs_month=None, *, user=None, today=None):
    """
    One BS month, Sunday-first.  ``bs_year`` / ``bs_month`` default to today's BS month
    (Asia/Kathmandu).  Future days get no index figures but keep their holiday names
    and scheduled events.  Without a ``user`` there are no events.
    """
    today = today or timezone.localdate()
    if bs_year is None and bs_month is None:
        current = nepali_datetime.date.from_datetime_date(today)
        bs_year, bs_month = current.year, current.month
    elif bs_year is None or bs_month is None:
        raise CalendarError("Pass both bs_year and bs_month, or neither.")

    first = _bs_month_start(bs_year, bs_month)
    bs_days = []
    day = first
    while day is not None and day.month == first.month:
        bs_days.append(day)
        day = _shift(day, 1)
    previous_month = _shift(first, -1)

    ad_start = first.to_datetime_date()
    ad_end = bs_days[-1].to_datetime_date()

    index = _nepse()
    history_from = index.daily.order_by("date").values_list("date", flat=True).first()
    rows = index_daily_changes(index, ad_start, min(ad_end, today)) if ad_start <= today else {}
    holidays = dict(TradingHoliday.objects.filter(date__range=(ad_start, ad_end)).values_list("date", "name"))
    events = day_events(ad_start, ad_end, user)

    days = []
    for bs in bs_days:
        ad = bs.to_datetime_date()
        day_data = _day(bs, today, rows.get(ad), holidays.get(ad), history_from, events.get(ad, []))
        if day_data["index"]:
            day_data["index"] = {field: day_data["index"][field] for field in MONTH_INDEX_FIELDS}
        day_data["events"] = [{field: event[field] for field in MONTH_EVENT_FIELDS} for event in day_data["events"]]
        days.append(day_data)

    return {
        "scope": "tracked_companies",
        "index_code": INDEX_CODE,
        "today": today,
        "bs_year": first.year,
        "bs_month": first.month,
        "month_name": first.strftime("%B"),
        "month_name_np": first.strftime("%N"),
        "bs_year_np": first.strftime("%K"),
        "ad_start": ad_start,
        "ad_end": ad_end,
        "prev": _ym(previous_month) if previous_month else None,
        "next": _ym(day) if day else None,
        "leading_blanks": days[0]["weekday"],
        "index_history_from": history_from,
        "days": days,
        "data_notes": _data_notes(),
    }
