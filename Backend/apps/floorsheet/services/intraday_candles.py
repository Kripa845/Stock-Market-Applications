

from collections import defaultdict
from datetime import datetime, time, timedelta
from datetime import timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Max, Min, Sum, Window
from django.db.models.functions import Coalesce, RowNumber, TruncMinute

from apps.floorsheet.models import FloorsheetTransaction, IntradayCandle

NPT = ZoneInfo("Asia/Kathmandu")

# NEPSE continuous session, Asia/Kathmandu.  Every interval below divides it evenly.
SESSION_OPEN = time(11, 0)
SESSION_CLOSE = time(15, 0)

INTERVAL_MINUTES = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60}
INTERVALS = tuple(INTERVAL_MINUTES)

CANDLE_FIELDS = ["open", "high", "low", "close", "volume", "turnover", "trade_count"]


def session_bounds(day):
    """(open, close) of ``day``'s session as aware Asia/Kathmandu datetimes."""
    return (
        datetime.combine(day, SESSION_OPEN, tzinfo=NPT),
        datetime.combine(day, SESSION_CLOSE, tzinfo=NPT),
    )


def bucket_start_for(moment, minutes, day):
    """Start of the ``minutes``-wide session bucket holding ``moment``, clamped to the session."""
    session_open, session_close = session_bounds(day)
    size = timedelta(minutes=minutes)
    local = max(moment.astimezone(NPT), session_open)
    start = session_open + ((local - session_open) // size) * size
    return min(start, session_close - size)


def minute_rows(day, company_ids=None):
    """
    One dict per (company, minute) with trades on ``day``, ordered by company then minute.

    Minutes are truncated in UTC; Nepal's +05:45 offset is a whole number of
    minutes, so the buckets are the same as Nepal-time minutes.
    """
    trades = FloorsheetTransaction.objects.filter(date=day, trade_time__isnull=False)
    if company_ids is not None:
        trades = trades.filter(company_id__in=company_ids)

    minute = TruncMinute("trade_time", tzinfo=dt_timezone.utc)
    partition = [F("company_id"), minute]
    trade_turnover = Coalesce(
        "amount",
        ExpressionWrapper(F("rate") * F("quantity"), output_field=DecimalField(max_digits=20, decimal_places=4)),
    )
    ranked = trades.annotate(
        minute=minute,
        first_rank=Window(
            RowNumber(), partition_by=partition,
            order_by=[F("trade_time").asc(), F("transaction_id").asc(), F("pk").asc()],
        ),
        last_rank=Window(
            RowNumber(), partition_by=partition,
            order_by=[F("trade_time").desc(), F("transaction_id").desc(), F("pk").desc()],
        ),
        bucket_high=Window(Max("rate"), partition_by=partition),
        bucket_low=Window(Min("rate"), partition_by=partition),
        bucket_volume=Window(Sum("quantity"), partition_by=partition),
        bucket_turnover=Window(Sum(trade_turnover), partition_by=partition),
        bucket_trades=Window(Count("pk"), partition_by=partition),
    )

    closes = {
        (row["company_id"], row["minute"]): row["rate"]
        for row in ranked.filter(last_rank=1).values("company_id", "minute", "rate")
    }
    rows = ranked.filter(first_rank=1).values(
        "company_id", "minute", "rate",
        "bucket_high", "bucket_low", "bucket_volume", "bucket_turnover", "bucket_trades",
    )
    result = [
        {
            "company_id": row["company_id"],
            "minute": row["minute"],
            "open": row["rate"],
            "high": row["bucket_high"],
            "low": row["bucket_low"],
            "close": closes[(row["company_id"], row["minute"])],
            "volume": row["bucket_volume"],
            "turnover": row["bucket_turnover"],
            "trade_count": row["bucket_trades"],
        }
        for row in rows
    ]
    return sorted(result, key=lambda r: (r["company_id"], r["minute"]))


def roll_up(rows, interval, day):
    """Merge ordered 1-minute rows into ``interval`` candles (one dict per company-bucket)."""
    minutes = INTERVAL_MINUTES[interval]
    candles = {}
    for row in rows:
        key = (row["company_id"], bucket_start_for(row["minute"], minutes, day))
        candle = candles.get(key)
        if candle is None:
            candles[key] = {**row, "bucket_start": key[1]}
            continue
        candle["high"] = max(candle["high"], row["high"])
        candle["low"] = min(candle["low"], row["low"])
        candle["close"] = row["close"]
        candle["volume"] += row["volume"]
        candle["turnover"] += row["turnover"]
        candle["trade_count"] += row["trade_count"]
    return list(candles.values())


def rebuild_day(day, company_ids=None, intervals=INTERVALS):
    """
    Recompute ``day``'s candles for ``company_ids`` (default: every company with
    timestamped trades or stored candles that day).  Upserts current buckets and
    deletes buckets that no longer have trades.  Returns the number of candles written.
    """
    day_start = datetime.combine(day, time.min, tzinfo=NPT)
    day_end = day_start + timedelta(days=1)
    rows = minute_rows(day, company_ids)

    if company_ids is None:
        company_ids = {row["company_id"] for row in rows} | set(
            IntradayCandle.objects
            .filter(bucket_start__gte=day_start, bucket_start__lt=day_end)
            .values_list("company_id", flat=True)
        )

    objs = []
    keep = defaultdict(set)
    for interval in intervals:
        for candle in roll_up(rows, interval, day):
            keep[(candle["company_id"], interval)].add(candle["bucket_start"])
            objs.append(IntradayCandle(
                company_id=candle["company_id"],
                interval=interval,
                bucket_start=candle["bucket_start"],
                **{field: candle[field] for field in CANDLE_FIELDS},
            ))

    with transaction.atomic():
        for company_id in company_ids:
            for interval in intervals:
                (
                    IntradayCandle.objects
                    .filter(company_id=company_id, interval=interval,
                            bucket_start__gte=day_start, bucket_start__lt=day_end)
                    .exclude(bucket_start__in=keep[(company_id, interval)])
                    .delete()
                )
        if objs:
            IntradayCandle.objects.bulk_create(
                objs,
                batch_size=2000,
                update_conflicts=True,
                unique_fields=["company", "interval", "bucket_start"],
                update_fields=CANDLE_FIELDS + ["updated_at"],
            )
    return len(objs)


def rebuild_range(start, end, company_ids=None, intervals=INTERVALS):
    """Rebuild every day in [start, end] that has timestamped trades or stored candles."""
    trades = FloorsheetTransaction.objects.filter(
        date__gte=start, date__lte=end, trade_time__isnull=False,
    )
    candles = IntradayCandle.objects.filter(
        bucket_start__gte=datetime.combine(start, time.min, tzinfo=NPT),
        bucket_start__lt=datetime.combine(end + timedelta(days=1), time.min, tzinfo=NPT),
    )
    if company_ids is not None:
        trades = trades.filter(company_id__in=company_ids)
        candles = candles.filter(company_id__in=company_ids)
    days = set(trades.values_list("date", flat=True).distinct())
    days |= {moment.astimezone(NPT).date() for moment in candles.values_list("bucket_start", flat=True).distinct()}

    written = {}
    for day in sorted(days):
        written[day.isoformat()] = rebuild_day(day, company_ids, intervals)
    return written


def latest_candle_date(company):
    """Asia/Kathmandu date of the company's newest stored candle, or None."""
    latest = (
        IntradayCandle.objects
        .filter(company=company)
        .order_by("-bucket_start")
        .values_list("bucket_start", flat=True)
        .first()
    )
    return latest.astimezone(NPT).date() if latest else None
