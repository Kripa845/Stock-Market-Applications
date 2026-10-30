"""
NEPSE day by day: one row per month, one tile per day, each tile = that session's index change.

Months are Bikram Sambat (``bs``) or Gregorian (``ad``).  A day's change is NEPSE's own
``source_change_pct`` (the close against the previous trading day's close), falling back to
the previous stored close when the feed sent none.  A month's change is its last close
against the last close before it began; it is ``partial`` while the month is still running
or when the index history starts inside it.  Whole market: no per-company data.
"""

import calendar as ad_calendar
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

import nepali_datetime
from django.utils import timezone

from apps.market_calendar.services.calendar import TRADED, day_status
from apps.market_data.models import TradingHoliday
from apps.market_indices.models import MarketIndex

BS, AD = "bs", "ad"
CALENDARS = (BS, AD)
DEFAULT_INDEX = "NEPSE"
DEFAULT_MONTHS = 12
MONTH_CHOICES = (6, 12, 24)
HUNDRED = Decimal(100)

# Spoken month names (the library has the formal ones: श्रावण, आश्विन ...).
BS_MONTHS_NP = ("वैशाख", "जेठ", "असार", "साउन", "भदौ", "असोज", "कात्तिक", "मंसिर", "पुस", "माघ", "फागुन", "चैत")
NP_DIGITS = str.maketrans("0123456789", "०१२३४५६७८९")
# Chip labels where the sector name is too long for the grid.
SHORT_LABELS = {
    "Hotels And Tourism": "Hotels",
    "Manufacturing And Processing": "Manufacturing",
    "Non Life Insurance": "Non-Life Insurance",
}


class SummaryError(ValueError):
    """Bad calendar / months / index (the view answers 400)."""


class NoIndexData(LookupError):
    """The index has no stored sessions yet (the view answers 404)."""


def np_digits(value):
    return str(value).translate(NP_DIGITS)


def index_catalogue():
    """NEPSE first, then the sub-indices, in the order the indices page shows them."""
    indices = list(MarketIndex.objects.filter(code=DEFAULT_INDEX)) + list(MarketIndex.objects.filter(kind=MarketIndex.KIND_SUB))
    return [
        {"code": i.code, "label": "NEPSE" if i.code == DEFAULT_INDEX else SHORT_LABELS.get(i.sector_name, i.sector_name or i.name)}
        for i in indices
    ]


class _Month:
    """One calendar month: its first / last AD date, label and how to number a day in it."""

    def __init__(self, mode, year, month):
        self.mode, self.year, self.month = mode, year, month
        if mode == BS:
            first = nepali_datetime.date(year, month, 1)
            self.start = first.to_datetime_date()
            nxt = (year + 1, 1) if month == 12 else (year, month + 1)
            self.end = nepali_datetime.date(*nxt, 1).to_datetime_date() - timedelta(days=1)
            self.label = f"{first.strftime('%B')} {year}"
            self.label_np = f"{BS_MONTHS_NP[month - 1]} {np_digits(year)}"
        else:
            self.start = date(year, month, 1)
            self.end = date(year, month, ad_calendar.monthrange(year, month)[1])
            self.label = self.start.strftime("%B %Y")
            self.label_np = ""

    def previous(self):
        if self.month == 1:
            return _Month(self.mode, self.year - 1, 12)
        return _Month(self.mode, self.year, self.month - 1)

    def days(self):
        day = self.start
        while day <= self.end:
            yield day
            day += timedelta(days=1)


def _month_of(mode, day):
    if mode == BS:
        bs = nepali_datetime.date.from_datetime_date(day)
        return _Month(BS, bs.year, bs.month)
    return _Month(AD, day.year, day.month)


def _bs_label(day):
    bs = nepali_datetime.date.from_datetime_date(day)
    return f"{np_digits(bs.day)} {BS_MONTHS_NP[bs.month - 1]} {np_digits(bs.year)}", f"{bs.day} {bs.strftime('%B')} {bs.year}"


def _pct(now, before):
    return (now / before - 1) * HUNDRED if before else None


