"""
Sessions where our stored prices are NOT adjusted for a bonus / right share issue.

DailyPrice keeps the raw published close.  ShareSansar's ``source_change_pct`` is
measured against NEPSE's previous close, which the exchange adjusts on a book
closure.  When the two changes disagree by more than ADJUSTMENT_GAP_PCT the
previous close was adjusted and ours was not, so anything spanning that session
(RSI, MACD, moving averages, 52-week range) mixes pre- and post-issue prices.

Nothing here changes data; it only reports the sessions.
"""

from decimal import Decimal

from apps.market_data.models import DailyPrice

# Above rounding (the source % has 2 decimals) and the odd late close revision;
# every gap above this on 2026-11-01 lined up with a bonus / right book closure.
ADJUSTMENT_GAP_PCT = Decimal("1")


def adjustment_sessions(company_ids=None):
    """{company_id: [{date, close_to_close_pct, source_change_pct}, ...]} oldest first."""
    prices = DailyPrice.objects.filter(source="crawled").order_by("company_id", "date")
    if company_ids is not None:
        prices = prices.filter(company_id__in=company_ids)
    result = {}
    previous = None
    for company_id, day, close, source_pct in prices.values_list("company_id", "date", "close", "source_change_pct"):
        if previous and previous[0] == company_id and source_pct is not None and previous[1] > 0:
            ours = (close - previous[1]) / previous[1] * 100
            if abs(ours - source_pct) > ADJUSTMENT_GAP_PCT:
                result.setdefault(company_id, []).append({
                    "date": day,
                    "close_to_close_pct": ours.quantize(Decimal("0.01")),
                    "source_change_pct": source_pct,
                })
        previous = (company_id, close)
    return result
