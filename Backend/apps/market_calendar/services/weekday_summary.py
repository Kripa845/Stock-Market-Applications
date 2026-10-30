"""
Which weekday pays: the tracked companies' daily moves by weekday over the last N trading weeks.

Scopes: ``tracked`` (every tracked company the user may access) or ``tracked:<sector>``.
Each is an equal-weighted basket: a day's move is the plain average of each company's session
change from ``movers`` (adjusted for bonus / right shares like the movers pages), and a week's
move compounds those daily averages.  Companies with no price, no trade, no previous session
or a suspected corporate action that day are left out of that day's average (``excluded``).

Days are stored sessions only (today's figures appear once prices are crawled after the close).
The window never crosses a change of trading week (Sunday-Thursday until 2026-04-05), so
every week has the same weekday columns.
"""

import hashlib
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal

import nepali_datetime
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.companies.models import Company
from apps.market_data.models import DailyPrice, TradingHoliday
from apps.market_data.services.market_stats import PRICE_SOURCE, tracked_companies
from apps.market_data.services.movers import RANKED, annotated_companies, resolve_sessions
from apps.market_data.services.trading_days import trading_weekdays

TRACKED_SCOPE = "tracked"
DEFAULT_SCOPE = TRACKED_SCOPE
BASKET_CACHE_SECONDS = 60 * 60
DEFAULT_WEEKS = 6
# 4W, 6W, 3M, 6M.
WEEK_CHOICES = (4, 6, 13, 26)
HUNDRED = Decimal(100)

UP, DOWN, FLAT = "up", "down", "flat"
HOLIDAY, NO_SESSION, PENDING = "holiday", "no_session", "pending"


class NoSessions(LookupError):
    """No crawled prices for the scope's companies yet."""


class ScopeError(ValueError):
    """Unknown scope, or no accessible tracked companies in it (the view answers 400)."""


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


class Basket:
    """An equal-weighted basket of tracked companies."""

    def __init__(self, company_ids, label):
        self.company_ids = sorted(company_ids)
        self.label = label
        self.symbols = list(
            Company.objects.filter(id__in=self.company_ids).order_by("symbol").values_list("symbol", flat=True)
        )
        self.cache_prefix = "weekday-basket:" + hashlib.md5(",".join(map(str, self.company_ids)).encode()).hexdigest()

    def dates(self):
        """Newest-first dates with crawled prices for any of the companies."""
        return list(
            DailyPrice.objects.filter(source=PRICE_SOURCE, company_id__in=self.company_ids)
            .order_by("-date").values_list("date", flat=True).distinct()
        )

    def sessions(self, dates):
        # ~25 ms of SQL per day, so finished days are cached (6M = ~125 days); the newest day
        # is always recomputed because its prices can still be re-crawled.
        newest = max(dates)
        keys = {day: f"{self.cache_prefix}:{day.isoformat()}" for day in dates if day != newest}
        cached = cache.get_many(list(keys.values()))
        result = {day: cached[key] for day, key in keys.items() if cached.get(key)}
        fresh = self._compute([day for day in dates if day not in result])
        cache.set_many({keys[day]: value for day, value in fresh.items() if day in keys}, BASKET_CACHE_SECONDS)
        return {**result, **fresh}

    def _compute(self, dates):
        result = {}
        for day in dates:
            as_of, base_date, window = resolve_sessions(day)
            if as_of != day:
                continue
            rows = list(
                annotated_companies(day, base_date, window, self.company_ids)
                .values("symbol", "change_pct", "bucket")
            )
            moved = [r for r in rows if r["bucket"] in RANKED and r["change_pct"] is not None]
            if not moved:
                continue
            best = max(moved, key=lambda r: r["change_pct"])
            worst = min(moved, key=lambda r: r["change_pct"])
            result[day] = {
                "change_pct": sum(r["change_pct"] for r in moved) / len(moved),
                "companies": len(moved),
                "companies_up": sum(1 for r in moved if r["change_pct"] > 0),
                "excluded": len(self.company_ids) - len(moved),
                "best": {"symbol": best["symbol"], "change_pct": best["change_pct"]},
                "worst": {"symbol": worst["symbol"], "change_pct": worst["change_pct"]},
            }
        return result


