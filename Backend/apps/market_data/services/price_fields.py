"""
Fill DailyPrice.transactions from floorsheet trades already stored.

The ShareSansar price-history endpoint has no transaction count, so
transactions = number of real floorsheet trades for that company-day, set
only once that day's floorsheet has been crawled (otherwise NULL, never 0).

One UPDATE statement; re-running is cheap and idempotent.
(Previous close and change are not stored -- see services.movers.)
"""

from django.db.models import Count, Exists, OuterRef, Subquery

from apps.market_data.models import DailyPrice, FloorsheetTransaction

# Seeded demo floorsheet rows use this prefix; real exchange contract numbers never do.
SYNTHETIC_TRANSACTION_PREFIX = "TX-"


def real_floorsheet():
    return FloorsheetTransaction.objects.exclude(transaction_id__startswith=SYNTHETIC_TRANSACTION_PREFIX)


def derive_price_fields(company_ids=None, source="crawled"):
    rows = DailyPrice.objects.filter(source=source)
    if company_ids is not None:
        rows = rows.filter(company_id__in=company_ids)

    same_company_day = real_floorsheet().filter(company_id=OuterRef("company_id"), date=OuterRef("date"))
    trade_count = (
        same_company_day
        .order_by()
        .values("company_id")
        .annotate(n=Count("id"))
        .values("n")
    )
    transaction_rows = rows.filter(Exists(same_company_day)).update(transactions=Subquery(trade_count))

    return {"transactions_filled": transaction_rows}
