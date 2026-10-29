"""
Which weekday pays: the NEPSE index's daily move by weekday over the last N trading weeks.

Days are the stored index sessions only (today's row is not stored until the close).  A
day's move is NEPSE's own ``source_change_pct``; a week's move is its last close against
the previous week's last close.  The window never crosses a change of trading week
(Sunday-Thursday until 2026-04-05), so every week has the same weekday columns.
"""

from datetime import date, timedelta
from decimal import Decimal

import nepali_datetime
from django.conf import settings
from django.utils import timezone

from apps.market_data.models import TradingHoliday
from apps.market_data.services.trading_days import trading_weekdays
from apps.market_indices.models import IndexDaily

INDEX_CODE = "NEPSE"
DEFAULT_WEEKS = 6
# 4W, 6W, 3M, 6M.
WEEK_CHOICES = (4, 6, 13, 26)
HUNDRED = Decimal(100)

UP, DOWN, FLAT = "up", "down", "flat"
HOLIDAY, NO_SESSION, PENDING = "holiday", "no_session", "pending"


class IndexNotFound(LookupError):
    """No NEPSE index rows are stored (run sync_market_indices)."""


def ordered_weekdays(on_day):
    """The trading weekdays in force on ``on_day``, first day of the week first (Mon=0)."""
    days = trading_weekdays(on_day)
    first = next(d for d in days if (d - 1) % 7 not in days)
    return sorted(days, key=lambda d: (d - first) % 7)


def week_start(day, weekdays):
    return day - timedelta(days=(day.weekday() - weekdays[0]) % 7)


def week_config_start(on_day):
    """Date the trading week in force on ``on_day`` began."""
    start = date.min
    for begins, _ in settings.NEPSE_TRADING_WEEKS:
        begins = date.fromisoformat(begins)
        if begins <= on_day:
            start = begins
    return start


def bs_label(day):
    bs = nepali_datetime.date.from_datetime_date(day)
    return f"{bs.day} {bs.strftime('%B')}"


def tone(pct):
    if pct is None or pct == 0:
        return FLAT
    return UP if pct > 0 else DOWN


def _pct(value, base):
    return (value - base) * HUNDRED / base if value is not None and base else None


def weekday_summary(weeks=DEFAULT_WEEKS, today=None):
    today = today or timezone.localdate()
    rows = IndexDaily.objects.filter(index__code=INDEX_CODE).order_by("-date")
    latest = rows.values_list("date", flat=True).first()
    if latest is None:
        raise IndexNotFound(f"No {INDEX_CODE} index rows are stored.")

    weekdays = ordered_weekdays(latest)
    config_start = week_config_start(latest)
    names = {d: date(2024, 1, 1 + d).strftime("%a") for d in range(7)}  # 2024-01-01 was a Monday

    # Walk back over the stored sessions, keeping the newest `weeks` weeks that traded.
    sessions = {}
    for row in rows.filter(date__gte=config_start).iterator():
        start = week_start(row.date, weekdays)
        if start not in sessions and len(sessions) == weeks:
            break
        sessions.setdefault(start, []).append(row)

    starts = sorted(sessions)
    if not starts:
        raise IndexNotFound(f"No {INDEX_CODE} sessions since the current trading week began.")
    first_day = starts[0]
    before = rows.filter(date__lt=first_day).values_list("close", flat=True).first()
    holidays = dict(TradingHoliday.objects.filter(
        date__gte=first_day, date__lte=starts[-1] + timedelta(days=6),
    ).values_list("date", "name"))

    # Weeks inside the window with no session at all (e.g. a Dashain closure).
    closed_weeks = []
    cursor = first_day
    while cursor < starts[-1]:
        if cursor not in sessions:
            closed_weeks.append({"week_start": cursor, "label": bs_label(cursor)})
        cursor += timedelta(days=7)

    week_rows = []
    previous_close = before       # last close before the week
    session_close = before        # last close before the day
    for start in starts:
        by_day = {row.date: row for row in sessions[start]}
        days = []
        for weekday in weekdays:
            day = start + timedelta(days=(weekday - weekdays[0]) % 7)
            row = by_day.get(day)
            if row is not None:
                # NEPSE's own % when published, else close-to-close (fallback feed rows).
                pct = row.source_change_pct if row.source_change_pct is not None else _pct(row.close, session_close)
                session_close = row.close
                days.append({"date": day, "weekday": names[weekday], "status": tone(pct),
                             "change_pct": pct, "close": row.close})
            else:
                status = HOLIDAY if day in holidays else PENDING if day >= today else NO_SESSION
                days.append({"date": day, "weekday": names[weekday], "status": status,
                             "change_pct": None, "close": None, "holiday": holidays.get(day, "")})
        last_close = max(by_day.values(), key=lambda r: r.date).close
        week_rows.append({
            "week_start": start,
            "label": bs_label(start),
            "days": days,
            "change_pct": _pct(last_close, previous_close),
            "sessions": len(by_day),
            "up_days": sum(1 for d in days if d["status"] == UP),
            "partial": any(d["status"] == PENDING for d in days),
        })
        previous_close = last_close

    columns = []
    for position, weekday in enumerate(weekdays):
        moves = [week["days"][position]["change_pct"] for week in week_rows
                 if week["days"][position]["change_pct"] is not None]
        columns.append({
            "weekday": names[weekday],
            "average_pct": sum(moves) / len(moves) if moves else None,
            "sessions": len(moves),
            "up": sum(1 for m in moves if m > 0),
            "down": sum(1 for m in moves if m < 0),
            # Oldest week first, one entry per week.
            "dots": [week["days"][position]["status"] for week in week_rows],
        })

    complete = [w for w in week_rows if not w["partial"] and w["change_pct"] is not None]
    best = max(complete, key=lambda w: w["change_pct"], default=None)
    worst = min(complete, key=lambda w: w["change_pct"], default=None)
    for week in week_rows:
        week["best"] = week is best
        week["worst"] = week is worst and worst is not best

    return {
        "index": INDEX_CODE,
        "weeks": len(week_rows),
        "today": today,
        "sessions_total": sum(w["sessions"] for w in week_rows),
        "sessions_up": sum(w["up_days"] for w in week_rows),
        "requested_weeks": weeks,
        "from": first_day,
        "to": latest,
        "trading_week": [names[d] for d in weekdays],
        "columns": columns,
        # Newest week first.
        "week_rows": list(reversed(week_rows)),
        "closed_weeks": closed_weeks,
        "insights": insights(columns, len(week_rows)),
        "notes": _notes(len(week_rows), weeks, config_start, closed_weeks),
    }


