"""
Read-side filters for floorsheet trades.  Nothing here deletes or changes rows.

* Odd lots: trades under NEPSE's 10-share board lot print away from the market and do
  not set the official high / low.  Leaving them out makes the floorsheet's daily high /
  low match DailyPrice on 99.7% of company-days (vs 48.8% with them); they are 1.4% of
  trades and 0.02% of volume.
* Pre-open: the opening auction fills, all stamped in the 10:46 minute (NPT), one price
  per company-day that equals the official open.  An auction is not aggressive buying or
  selling, so they stay out of continuous-session buckets and tick-rule classification.
* Untimed days: rows from the date-only ShareSansar floorsheet have no trade_time; such
  company-days can only get a daily-level footprint, ordered by contract number.
"""

from apps.floorsheet.models import FloorsheetTransaction
from apps.floorsheet.services.intraday_candles import NPT, SESSION_OPEN

ODD_LOT_THRESHOLD = 10


def board_lots(trades):
    """``trades`` without odd lots (quantity under ODD_LOT_THRESHOLD)."""
    return trades.filter(quantity__gte=ODD_LOT_THRESHOLD)


def is_odd_lot(quantity):
    return quantity < ODD_LOT_THRESHOLD


def is_pre_open(trade_time):
    """True for an opening-auction fill (before the 11:00 continuous session).  Untimed trades are not."""
    return trade_time is not None and trade_time.astimezone(NPT).time() < SESSION_OPEN


# ``__time`` compares in the project time zone (Asia/Kathmandu), the same clock as SESSION_OPEN.
def pre_open(trades):
    return trades.filter(trade_time__isnull=False, trade_time__time__lt=SESSION_OPEN)


def continuous_session(trades):
    """Timed trades from the 11:00 open on (the 15:00:00.00x closing prints included)."""
    return trades.filter(trade_time__isnull=False, trade_time__time__gte=SESSION_OPEN)


def untimed_company_days(start=None, end=None, company_ids=None):
    """Sorted (company_id, date) pairs that have at least one trade without a trade_time."""
    rows = FloorsheetTransaction.objects.filter(trade_time__isnull=True)
    if start:
        rows = rows.filter(date__gte=start)
    if end:
        rows = rows.filter(date__lte=end)
    if company_ids is not None:
        rows = rows.filter(company_id__in=company_ids)
    return sorted(set(rows.values_list("company_id", "date").distinct()))

