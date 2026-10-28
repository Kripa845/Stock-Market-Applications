"""
Queries that feed the indices page.

Panel A -- whole NEPSE market (MarketStockDaily + IndexDaily, all crawled).
Panel B -- tracked companies only (DailyPrice, same rules as services.movers).
"""

from datetime import timedelta

from django.db.models import Count, F, Sum

from apps.market_data.models import DailyPrice
from apps.market_data.services.market_stats import tracked_prices
from apps.market_data.services.trading_calendar import latest_trading_date, previous_trading_sessions
from apps.market_indices.models import IndexDaily, MarketIndex, MarketStockDaily
from apps.market_indices.services.calc import build_sector_rows, pct_change, pct_of

WHOLE_MARKET = "whole_market"
TRACKED = "tracked_companies"

TOP_METRICS = {"turnover", "volume", "transactions"}
SPARKLINE_SESSIONS = 30


def _totals_by_sector(queryset, sector_field):
    # values(sector=F("sector")) is rejected when the model already has a "sector" field.
    grouping = queryset.values("sector") if sector_field == "sector" else queryset.values(sector=F(sector_field))
    rows = (
        grouping.order_by()
        .annotate(
            # Counted before the Sum below, which reuses the name "transactions".
            transactions_reported=Count("transactions"),  # COUNT of non-NULL
            turnover=Sum("turnover"),
            volume=Sum("volume"),
            transactions=Sum("transactions"),      # SUM ignores NULL transactions
            companies=Count("id"),
        )
    )
    return {row["sector"]: row for row in rows}


def sector_table(queryset_today, queryset_previous, sector_field):
    """
    ``queryset_*`` are restricted to ONE session each.
    ``sector_field`` is "sector" (MarketStockDaily) or "company__sector" (DailyPrice).
    """
    today = _totals_by_sector(queryset_today, sector_field)
    previous = _totals_by_sector(queryset_previous, sector_field)
    rows, totals = build_sector_rows(today, previous)
    return {"rows": rows, "totals": totals}


# ----------------------------------------------------------------------
# Panel A: whole market
# ----------------------------------------------------------------------

def market_dates():
    """(as_of, base_date) = the two latest sessions present in MarketStockDaily."""
    dates = list(
        MarketStockDaily.objects.order_by("-date").values_list("date", flat=True).distinct()[:2]
    )
    as_of = dates[0] if dates else None
    base = dates[1] if len(dates) > 1 else None
    return as_of, base


def market_sector_table():
    as_of, base = market_dates()
    if as_of is None:
        return {
            "scope": WHOLE_MARKET, "as_of": None, "base_date": None, "rows": [], "totals": None,
            "reason": "No whole-market stock data has been crawled yet.",
            "action": "Run: cd Backend/crawlers && scrapy crawl market_stocks",
        }
    previous = (
        MarketStockDaily.objects.filter(date=base) if base else MarketStockDaily.objects.none()
    )
    data = sector_table(MarketStockDaily.objects.filter(date=as_of), previous, "sector")
    unclassified = list(
        MarketStockDaily.objects.filter(date=as_of, sector=MarketStockDaily.UNCLASSIFIED)
        .values_list("symbol", flat=True)
    )
    return {
        "scope": WHOLE_MARKET, "as_of": as_of, "base_date": base,
        "unclassified_symbols": unclassified,
        **data,
    }


def index_session(day=None):
    """The latest IndexDaily session on or before ``day`` (default: the latest stored)."""
    sessions = IndexDaily.objects.order_by("-date")
    if day is not None:
        sessions = sessions.filter(date__lte=day)
    return sessions.values_list("date", flat=True).first()


