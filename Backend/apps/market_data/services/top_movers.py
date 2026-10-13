"""
Top Gainers / Losers / Turnover / Volume / Transactions pages for the TRACKED companies
(GET /api/market/top-gainers/ and /api/market/top-activity/).

Every period except Today is the official end-of-day view from services.movers:
crawled closes, with ShareSansar's exchange-adjusted % compounded per session when
"Adjusted Price" is on.

Today uses NEPSE's live feed (services.live_prices) while the live session is newer
than the last crawled close -- during market hours and until the 18:00 price crawl --
and the crawled close after that.  Live rows are unofficial until the session closes.
"""

from decimal import Decimal

from django.db.models import BigIntegerField, Count, DecimalField, F, IntegerField, Max, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce

from apps.market_data.models import DailyPrice
from apps.market_data.services import movers
from apps.market_data.services.live_prices import NPT, is_stale, last_successful_fetch
from apps.market_data.services.market_stats import PRICE_SOURCE, tracked_companies
from apps.market_data.services.trading_calendar import latest_trading_date, previous_trading_sessions
from apps.market_data.services.trading_days import is_market_open

SIDES = {"gainers": "gainer", "losers": "loser"}

# Query value -> (movers period, label).  Periods count NEPSE trading sessions, so
# "1 Week" and "5 Days" are the same 5 sessions.
PERIODS = {
    "today": ("1D", "Today"),
    "2d": ("2S", "2 Days"),
    "3d": ("3S", "3 Days"),
    "5d": ("5S", "5 Days"),
    "7d": ("7S", "7 Days"),
    "1w": ("5S", "1 Week"),
    "1m": ("20S", "1 Month"),
    "3m": ("60S", "3 Months"),
    "4m": ("80S", "4 Months"),
    "6m": ("120S", "6 Months"),
    "1y": ("240S", "1 Year"),
}

TWO_PLACES = Decimal("0.01")
ROW_KEYS = ("symbol", "name", "logo_url", "sector", "ltp", "change", "change_pct", "adjusted", "last_updated")


def _two(value):
    return None if value is None else Decimal(value).quantize(TWO_PLACES)


def _npt(moment):
    """Aware datetime -> ISO string in Nepal time (None stays None)."""
    return None if moment is None else moment.astimezone(NPT).isoformat()


def live_session_date(company_ids=None):
    """Date of the live session when it is newer than the last crawled close, else None."""
    latest = tracked_companies(company_ids).aggregate(at=Max("prices_updated_at"))["at"]
    if latest is None:
        return None
    session = latest.astimezone(NPT).date()
    crawled = latest_trading_date()
    return session if crawled is None or session > crawled else None


def _live_rows(session, side, adjusted, company_ids):
    """
    Today's live rows for one side.

    Adjusted: against NEPSE's previous close (already adjusted by the exchange for
    bonus / right shares).  Not adjusted: against our crawled close of the previous
    session, and -- like services.movers -- a move beyond the daily circuit is then
    treated as a corporate action and left out.
    """
    companies = list(
        tracked_companies(company_ids)
        .only("id", "symbol", "name", "sector", "logo_url", "ltp", "previous_close", "prices_updated_at")
    )
    earlier = previous_trading_sessions(session, 1)
    raw_close = dict(
        DailyPrice.objects
        .filter(source=PRICE_SOURCE, date=earlier[0], company__in=[c.id for c in companies])
        .values_list("company_id", "close")
    ) if earlier else {}

    rows = []
    for c in companies:
        traded = c.prices_updated_at is not None and c.prices_updated_at.astimezone(NPT).date() == session
        if not traded or c.ltp is None:
            continue
        raw = raw_close.get(c.id)
        base = c.previous_close if adjusted else raw
        if base is None or base <= 0:
            continue
        change = c.ltp - base
        change_pct = change * 100 / base
        if not adjusted and abs(change_pct) > movers.CORPORATE_ACTION_PCT:
            continue
        if (side == "gainer" and change_pct <= 0) or (side == "loser" and change_pct >= 0):
            continue
        raw_pct = (c.ltp - raw) * 100 / raw if raw else None
        rows.append({
            "symbol": c.symbol, "name": c.name, "logo_url": c.logo_url, "sector": c.sector,
            "ltp": c.ltp, "change": _two(change), "change_pct": _two(change_pct),
            "adjusted": adjusted and raw_pct is not None
            and abs(change_pct - raw_pct) > movers.ADJUSTMENT_TOLERANCE_PCT,
            "last_updated": _npt(c.prices_updated_at),
        })
    sign = -1 if side == "gainer" else 1
    rows.sort(key=lambda r: (sign * r["change_pct"], r["symbol"]))
    return rows, (earlier[0] if earlier else None)


