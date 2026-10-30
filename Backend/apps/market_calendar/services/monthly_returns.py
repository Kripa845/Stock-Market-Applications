"""
NEPSE month by month: one row per BS year, one tile per BS month, each tile = that month's
index return, plus the year's return.  Derived from the stored daily closes (IndexDaily);
no table of its own.

* A month's return is its last close against the last close before it began (the same rule
  as the day-by-day page), so a month with no session is blank and the next month spans the
  gap.  The month the history starts in has no earlier close and stays blank.
* A year's return is its last close against the last close before it began: compounded from
  closes, never the sum of its months.  The first year of history has no earlier close.
* ``partial``: the running month / year, and the month / year the history starts in.
* AVG row, "strongest month" and "months that closed up" skip blanks (never counted as 0);
  the running month counts with its return so far (it is flagged partial).

Whole market: no per-company data.
"""

from bisect import bisect_left
from datetime import timedelta

import nepali_datetime
from django.core.cache import cache
from django.db.models import Max
from django.utils import timezone

from apps.market_calendar.services.month_summary import (
    BS, BS_MONTHS_NP, DEFAULT_INDEX, NoIndexData, SummaryError, _Month, _month_of, _pct, index_catalogue,
)
from apps.market_indices.models import MarketIndex

BS_MONTHS_EN = tuple(nepali_datetime.date(2083, m, 1).strftime("%B") for m in range(1, 13))
CACHE_SECONDS = 60 * 60


def monthly_returns(index_code=DEFAULT_INDEX, today=None):
    index = MarketIndex.objects.filter(code=index_code).first()
    if index is None:
        raise SummaryError(f"Unknown index {index_code!r}.")
    today = today or timezone.localdate()
    # Keyed on the newest stored row, so a new close (or a NEPSE row replacing a fallback one)
    # gives a fresh result; until then the grid cannot change within the day.
    stamp = index.daily.aggregate(latest=Max("date"), updated=Max("updated_at"))
    if stamp["latest"] is None:
        raise NoIndexData(f"No stored sessions for {index.name} yet.")
    key = f"market-calendar:monthly:{index.code}:{today}:{stamp['latest']}:{stamp['updated'].timestamp():.0f}"
    data = cache.get(key)
    if data is None:
        data = _build(index, today)
        cache.set(key, data, CACHE_SECONDS)
    return data


def _build(index, today):
    rows = list(index.daily.filter(date__lte=today).order_by("date").values_list("date", "close"))
    dates = [day for day, _ in rows]
    history_from = dates[0]

    def close_before(day):
        """(date, close) of the last session before ``day``, or None."""
        position = bisect_left(dates, day)
        return rows[position - 1] if position else None

    def last_in(start, end):
        position = bisect_left(dates, end + timedelta(days=1)) - 1
        return rows[position] if position >= 0 and dates[position] >= start else None

    current = _month_of(BS, today)
    first = _month_of(BS, history_from)

    years = []
    for year in range(current.year, first.year - 1, -1):
        cells = []
        for number in range(1, 13):
            month = _Month(BS, year, number)
            if month.end < history_from or month.start > today:
                cells.append(None)
                continue
            closing = last_in(month.start, min(month.end, today))
            opening = close_before(month.start)
            is_current = (year, number) == (current.year, current.month)
            cells.append({
                "month": number,
                "close": closing[1] if closing else None,
                "close_date": closing[0] if closing else None,
                "previous_close": opening[1] if opening else None,
                "return_pct": _pct(closing[1], opening[1]) if closing and opening else None,
                "is_current": is_current,
                "partial": is_current or month.start <= history_from <= month.end,
            })
        year_start = _Month(BS, year, 1).start
        year_end = min(_Month(BS, year, 12).end, today)
        closing = last_in(year_start, year_end)
        opening = close_before(year_start)
        years.append({
            "year": year,
            "months": cells,
            "close": closing[1] if closing else None,
            "year_return": _pct(closing[1], opening[1]) if closing and opening else None,
            "partial": year == current.year or year == first.year,
        })

    # Blanks say nothing about a month's habit; they are skipped, never counted as 0.
    valued = [c for y in years for c in y["months"] if c and c["return_pct"] is not None]
    avg_row = []
    for number in range(1, 13):
        moves = [c["return_pct"] for c in valued if c["month"] == number]
        avg_row.append({"average_pct": sum(moves) / len(moves), "years": len(moves)} if moves else None)

    ranked = [y for y in years if y["year_return"] is not None]
    best = max(ranked, key=lambda y: y["year_return"], default=None)
    worst = min(ranked, key=lambda y: y["year_return"], default=None)
    strongest = max((m for m in range(12) if avg_row[m]), key=lambda m: avg_row[m]["average_pct"], default=None)

    return {
        "scope": "whole_market",
        "index": {"code": index.code, "name": index.name},
        "today": today,
        "history_from": history_from,
        "current": {"year": current.year, "month": current.month},
        "months": [{"month": m + 1, "label": BS_MONTHS_EN[m], "label_np": BS_MONTHS_NP[m]} for m in range(12)],
        "years": years,
        "avg_row": avg_row,
        "stats": {
            "best_year": _year_ref(best),
            "worst_year": _year_ref(worst if worst is not best else None),
            "strongest_month": {"month": strongest + 1, "label": BS_MONTHS_EN[strongest],
                                "label_np": BS_MONTHS_NP[strongest], **avg_row[strongest]}
            if strongest is not None else None,
            "months_up": sum(1 for c in valued if c["return_pct"] > 0),
            "months_counted": len(valued),
        },
        "indices": index_catalogue(),
        "notes": [f"Index history starts {history_from:%d %b %Y}."],
    }


def _year_ref(row):
    if row is None:
        return None
    return {"year": row["year"], "year_return": row["year_return"], "partial": row["partial"]}

