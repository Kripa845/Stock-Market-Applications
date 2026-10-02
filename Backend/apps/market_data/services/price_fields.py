"""
Fill DailyPrice.ltp / prev_close / transactions from data already stored.

The ShareSansar price-history endpoint returns only date, open, high, low,
close, % change, traded quantity and traded amount, so:

  ltp           = close.  The source is end-of-day; the last traded price of a
                  finished session is its close.
  prev_close    = the same company's close on its previous stored row of the
                  same source.  NOT adjusted for bonus / right / dividend book
                  closures (see market_stats.CORPORATE_ACTION_NOTE).
  transactions  = number of floorsheet trades for that company-day, set only
                  once that day's floorsheet has been crawled (otherwise NULL,
                  never 0).

Each step is one UPDATE statement, so re-running is cheap and idempotent;
prev_close is always recomputed so a back-filled gap corrects the next day.
"""

from django.db.models import Count, Exists, F, OuterRef, Subquery

from apps.market_data.models import DailyPrice, FloorsheetTransaction

# Seeded demo floorsheet rows use this prefix; real exchange contract numbers never do.
SYNTHETIC_TRANSACTION_PREFIX = "TX-"


def real_floorsheet():
    return FloorsheetTransaction.objects.exclude(transaction_id__startswith=SYNTHETIC_TRANSACTION_PREFIX)


def derive_price_fields(company_ids=None, source="crawled"):
    rows = DailyPrice.objects.filter(source=source)
    if company_ids is not None:
        rows = rows.filter(company_id__in=company_ids)

    ltp_rows = rows.filter(ltp__isnull=True).update(ltp=F("close"))

    previous_close = (
        DailyPrice.objects
        .filter(company_id=OuterRef("company_id"), source=source, date__lt=OuterRef("date"))
        .order_by("-date")
        .values("close")[:1]
    )
    prev_close_rows = rows.update(prev_close=Subquery(previous_close))

    same_company_day = real_floorsheet().filter(company_id=OuterRef("company_id"), date=OuterRef("date"))
    trade_count = (
        same_company_day
        .order_by()
        .values("company_id")
        .annotate(n=Count("id"))
        .values("n")
    )
    transaction_rows = rows.filter(Exists(same_company_day)).update(transactions=Subquery(trade_count))

    return {
        "ltp_filled": ltp_rows,
        "prev_close_rows": prev_close_rows,
        "transactions_filled": transaction_rows,
    }
