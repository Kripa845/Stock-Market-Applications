"""
Rows for the watchlist page: each saved company's latest crawled session plus the
holding the user entered (units, WACC) and what it is worth at that close.

Prices come only from crawled DailyPrice rows (PRICE_SOURCE), never "unverified" ones,
so a saved company that has never been crawled shows null prices rather than made-up ones.
Any active company can be saved, tracked or not.
"""

from decimal import Decimal

from django.db.models import F, Window
from django.db.models.functions import RowNumber

from apps.market_data.models import DailyPrice
from apps.market_data.services.market_stats import PRICE_SOURCE

SPARKLINE_SESSIONS = 30
HUNDRED = Decimal("100")
TWO_PLACES = Decimal("0.01")


def _recent_sessions(company_ids):
    """The last SPARKLINE_SESSIONS crawled rows per company, oldest first."""
    recent = (
        DailyPrice.objects
        .filter(source=PRICE_SOURCE, company_id__in=company_ids)
        .annotate(position=Window(RowNumber(), partition_by=[F("company_id")], order_by=F("date").desc()))
        .filter(position__lte=SPARKLINE_SESSIONS)
        .order_by("company_id", "date")
        .values("company_id", "date", "high", "low", "close", "volume", "turnover", "source_change_pct")
    )
    by_company = {}
    for row in recent:
        by_company.setdefault(row["company_id"], []).append(row)
    return by_company


def _change(latest, previous):
    """(change, change_pct): the source's % when crawled (corporate-action adjusted), else close-to-close."""
    close = latest["close"]
    pct = latest["source_change_pct"]
    if pct is not None and pct > -100:
        reference = close * HUNDRED / (HUNDRED + pct)
        return (close - reference).quantize(TWO_PLACES), pct.quantize(TWO_PLACES)
    if previous and previous["close"]:
        change = close - previous["close"]
        return change, (change * HUNDRED / previous["close"]).quantize(TWO_PLACES)
    return None, None


def _holding(units, wacc, ltp):
    investment = (Decimal(units) * wacc).quantize(TWO_PLACES)
    current_value = (Decimal(units) * ltp).quantize(TWO_PLACES) if ltp is not None else None
    profit = current_value - investment if current_value is not None else None
    profit_pct = (profit * HUNDRED / investment).quantize(TWO_PLACES) if profit is not None and investment else None
    return {"investment": investment, "current_value": current_value, "profit": profit, "profit_pct": profit_pct}


def item_rows(items):
    """One row per WatchlistItem (company must be select_related), in the given order."""
    items = list(items)
    sessions = _recent_sessions([item.company_id for item in items])
    rows = []
    for item in items:
        company = item.company
        history = sessions.get(company.id, [])
        latest = history[-1] if history else None
        previous = history[-2] if len(history) > 1 else None
        change, change_pct = _change(latest, previous) if latest else (None, None)
        ltp = latest["close"] if latest else None
        rows.append({
            "id": item.id,
            "watchlist_id": item.watchlist_id,
            "company_id": company.id,
            "symbol": company.symbol,
            "name": company.name,
            "sector": company.sector,
            "logo_url": company.logo_url,
            "trade_date": latest["date"] if latest else None,
            "ltp": ltp,
            "high": latest["high"] if latest else None,
            "low": latest["low"] if latest else None,
            "change": change,
            "change_pct": change_pct,
            "volume": latest["volume"] if latest else None,
            "turnover": latest["turnover"] if latest else None,
            "sparkline": [{"date": row["date"], "close": row["close"]} for row in history],
            "units": item.units,
            "wacc": item.wacc,
            **_holding(item.units, item.wacc, ltp),
            "created_at": item.created_at,
        })
    return rows


def summary(rows):
    """Totals for the summary cards; average WACC = total investment / total units."""
    units = sum(row["units"] for row in rows)
    investment = sum((row["investment"] for row in rows), Decimal("0"))
    valued = [row for row in rows if row["current_value"] is not None]
    current_value = sum((row["current_value"] for row in valued), Decimal("0"))
    valued_investment = sum((row["investment"] for row in valued), Decimal("0"))
    profit = current_value - valued_investment
    return {
        "total_units": units,
        "average_wacc": (investment / units).quantize(TWO_PLACES) if units else Decimal("0"),
        "current_value": current_value,
        "investment": investment,
        "profit": profit,
        "profit_pct": (profit * HUNDRED / valued_investment).quantize(TWO_PLACES) if valued_investment else Decimal("0"),
    }