def top_movers(side="gainers", period="today", sector=None, adjusted=True, page=1, page_size=20, company_ids=None):
    """One page of gainers or losers; ``side`` and ``period`` are validated keys of SIDES / PERIODS."""
    bucket = SIDES[side]
    movers_period, label = PERIODS[period]
    sectors = sorted(set(tracked_companies(company_ids).values_list("sector", flat=True)))
    out = {
        "side": side,
        "period": period,
        "period_label": label,
        "adjusted": adjusted,
        "sector": sector or None,
        "sectors": sectors,
        "page": page,
        "page_size": page_size,
        "market_open": is_market_open(),
        "live": False,
    }

    session = live_session_date(company_ids) if movers_period == "1D" else None
    if session is not None:
        rows, base_date = _live_rows(session, bucket, adjusted, company_ids)
        if sector:
            rows = [r for r in rows if r["sector"] == sector]
        last_fetch = last_successful_fetch()
        start = (page - 1) * page_size
        out.update(
            live=True,
            stale=is_stale(last_fetch),
            last_successful_fetch=last_fetch,
            as_of=session,
            base_date=base_date,
            total=len(rows),
            rows=rows[start:start + page_size],
        )
    else:
        data = movers.tracked_movers_page(
            side=bucket, period=movers_period, sector=sector or None, adjusted=adjusted,
            page=page, page_size=page_size, company_ids=company_ids,
        )
        rows = [{
            "symbol": r["symbol"], "name": r["name"], "logo_url": r["logo_url"], "sector": r["sector"],
            "ltp": r["close"], "change": _two(r["change"]), "change_pct": _two(r["change_pct"]),
            "adjusted": r["adjusted"], "last_updated": _npt(r["last_updated"]),
        } for r in data["rows"]]
        out.update(as_of=data["as_of"], base_date=data["base_date"], total=data["total"], rows=rows)
        for key in ("reason", "action"):
            if data.get(key):
                out[key] = data[key]

    out["pages"] = max(1, -(-out["total"] // page_size))
    return out


# --- Top Turnover / Volume / Transactions -----------------------------------------------------

# Metric -> (DailyPrice field, output field for its sum over the period).
METRICS = {
    "turnover": ("turnover", DecimalField(max_digits=24, decimal_places=2)),
    "volume": ("volume", BigIntegerField()),
    "transactions": ("transactions", BigIntegerField()),
}
ACTIVITY_ROW_KEYS = ("symbol", "name", "logo_url", "sector", "ltp", "change_pct", "value",
                     "sessions_traded", "complete")


def top_activity(metric="turnover", period="today", sector=None, page=1, page_size=20, company_ids=None):
    """
    Tracked companies ranked by turnover, volume or transactions summed over the period's
    sessions (official crawled rows only; the live feed has none of these).

    ``complete`` is False when some traded sessions in the period have no trade count yet
    (transactions are filled from the floorsheet), so that total is a lower bound.
    """
    field, output = METRICS[metric]
    movers_period, label = PERIODS[period]
    sessions = movers.PERIODS[movers_period]["sessions"]
    as_of, base_date, window_dates = movers.resolve_sessions(None, sessions)
    out = {
        "metric": metric,
        "period": period,
        "period_label": label,
        "sector": sector or None,
        "sectors": sorted(set(tracked_companies(company_ids).values_list("sector", flat=True))),
        "page": page,
        "page_size": page_size,
        "market_open": is_market_open(),
        "live": False,
        "as_of": as_of,
        "base_date": base_date,
        "first_session": window_dates[-1] if window_dates else None,
        "total": 0,
        "pages": 1,
        "rows": [],
    }
    if as_of is None:
        out["reason"] = "No crawled trading day yet."
        out["action"] = movers.NO_DATA_ACTION
        return out

    traded = (
        DailyPrice.objects
        .filter(company=OuterRef("pk"), source=PRICE_SOURCE, date__in=window_dates, volume__gt=0)
        .order_by().values("company")
    )

    def count_of(queryset):
        return Coalesce(
            Subquery(queryset.annotate(n=Count("id")).values("n")[:1], output_field=IntegerField()),
            Value(0), output_field=IntegerField(),
        )

    qs = movers.annotated_companies(as_of, base_date, window_dates, company_ids).annotate(
        value=Subquery(traded.annotate(v=Sum(field)).values("v")[:1], output_field=output),
        sessions_traded=count_of(traded),
        sessions_known=count_of(traded.filter(**{field + "__isnull": False})),
    ).filter(value__gt=0)
    if sector:
        qs = qs.filter(sector=sector)

    total = qs.count()
    start = (page - 1) * page_size
    rows = qs.order_by(F("value").desc(), "symbol").values(
        "symbol", "name", "logo_url", "sector", "close", "change_pct", "bucket",
        "value", "sessions_traded", "sessions_known",
    )[start:start + page_size]
    out["rows"] = [{
        "symbol": r["symbol"], "name": r["name"], "logo_url": r["logo_url"], "sector": r["sector"],
        "ltp": r["close"],
        # The period's change only where services.movers can rank it (not for no-trade or corporate-action rows).
        "change_pct": _two(r["change_pct"]) if r["bucket"] in movers.RANKED else None,
        "value": r["value"],
        "sessions_traded": r["sessions_traded"],
        "complete": r["sessions_known"] == r["sessions_traded"],
    } for r in rows]
    out.update(total=total, pages=max(1, -(-total // page_size)))
    if base_date is None:
        out["warning"] = f"Fewer than {sessions + 1} crawled sessions: the % change for {label} is not available."
    return out