def insights(columns, week_count):
    """Up to three plain statements; each only when the data supports it."""
    found = []
    ranked = [c for c in columns if c["average_pct"] is not None]
    # One session says nothing about a weekday; claims need at least two.
    supported = [c for c in ranked if c["sessions"] >= 2]
    if supported:
        best = max(supported, key=lambda c: c["average_pct"])
        if best["average_pct"] > 0:
            found.append({"kind": "best", "weekdays": [best["weekday"]], "average_pct": best["average_pct"],
                          "up": best["up"], "sessions": best["sessions"]})
    always_up = [c for c in ranked if c["sessions"] >= 2 and c["up"] == c["sessions"]]
    if always_up:
        top = max(always_up, key=lambda c: c["sessions"])
        found.append({"kind": "always_up", "weekdays": [top["weekday"]], "sessions": top["sessions"]})
    else:
        steady = max(ranked, key=lambda c: (c["up"] / c["sessions"], c["sessions"]), default=None) if ranked else None
        if steady and steady["up"]:
            found.append({"kind": "most_up", "weekdays": [steady["weekday"]], "up": steady["up"],
                          "sessions": steady["sessions"]})
    negative = [c for c in ranked if c["average_pct"] < 0]
    if negative:
        found.append({"kind": "negative", "weekdays": [c["weekday"] for c in negative],
                      "averages": [c["average_pct"] for c in negative]})
    streaks = [(up_streak(c["dots"]), c["weekday"]) for c in columns]
    longest, weekday = max(streaks, key=lambda s: s[0], default=(0, None))
    if longest >= 2:
        found.append({"kind": "streak", "weekdays": [weekday], "sessions": longest})
    return found


def up_streak(dots):
    """Consecutive up closes counting back from the newest week; days without a session don't break it."""
    run = 0
    for status in reversed(dots):
        if status in (HOLIDAY, NO_SESSION, PENDING):
            continue
        if status != UP:
            break
        run += 1
    return run


def _notes(found, requested, config_start, closed_weeks):
    notes = []
    if found < requested:
        notes.append(
            f"Only {found} trading week(s) since the current trading week began on {config_start:%d %b %Y}."
        )
    if closed_weeks:
        notes.append("Skipped (no sessions): week of " + ", ".join(w["label"] for w in closed_weeks) + ".")
    return notes


def to_json(value):
    """Decimals as rounded numbers (the page charts them), dates as YYYY-MM-DD."""
    if isinstance(value, Decimal):
        return round(float(value), 4)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: to_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_json(item) for item in value]
    return value