def scope_catalogue(company_ids=None):
    """What the scope picker offers: all tracked companies, then each tracked sector."""
    tracked = tracked_companies(company_ids)
    sectors = Counter(tracked.values_list("sector", flat=True))
    return {
        "tracked": [{"scope": TRACKED_SCOPE, "label": "All tracked companies", "companies": tracked.count()}] if tracked.exists() else [],
        "tracked_sectors": [
            {"scope": f"{TRACKED_SCOPE}:{sector}", "label": sector or "No sector", "companies": count}
            for sector, count in sorted(sectors.items(), key=lambda item: (-item[1], item[0] or ""))
        ],
    }


def resolve_scope(scope, company_ids=None):
    """``tracked`` or ``tracked:<sector>`` -> Basket; ScopeError when unknown or empty."""
    if scope != TRACKED_SCOPE and not scope.startswith(f"{TRACKED_SCOPE}:"):
        raise ScopeError(f"Unknown scope {scope!r}.")
    companies = tracked_companies(company_ids)
    label = "Tracked companies"
    if ":" in scope:
        sector = scope.split(":", 1)[1]
        companies = companies.filter(sector=sector)
        label = f"Tracked {sector}"
    ids = list(companies.values_list("id", flat=True))
    if not ids:
        raise ScopeError(f"No tracked companies you can access in scope {scope!r}.")
    return Basket(ids, label)


def week_change(sessions):
    """The week's daily averages compounded."""
    growth = Decimal(1)
    for day in sorted(sessions):
        growth *= 1 + sessions[day]["change_pct"] / HUNDRED
    return (growth - 1) * HUNDRED


def weekday_summary(weeks=DEFAULT_WEEKS, today=None, scope=DEFAULT_SCOPE, company_ids=None):
    today = today or timezone.localdate()
    basket = resolve_scope(scope, company_ids)
    all_dates = basket.dates()
    if not all_dates:
        raise NoSessions(f"No crawled prices for {basket.label} yet.")
    latest = all_dates[0]

    weekdays = ordered_weekdays(latest)
    config_start = week_config_start(latest)
    names = {d: date(2024, 1, 1 + d).strftime("%a") for d in range(7)}  # 2024-01-01 was a Monday

    # Walk back over the stored sessions, keeping the newest `weeks` weeks that traded.
    by_week = {}
    for day in all_dates:
        if day < config_start:
            break
        start = week_start(day, weekdays)
        if start not in by_week and len(by_week) == weeks:
            break
        by_week.setdefault(start, []).append(day)

    starts = sorted(by_week)
    if not starts:
        raise NoSessions(f"No {basket.label} sessions since the current trading week began.")
    first_day = starts[0]
    values = basket.sessions([day for days in by_week.values() for day in days])
    holidays = dict(TradingHoliday.objects.filter(
        date__gte=first_day, date__lte=starts[-1] + timedelta(days=6),
    ).values_list("date", "name"))

    # Weeks inside the window with no session at all (e.g. a Dashain closure).
    closed_weeks = []
    cursor = first_day
    while cursor < starts[-1]:
        if cursor not in by_week:
            closed_weeks.append({"week_start": cursor, "label": bs_label(cursor)})
        cursor += timedelta(days=7)

    week_rows = []
    for start in starts:
        by_day = {day: values[day] for day in by_week[start] if day in values}
        days = []
        for weekday in weekdays:
            day = start + timedelta(days=(weekday - weekdays[0]) % 7)
            value = by_day.get(day)
            if value is not None:
                days.append({"date": day, "weekday": names[weekday], "status": tone(value["change_pct"]), **value})
            else:
                status = HOLIDAY if day in holidays else PENDING if day >= today else NO_SESSION
                days.append({"date": day, "weekday": names[weekday], "status": status,
                             "change_pct": None, "holiday": holidays.get(day, "")})
        week_rows.append({
            "week_start": start,
            "label": bs_label(start),
            "days": days,
            "change_pct": week_change(by_day) if by_day else None,
            "sessions": len(by_day),
            "up_days": sum(1 for d in days if d["status"] == UP),
            "partial": any(d["status"] == PENDING for d in days),
        })

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
        "scope": scope,
        "scope_label": basket.label,
        "companies": len(basket.company_ids),
        "symbols": basket.symbols,
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
    """Plain statements, each only when the data supports it."""
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