def month_summary(index_code=DEFAULT_INDEX, mode=BS, months=DEFAULT_MONTHS, today=None):
    if mode not in CALENDARS:
        raise SummaryError(f"calendar must be one of {', '.join(CALENDARS)}.")
    if months not in MONTH_CHOICES:
        raise SummaryError(f"months must be one of {', '.join(map(str, MONTH_CHOICES))}.")
    index = MarketIndex.objects.filter(code=index_code).first()
    if index is None:
        raise SummaryError(f"Unknown index {index_code!r}.")
    today = today or timezone.localdate()

    history_from = index.daily.order_by("date").values_list("date", flat=True).first()
    if history_from is None:
        raise NoIndexData(f"No stored sessions for {index.name} yet.")

    # Newest month first; never older than the month the history starts in.
    current = _month_of(mode, today)
    window = [current]
    while len(window) < months and window[-1].start > history_from:
        window.append(window[-1].previous())
    start, end = window[-1].start, min(current.end, today)

    rows = list(index.daily.filter(date__gte=start, date__lte=end).order_by("date"))
    base = index.daily.filter(date__lt=start).order_by("-date").first()
    holidays = dict(TradingHoliday.objects.filter(date__range=(start, current.end)).values_list("date", "name"))

    sessions = {}
    previous = base
    for row in rows:
        change_pct = row.source_change_pct
        if change_pct is None and previous is not None:
            change_pct = _pct(row.close, previous.close)
        sessions[row.date] = {
            "close": row.close,
            "previous_close": previous.close if previous else None,
            "previous_date": previous.date if previous else None,
            "change_pct": change_pct,
        }
        previous = row

    # Last close on or before each month's end, for month changes.
    closes = [(base.date, base.close)] if base else []
    closes += [(row.date, row.close) for row in rows]

    def close_on_or_before(day):
        found = None
        for when, close in closes:
            if when > day:
                break
            found = close
        return found

    month_rows = []
    weekday_moves = defaultdict(list)
    for month in window:
        days = []
        for number, day in enumerate(month.days(), start=1):
            session = sessions.get(day)
            bs_np, bs_en = _bs_label(day)
            days.append({
                "day": number,
                "date": day,
                "bs_label_np": bs_np,
                "bs_label": bs_en,
                "weekday": day.strftime("%a"),
                "status": day_status(day, today, session, holidays.get(day), history_from),
                "holiday": holidays.get(day),
                **(session or {"close": None, "previous_close": None, "previous_date": None, "change_pct": None}),
            })
            if session and session["change_pct"] is not None:
                weekday_moves[day.strftime("%a")].append(session["change_pct"])
        traded = [d for d in days if d["status"] == TRADED and d["change_pct"] is not None]
        opening = close_on_or_before(month.start - timedelta(days=1))
        closing = close_on_or_before(min(month.end, today))
        has_session = bool(traded)
        month_rows.append({
            "year": month.year,
            "month": month.month,
            "label": month.label,
            "label_np": month.label_np,
            "ad_start": month.start,
            "ad_end": month.end,
            "is_current": month is current,
            "partial": month is current or month.start < history_from <= month.end,
            "change_pct": _pct(closing, opening) if has_session and opening else None,
            "sessions": len(traded),
            "up_days": sum(1 for d in traded if d["change_pct"] > 0),
            "days": days,
        })

    this_year = [m for m in month_rows if m["year"] == current.year and m["change_pct"] is not None]
    best = max(this_year, key=lambda m: m["change_pct"], default=None)
    worst = min(this_year, key=lambda m: m["change_pct"], default=None)
    # One session says nothing about a weekday.
    averages = {name: sum(moves) / len(moves) for name, moves in weekday_moves.items() if len(moves) >= 2}
    strongest = max(averages, key=averages.get, default=None)
    all_moves = [m for moves in weekday_moves.values() for m in moves]

    return {
        "scope": "whole_market",
        "index": {"code": index.code, "name": index.name},
        "calendar": mode,
        "today": today,
        "today_day": (today - current.start).days + 1,
        "max_days": max(len(m["days"]) for m in month_rows),
        "history_from": history_from,
        "requested_months": months,
        "months": month_rows,
        "stats": {
            "year": current.year,
            "best_month": _month_ref(best),
            "worst_month": _month_ref(worst if worst is not best else None),
            "strongest_weekday": {"weekday": strongest, "average_pct": averages[strongest],
                                  "sessions": len(weekday_moves[strongest])} if strongest else None,
            "sessions": len(all_moves),
            "up_days": sum(1 for m in all_moves if m > 0),
        },
        "indices": index_catalogue(),
        "notes": [f"Index history starts {history_from:%d %b %Y}."] if len(window) < months else [],
    }


def _month_ref(row):
    if row is None:
        return None
    return {key: row[key] for key in ("label", "label_np", "change_pct", "partial", "sessions", "up_days")}