def index_table(kind, day=None):
    """
    One row per index of ``kind`` (main | sub) for the session on or before ``day``.

    CH and the turnover / volume / transaction changes compare with that index's
    previous stored session.  ``turnover_share_pct`` is the share of the NEPSE
    Index turnover (the whole market) on the same session.
    """
    session = index_session(day)
    if session is None:
        return []
    market = IndexDaily.objects.filter(index__code="NEPSE", date=session).values_list("turnover", flat=True).first()
    rows = []
    for index in MarketIndex.objects.filter(kind=kind):
        recent = list(index.daily.filter(date__lte=session).order_by("-date")[:SPARKLINE_SESSIONS])
        last_two = recent[:2]
        if not last_two or last_two[0].date != session:
            continue
        current = last_two[0]
        previous = last_two[1] if len(last_two) > 1 else None

        def change(field):
            now = getattr(current, field)
            before = getattr(previous, field) if previous else None
            return (now - before) if now is not None and before is not None else None, pct_change(now, before)

        ch, ch_pct = change("close")
        if previous and current.source_change_pct is not None:
            ch_pct = current.source_change_pct   # NEPSE's own %, from unrounded values
        tu_ch, tu_ch_pct = change("turnover")
        vol_ch, vol_ch_pct = change("volume")
        trans_ch, trans_ch_pct = change("transactions")
        rows.append({
            "code": index.code,
            "name": index.name,
            "sector": index.sector_name,
            "date": current.date,
            "previous_date": previous.date if previous else None,
            "open": current.open,
            "high": current.high,
            "low": current.low,
            "close": current.close,
            "prev_close": previous.close if previous else None,
            "ch": ch, "ch_pct": ch_pct,
            "turnover": current.turnover, "tu_ch": tu_ch, "tu_ch_pct": tu_ch_pct,
            "turnover_share_pct": pct_of(current.turnover, market),
            "volume": current.volume, "vol_ch": vol_ch, "vol_ch_pct": vol_ch_pct,
            "transactions": current.transactions, "trans_ch": trans_ch, "trans_ch_pct": trans_ch_pct,
            # Stored closes, oldest first, for the trend sparkline on Technical Charts.
            "sparkline": [row.close for row in reversed(recent)],
            # "crawled" = NEPSE's own feed; "sharesansar" = the fallback (services/sharesansar_indices).
            "source": current.source,
        })
    return rows


def sub_index_table(day=None):
    """Sub-index rows; sector totals from MarketStockDaily only fill values NEPSE did not publish."""
    index_rows = index_table(MarketIndex.KIND_SUB, day)
    sectors = market_sector_table() if any(row["turnover"] is None for row in index_rows) else {"rows": []}
    by_sector = {row["sector"]: row for row in sectors["rows"]}
    for row in index_rows:
        extra = by_sector.get(row["sector"])
        if extra and row["turnover"] is None:
            for key in (
                "turnover", "tu_ch", "tu_ch_pct", "volume", "vol_ch", "vol_ch_pct",
                "transactions", "trans_ch", "trans_ch_pct", "transactions_complete",
            ):
                row[key] = extra[key]
    return {
        "scope": WHOLE_MARKET,
        "as_of": max((r["date"] for r in index_rows), default=None),
        "rows": index_rows,
    }


def main_index_table(day=None):
    """Main indices with NEPSE's published turnover / volume / transactions.

    Only if NEPSE published none for the NEPSE Index are whole-market totals from
    MarketStockDaily used instead; other columns stay None ("—"), never guessed.
    """
    rows = index_table(MarketIndex.KIND_MAIN, day)
    needs_totals = any(row["code"] == "NEPSE" and row["turnover"] is None for row in rows)
    sectors = market_sector_table() if needs_totals else {}
    totals = sectors.get("totals")
    if totals:
        previous_totals = _previous_market_totals(sectors.get("base_date"))
        for row in rows:
            if row["code"] == "NEPSE" and row["turnover"] is None:
                row["turnover"] = totals["turnover"]
                row["tu_ch_pct"] = pct_change(totals["turnover"], previous_totals.get("turnover"))
                row["volume"] = totals["volume"]
                row["vol_ch_pct"] = pct_change(totals["volume"], previous_totals.get("volume"))
                row["transactions"] = totals["transactions"]
                row["trans_ch_pct"] = pct_change(totals["transactions"], previous_totals.get("transactions"))
    return {
        "scope": WHOLE_MARKET,
        "as_of": max((r["date"] for r in rows), default=None),
        "rows": rows,
    }


def _previous_market_totals(base_date):
    if base_date is None:
        return {}
    agg = MarketStockDaily.objects.filter(date=base_date).aggregate(
        turnover=Sum("turnover"), volume=Sum("volume"), transactions=Sum("transactions"),
    )
    return agg


def market_top(metric, limit=10):
    if metric not in TOP_METRICS:
        raise ValueError(f"metric must be one of {sorted(TOP_METRICS)}")
    as_of, _ = market_dates()
    if as_of is None:
        return {"scope": WHOLE_MARKET, "as_of": None, "metric": metric, "rows": []}
    rows = list(
        MarketStockDaily.objects.filter(date=as_of)
        .exclude(**{f"{metric}__isnull": True})
        .order_by(f"-{metric}", "symbol")[:limit]
        .values("symbol", "sector", "close", "prev_close", "volume", "turnover", "transactions")
    )
    for row in rows:
        row["ltp"] = row["close"]
        row["ch_pct"] = pct_change(row["close"], row["prev_close"])
    return {"scope": WHOLE_MARKET, "as_of": as_of, "metric": metric, "rows": rows}


# ----------------------------------------------------------------------
# Candlestick chart: one index's stored daily OHLC
# ----------------------------------------------------------------------

