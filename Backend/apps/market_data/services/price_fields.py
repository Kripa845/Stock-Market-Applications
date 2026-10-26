"""
Fill DailyPrice.transactions (number of trades for the company-day).

The ShareSansar price-history endpoint has no trade count, so it comes from
two other places, and is set only when it can be trusted (otherwise NULL,
never 0):

1. NEPSE's own day summary (``totalTrades`` in /api/nots/nepse-data/today-price,
   read through the nepse-data-api client in services.live_prices).  Used when
   NEPSE's traded quantity for the day equals our stored volume, i.e. both
   describe the same session.  Also serves past dates, so it can back-fill.
2. The stored floorsheet: the number of real trades for the company-day, used
   only when the floorsheet is complete (its quantities add up to the stored
   volume).  A partially crawled floorsheet would under-count, so it is skipped.

Both are idempotent; re-running is cheap.
(Previous close and change are not stored -- see services.movers.)
"""

import logging

from django.db.models import BigIntegerField, Count, Exists, F, OuterRef, Subquery, Sum

from apps.market_data.models import DailyPrice
from apps.floorsheet.models import FloorsheetTransaction

logger = logging.getLogger(__name__)

# Seeded demo floorsheet rows use this prefix; real exchange contract numbers never do.
SYNTHETIC_TRANSACTION_PREFIX = "TX-"


def real_floorsheet():
    return FloorsheetTransaction.objects.exclude(transaction_id__startswith=SYNTHETIC_TRANSACTION_PREFIX)


def derive_price_fields(company_ids=None, source="crawled"):
    """Trade counts from complete floorsheets (see the module docstring)."""
    rows = DailyPrice.objects.filter(source=source)
    if company_ids is not None:
        rows = rows.filter(company_id__in=company_ids)

    same_company_day = real_floorsheet().filter(company_id=OuterRef("company_id"), date=OuterRef("date"))
    per_day = same_company_day.order_by().values("company_id")
    trade_count = per_day.annotate(n=Count("id")).values("n")
    traded_quantity = per_day.annotate(q=Sum("quantity")).values("q")

    with_floorsheet = rows.filter(Exists(same_company_day)).annotate(
        floorsheet_quantity=Subquery(traded_quantity, output_field=BigIntegerField()),
    )
    complete = with_floorsheet.filter(floorsheet_quantity=F("volume"))
    transaction_rows = rows.filter(pk__in=complete.values("pk")).update(transactions=Subquery(trade_count))

    return {
        "transactions_filled": transaction_rows,
        "incomplete_floorsheets": with_floorsheet.exclude(floorsheet_quantity=F("volume")).count(),
    }


def missing_transaction_dates(company_ids=None, source="crawled", limit=None):
    """Session dates (newest first) where at least one stored row has no trade count."""
    rows = DailyPrice.objects.filter(source=source, transactions__isnull=True)
    if company_ids is not None:
        rows = rows.filter(company_id__in=company_ids)
    dates = rows.order_by("-date").values_list("date", flat=True).distinct()
    return list(dates[:limit] if limit else dates)


def _as_int(value):
    try:
        return None if value is None else int(value)
    except (TypeError, ValueError):
        return None


def fill_transactions_from_nepse(dates, company_ids=None, source="crawled", fetch_day=None):
    """
    Set DailyPrice.transactions from NEPSE's day summary for each date in ``dates``.

    ``fetch_day(day)`` returns {SYMBOL: NEPSE row}; the default calls NEPSE.
    A row is written only when NEPSE's traded quantity equals our volume.
    """
    if fetch_day is None:
        from apps.market_data.services.live_prices import day_summary_fetcher
        fetch_day = day_summary_fetcher()

    result = {"dates": 0, "filled": 0, "unchanged": 0, "not_in_feed": 0, "volume_mismatch": [], "empty_days": []}
    for day in dates:
        prices = DailyPrice.objects.filter(source=source, date=day).select_related("company")
        if company_ids is not None:
            prices = prices.filter(company_id__in=company_ids)
        prices = list(prices)
        if not prices:
            continue

        feed = fetch_day(day)
        result["dates"] += 1
        if not feed:
            result["empty_days"].append(day)
            continue

        changed = []
        for price in prices:
            row = feed.get(price.company.symbol.upper())
            if row is None:
                result["not_in_feed"] += 1
                continue
            trades = _as_int(row.get("totalTrades"))
            if trades is None or _as_int(row.get("totalTradedQuantity")) != price.volume:
                result["volume_mismatch"].append(f"{price.company.symbol} {day}")
                continue
            if price.transactions == trades:
                result["unchanged"] += 1
                continue
            price.transactions = trades
            changed.append(price)

        if changed:
            DailyPrice.objects.bulk_update(changed, ["transactions"])
        result["filled"] += len(changed)

    if result["volume_mismatch"]:
        logger.warning("NEPSE trade counts skipped (volume differs from ours): %s", result["volume_mismatch"])
    return result
