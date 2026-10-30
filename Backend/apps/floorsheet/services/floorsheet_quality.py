"""
Read-only checks of the stored floorsheet against DailyPrice (source="crawled"), used by the
``floorsheet_quality_report`` command and the tests.  Nothing here writes.
"""

from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from django.db.models import Max, Min, Q, Sum

from apps.floorsheet.models import FloorsheetTransaction, IntradayCandle
from apps.floorsheet.services.intraday_candles import INTERVAL_MINUTES, NPT, SESSION_OPEN, bucket_start_for
from apps.floorsheet.services.trade_filters import ODD_LOT_THRESHOLD, board_lots, continuous_session, pre_open
from apps.market_data.models import DailyPrice

TOLERANCE = Decimal("0.005")


def _daily_prices(start=None, end=None, company_ids=None):
    rows = DailyPrice.objects.filter(source="crawled")
    if start:
        rows = rows.filter(date__gte=start)
    if end:
        rows = rows.filter(date__lte=end)
    if company_ids is not None:
        rows = rows.filter(company_id__in=company_ids)
    return {(r["company_id"], r["date"]): r for r in rows.values("company_id", "date", "high", "low", "volume")}


def _trades(start=None, end=None, company_ids=None):
    rows = FloorsheetTransaction.objects.all()
    if start:
        rows = rows.filter(date__gte=start)
    if end:
        rows = rows.filter(date__lte=end)
    if company_ids is not None:
        rows = rows.filter(company_id__in=company_ids)
    return rows


def compare_with_daily_prices(start=None, end=None, company_ids=None, odd_lots=False):
    """
    Per company-day: floorsheet volume (always every trade, as DailyPrice counts them) and high /
    low (board lots only unless ``odd_lots``) against DailyPrice.  Only days present in both count
    toward the match rates; the rest are listed as missing on one side.
    """
    trades = _trades(start, end, company_ids)
    # Without a range, only the floorsheet's own span counts (DailyPrice goes back further).
    span = trades.aggregate(first=Min("date"), last=Max("date"))
    dp = _daily_prices(start or span["first"], end or span["last"], company_ids)
    volume = {(r["company_id"], r["date"]): r["v"]
              for r in trades.values("company_id", "date").annotate(v=Sum("quantity"))}
    ranged = trades if odd_lots else board_lots(trades)
    ranges = {(r["company_id"], r["date"]): (r["hi"], r["lo"])
              for r in ranged.values("company_id", "date").annotate(hi=Max("rate"), lo=Min("rate"))}

    both = sorted(set(dp) & set(volume))
    volume_mismatches = [(key, volume[key], dp[key]["volume"]) for key in both if volume[key] != dp[key]["volume"]]
    range_mismatches = []
    for key in both:
        hi, lo = ranges.get(key, (None, None))
        if hi is None or abs(hi - dp[key]["high"]) > TOLERANCE or abs(lo - dp[key]["low"]) > TOLERANCE:
            range_mismatches.append((key, hi, dp[key]["high"], lo, dp[key]["low"]))
    return {
        "company_days": len(both),
        "volume_matched": len(both) - len(volume_mismatches),
        "volume_mismatches": volume_mismatches,
        "high_low_matched": len(both) - len(range_mismatches),
        "high_low_mismatches": range_mismatches,
        "missing_floorsheet": sorted(set(dp) - set(volume)),
        "missing_daily_price": sorted(set(volume) - set(dp)),
    }


def trade_counts(start=None, end=None):
    trades = _trades(start, end)
    return {
        "trades": trades.count(),
        "untimed": trades.filter(trade_time__isnull=True).count(),
        "odd_lots": trades.filter(quantity__lt=ODD_LOT_THRESHOLD).count(),
        "pre_open": pre_open(trades).count(),
        "pre_open_company_days": pre_open(trades).values("company_id", "date").distinct().count(),
        "continuous": continuous_session(trades).count(),
    }


def candle_filter_impact(start=None, end=None):
    """
    How many stored IntradayCandle rows would change if the builder left out odd lots (high /
    low), and how many 11:00 candles hold pre-open fills (their open / volume would change if
    those were kept out).  Per interval; per-minute aggregates rolled up as intraday_candles does.
    """
    minutes = (
        _trades(start, end).filter(trade_time__isnull=False)
        .values("company_id", "date", "trade_time__hour", "trade_time__minute")     # Asia/Kathmandu
        .annotate(
            hi=Max("rate"), lo=Min("rate"),
            board_hi=Max("rate", filter=Q(quantity__gte=ODD_LOT_THRESHOLD)),
            board_lo=Min("rate", filter=Q(quantity__gte=ODD_LOT_THRESHOLD)),
        )
    )
    minutes = [
        (m["company_id"], m["date"],
         datetime(m["date"].year, m["date"].month, m["date"].day, m["trade_time__hour"], m["trade_time__minute"], tzinfo=NPT),
         m["hi"], m["lo"], m["board_hi"], m["board_lo"])
        for m in minutes
    ]
    candles = IntradayCandle.objects.all()
    if start:
        candles = candles.filter(bucket_start__date__gte=start)
    if end:
        candles = candles.filter(bucket_start__date__lte=end)
    stored = defaultdict(set)
    for company_id, interval, bucket in candles.values_list("company_id", "interval", "bucket_start"):
        stored[interval].add((company_id, bucket.astimezone(NPT)))

    result = {}
    for interval, size in INTERVAL_MINUTES.items():
        buckets = {}
        for company_id, day, moment, hi, lo, board_hi, board_lo in minutes:
            b = buckets.setdefault((company_id, bucket_start_for(moment, size, day)), [hi, lo, board_hi, board_lo, False])
            b[0], b[1] = max(b[0], hi), min(b[1], lo)
            if board_hi is not None:
                b[2] = board_hi if b[2] is None else max(b[2], board_hi)
                b[3] = board_lo if b[3] is None else min(b[3], board_lo)
            b[4] = b[4] or moment.time() < SESSION_OPEN
        kept = [b for key, b in buckets.items() if key in stored[interval]]
        result[interval] = {
            "stored": len(stored[interval]),
            "odd_lot_high_low_changes": sum(1 for b in kept if (b[2], b[3]) != (b[0], b[1])),
            "contain_pre_open": sum(1 for b in kept if b[4]),
        }
    return result
