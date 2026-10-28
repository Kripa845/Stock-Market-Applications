"""
One session's market picture for the calendar's day panel: summary, top gainers / losers,
top volume / transactions and top brokers.

Everything is reused, nothing is recomputed here:
  * gainers / losers / summary / top lists -> market_data.services.movers (the only movers rule);
  * brokers -> analysis.services.brokers.build_broker_activity (as /api/analysis/brokers/top/).

These cover the TRACKED companies only (DailyPrice, floorsheet); the whole-market totals are
the NEPSE index row in the day view.  The movers services fall back to the last session on or
before a date, so every section is dropped unless that session is the requested day itself:
a holiday never shows the previous day's lists.
"""

from django.db.models import Min

from apps.analysis.services.brokers import build_broker_activity
from apps.floorsheet.models import Broker, FloorsheetTransaction
from apps.market_data.services import movers

TOP_N = 5

MOVER_FIELDS = ("symbol", "name", "logo_url", "close", "change", "change_pct", "volume", "turnover", "transactions")
SUMMARY_FIELDS = (
    "previous_trade_date", "tracked_count", "advanced", "declined", "unchanged",
    "positive_circuit", "negative_circuit", "total_turnover", "total_traded_shares",
    "total_transactions", "transactions_reported", "warning",
)


def _compact(rows):
    return [{field: row.get(field) for field in MOVER_FIELDS} for row in rows]


def _top(metric, day, company_ids):
    data = movers.top_by(metric, requested_date=day, company_ids=company_ids, limit=TOP_N)
    # NULL means "not crawled", never 0 (trade counts exist only for floorsheet days).
    return _compact(row for row in data["rows"] if row.get(metric) is not None)


def _brokers(day, company_ids):
    activity = build_broker_activity(date=day, company_ids=company_ids)
    if not activity["transaction_count"]:
        return None
    ranked = sorted(activity["brokers"], key=lambda row: (-row["total_value"], row["broker"]))[:TOP_N]
    names = dict(Broker.objects.filter(broker_code__in=[row["broker"] for row in ranked]).values_list("broker_code", "name"))
    return {
        "transaction_count": activity["transaction_count"],
        "broker_count": activity["broker_count"],
        "rows": [
            {
                "broker": row["broker"],
                "name": names.get(row["broker"]) or f"Broker {row['broker']}",
                "buy_value": row["buy_value"],
                "sell_value": row["sell_value"],
                "net_value": row["net_value"],
                "total_value": row["total_value"],
                "trades": row["trades"],
            }
            for row in ranked
        ],
    }


def market_day(day, *, company_ids=None, include_brokers=True):
    """
    The session ``day`` for the companies in ``company_ids`` (None = every tracked company),
    or ``{"available": False, ...}`` when no prices were crawled for that exact day.
    ``include_brokers=False`` (no view_analysis) leaves ``brokers`` out.
    """
    result = {"scope": "tracked_companies", "date": day}

    summary = movers.tracked_summary(requested_date=day, company_ids=company_ids)
    if summary.get("trade_date") != day:
        return {**result, "available": False, "reason": "No crawled prices for this day."}

    session = movers.tracked_movers("1D", requested_date=day, company_ids=company_ids, limit=TOP_N, lean=True)
    result.update(
        available=True,
        summary={field: summary.get(field) for field in SUMMARY_FIELDS},
        gainers=_compact(session["gainers"]),
        losers=_compact(session["losers"]),
        top_volume=_top("volume", day, company_ids),
        top_transactions=_top("transactions", day, company_ids),
    )
    if include_brokers:
        result["brokers"] = _brokers(day, company_ids)
        if result["brokers"] is None:
            # Only looked up to explain the gap: it scans the trades table.
            result["floorsheet_from"] = FloorsheetTransaction.objects.aggregate(first=Min("date"))["first"]
    return result