FIFTY_TWO_WEEK_DAYS = 365


def _text(value):
    """Decimals as strings, like the company price endpoint; NULL stays None (shown as "—")."""
    return None if value is None else str(value)


def index_candles(index, start=None, end=None):
    """
    Stored NEPSE OHLC rows of one index, oldest first, in the company price-row shape.

    ``fifty_two_week`` and ``latest`` are measured up to the latest stored session on or
    before ``end`` and ignore ``start``, so they do not change with the chart range:
      * 52-week high / low = max(high) / min(low) over the 365 days up to that session;
      * ``change_pct`` is NEPSE's own ``source_change_pct`` (never recomputed);
      * ``change`` = close minus the previous stored close, the same rule as ``index_table``.
    """
    history = index.daily.all()
    if end:
        history = history.filter(date__lte=end)
    shown = history.filter(date__gte=start) if start else history
    prices = [
        {
            "id": row.id,
            "date": row.date,
            "open": _text(row.open),
            "high": _text(row.high),
            "low": _text(row.low),
            "close": _text(row.close),
            "volume": row.volume,
            "turnover": _text(row.turnover),
        }
        for row in shown.order_by("date")
    ]

    last_two = list(history.order_by("-date")[:2])
    if not last_two:
        return {"prices": prices, "fifty_two_week": None, "latest": None}
    current = last_two[0]
    previous = last_two[1] if len(last_two) > 1 else None

    window = history.filter(date__gte=current.date - timedelta(days=FIFTY_TWO_WEEK_DAYS))
    high_row = window.filter(high__isnull=False).order_by("-high", "-date").first()
    low_row = window.filter(low__isnull=False).order_by("low", "-date").first()
    return {
        "prices": prices,
        "fifty_two_week": {
            "from": current.date - timedelta(days=FIFTY_TWO_WEEK_DAYS),
            "to": current.date,
            "high": _text(high_row.high) if high_row else None,
            "high_date": high_row.date if high_row else None,
            "low": _text(low_row.low) if low_row else None,
            "low_date": low_row.date if low_row else None,
        },
        "latest": {
            "date": current.date,
            "close": _text(current.close),
            "previous_date": previous.date if previous else None,
            "previous_close": _text(previous.close) if previous else None,
            "change": _text(current.close - previous.close) if previous else None,
            "change_pct": _text(current.source_change_pct),
        },
    }


def index_daily_changes(index, start, end):
    """
    {date: row} for every stored session of ``index`` from ``start`` to ``end`` (inclusive).

    Same change rule as ``index_candles``: ``change`` = close minus the previous stored
    close, ``change_pct`` = NEPSE's own ``source_change_pct``.  The previous close of the
    first session comes from the last row before ``start``, so a month view doesn't lose
    its first day's change.
    """
    rows = list(index.daily.filter(date__gte=start, date__lte=end).order_by("date"))
    previous = index.daily.filter(date__lt=start).order_by("-date").first()
    changes = {}
    for row in rows:
        changes[row.date] = {
            "open": _text(row.open),
            "high": _text(row.high),
            "low": _text(row.low),
            "close": _text(row.close),
            "change": _text(row.close - previous.close) if previous else None,
            "change_pct": _text(row.source_change_pct),
            "previous_date": previous.date if previous else None,
            "turnover": _text(row.turnover),
            "volume": row.volume,
            "transactions": row.transactions,
            "source": row.source,
        }
        previous = row
    return changes


# ----------------------------------------------------------------------
# Panel B: tracked companies only
# ----------------------------------------------------------------------

def tracked_sector_table():
    as_of = latest_trading_date()
    if as_of is None:
        return {
            "scope": TRACKED, "as_of": None, "base_date": None, "rows": [], "totals": None,
            "reason": "No crawled price data yet.",
        }
    earlier = previous_trading_sessions(as_of, 1)
    base = earlier[0] if earlier else None
    previous = tracked_prices().filter(date=base) if base else DailyPrice.objects.none()
    data = sector_table(tracked_prices().filter(date=as_of), previous, "company__sector")

    result = {"scope": TRACKED, "as_of": as_of, "base_date": base, **data}

    # Reuse the project's own partial-crawl warning (known issue #1).
    try:
        from apps.market_data.services.movers import incomplete_session_warning
        from apps.market_data.services.market_stats import tracked_companies

        tracked = tracked_companies().count()
        present = tracked_prices().filter(date=as_of).values("company").distinct().count()
        missing = tracked - present
        if missing > 0:
            result["warning"] = incomplete_session_warning(as_of, missing, tracked)
    except Exception:  # never break the table because of the warning helper
        pass
    return result
