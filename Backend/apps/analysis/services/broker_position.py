"""
Broker position: one broker's running net (bought - sold) in one stock over a range.

Ranges count floorsheet SESSIONS held for the stock (like broker_accumulation), so
holidays and missing crawl days never shorten a range:

    1D, 2D            intraday: one point per 1-minute (1D) / 5-minute (2D) bucket, from
                      each trade's own time; price = the stored intraday candle close
    1W ... 1Y         daily: one point per session; price = the crawled daily close

The running total starts at 0 at the start of the range, so it is the broker's net
buying WITHIN the range, not its holdings (the floorsheet can't show those).
Days or buckets the broker didn't trade are kept with zero flow so the line stays flat.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from django.db.models import Count, F, Q, Sum

from apps.floorsheet.models import IntradayCandle
from apps.floorsheet.services.intraday_candles import NPT, bucket_start_for
from apps.market_data.models import DailyPrice

from .broker_accumulation import exclude_self_trades_default
from .brokers import _base_queryset, _transaction_value

RANGE_SESSIONS = {"1D": 1, "2D": 2, "1W": 5, "2W": 10, "1M": 21, "3M": 63, "6M": 126, "1Y": 250}
DEFAULT_RANGE = "1M"
INTRADAY_MINUTES = {"1D": 1, "2D": 5}
TOP_BROKERS = 10
ZERO = Decimal(0)


def range_sessions(company, range_key):
    """The newest ``RANGE_SESSIONS[range_key]`` floorsheet dates held for the stock, oldest first."""
    dates = (
        _base_queryset(company=company).order_by("-date").values_list("date", flat=True).distinct()
        [:RANGE_SESSIONS[range_key]]
    )
    return sorted(dates)


def _avg(value, quantity):
    return (value / quantity).quantize(Decimal("0.01")) if quantity else None


def _scoped(company, sessions, exclude_self):
    queryset = _base_queryset(company=company, start_date=sessions[0], end_date=sessions[-1])
    if exclude_self:
        queryset = queryset.exclude(_buyer_broker_clean=F("_seller_broker_clean"))
    return queryset


def top_brokers(queryset, n=TOP_BROKERS):
    """The stock's most active brokers in the range (gross shares), with their net, for quick picking."""
    gross = defaultdict(lambda: {"bought": 0, "sold": 0})
    for side, field in (("bought", "_buyer_broker_clean"), ("sold", "_seller_broker_clean")):
        for row in queryset.order_by().values(field).annotate(quantity_sum=Sum("quantity")):
            gross[row[field]][side] += row["quantity_sum"] or 0
    ranked = sorted(gross.items(), key=lambda item: item[1]["bought"] + item[1]["sold"], reverse=True)[:n]
    return [{"broker": code, **sides, "net": sides["bought"] - sides["sold"]} for code, sides in ranked if code]


def _daily_points(company, broker, sessions, queryset):
    sides = defaultdict(lambda: {"bought": 0, "sold": 0, "buy_value": ZERO, "sell_value": ZERO, "trades": 0})
    for side, value_key, field in (("bought", "buy_value", "_buyer_broker_clean"), ("sold", "sell_value", "_seller_broker_clean")):
        rows = (
            queryset.filter(**{field: broker}).order_by().values("date")
            # Annotation names must not shadow the model's quantity / rate columns.
            .annotate(quantity_sum=Sum("quantity"), value_sum=Sum(_transaction_value()), trade_count=Count("id"))
        )
        for row in rows:
            day = sides[row["date"]]
            day[side] += row["quantity_sum"] or 0
            day[value_key] += row["value_sum"] or ZERO
            day["trades"] += row["trade_count"]
    closes = dict(
        DailyPrice.objects.filter(company=company, source="crawled", date__gte=sessions[0], date__lte=sessions[-1])
        .values_list("date", "close")
    )
    return [{"time": day, "date": day, "price": closes.get(day), **sides[day]} for day in sessions], sides


def _intraday_points(company, broker, sessions, queryset, minutes):
    interval = f"{minutes}m"
    sides = defaultdict(lambda: {"bought": 0, "sold": 0, "buy_value": ZERO, "sell_value": ZERO, "trades": 0})
    untimed = 0
    trades = queryset.filter(Q(_buyer_broker_clean=broker) | Q(_seller_broker_clean=broker)).values_list(
        "date", "trade_time", "quantity", "rate", "_buyer_broker_clean", "_seller_broker_clean",
    )
    for day, moment, quantity, rate, buyer, seller in trades:
        if moment is None:
            untimed += 1
            continue
        bucket = sides[bucket_start_for(moment, minutes, day)]
        value = quantity * rate
        if buyer == broker:
            bucket["bought"] += quantity
            bucket["buy_value"] += value
        if seller == broker:
            bucket["sold"] += quantity
            bucket["sell_value"] += value
        bucket["trades"] += 1

    candles = dict(
        IntradayCandle.objects.filter(company=company, interval=interval)
        .filter(bucket_start__date__gte=sessions[0], bucket_start__date__lte=sessions[-1])
        .values_list("bucket_start", "close")
    )
    # The price line and the broker's buckets share bucket starts (both from bucket_start_for).
    times = sorted(set(candles) | set(sides))
    points = [
        {"time": t, "date": t.astimezone(NPT).date(), "price": candles.get(t), **sides[t]}
        for t in times if t.astimezone(NPT).date() in set(sessions)
    ]
    return points, sides, untimed


def build_broker_position(company, broker, range_key=DEFAULT_RANGE, exclude_self=None):
    if exclude_self is None:
        exclude_self = exclude_self_trades_default()
    sessions = range_sessions(company, range_key)
    payload = {
        "symbol": company.symbol,
        "broker": broker,
        "range": range_key,
        "mode": "intraday" if range_key in INTRADAY_MINUTES else "daily",
        "bucket_minutes": INTRADAY_MINUTES.get(range_key),
        "exclude_self": exclude_self,
        "sessions": len(sessions),
        "start_date": sessions[0] if sessions else None,
        "end_date": sessions[-1] if sessions else None,
        "points": [],
        "totals": None,
        "top_brokers": [],
        "warnings": [],
    }
    if not sessions:
        return payload

    queryset = _scoped(company, sessions, exclude_self)
    payload["top_brokers"] = top_brokers(queryset)
    if not broker:
        # No broker picked yet: open on the stock's most active broker in the range.
        if not payload["top_brokers"]:
            return payload
        broker = payload["broker"] = payload["top_brokers"][0]["broker"]
    if range_key in INTRADAY_MINUTES:
        points, sides, untimed = _intraday_points(company, broker, sessions, queryset, INTRADAY_MINUTES[range_key])
        if untimed:
            payload["warnings"].append(
                f"{untimed} of this broker's trades have no trade time (ShareSansar-only day) and are not in the intraday chart."
            )
    else:
        points, sides = _daily_points(company, broker, sessions, queryset)

    running = 0
    for point in points:
        point["net"] = point["bought"] - point["sold"]
        running += point["net"]
        point["position"] = running

    bought = sum(s["bought"] for s in sides.values())
    sold = sum(s["sold"] for s in sides.values())
    buy_value = sum((s["buy_value"] for s in sides.values()), ZERO)
    sell_value = sum((s["sell_value"] for s in sides.values()), ZERO)
    volume = queryset.aggregate(quantity_sum=Sum("quantity"))["quantity_sum"] or 0
    last_price = next((p["price"] for p in reversed(points) if p["price"] is not None), None)
    self_trades = queryset.filter(_buyer_broker_clean=broker, _seller_broker_clean=broker).count() if not exclude_self else 0
    active = {p["date"] for p in points if p["bought"] or p["sold"]}

    payload["points"] = points
    payload["totals"] = {
        "bought": bought,
        "sold": sold,
        "net": bought - sold,
        "buy_value": buy_value,
        "sell_value": sell_value,
        "avg_buy_price": _avg(buy_value, bought),
        "avg_sell_price": _avg(sell_value, sold),
        "last_price": last_price,
        "trades": sum(s["trades"] for s in sides.values()),
        "active_sessions": len(active),
        # Share of all shares traded in the stock that this broker was on either side of.
        "share_of_volume_pct": (Decimal(bought + sold) * 50 / volume).quantize(Decimal("0.01")) if volume else None,
        "stock_volume": volume,
        "self_trades": self_trades,
    }
    return payload


def to_json(value):
    """Decimals as rounded numbers (the page charts them), dates / times as ISO strings."""
    from datetime import date

    if isinstance(value, Decimal):
        return round(float(value), 4)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: to_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_json(item) for item in value]
    return value


MAX_STOCKS = 8


def session_buckets(sessions, minutes):
    """Every bucket start of the sessions' continuous trading (11:00-15:00), in order."""
    from datetime import timedelta

    from apps.floorsheet.services.intraday_candles import session_bounds

    buckets = []
    for day in sessions:
        start, close = session_bounds(day)
        moment = start
        while moment < close:
            buckets.append(moment)
            moment += timedelta(minutes=minutes)
    return buckets


def build_broker_activity(broker, companies, range_key=DEFAULT_RANGE, exclude_self=None):
    """
    One broker's buy and sell quantity in several stocks on a shared time axis, for the
    Acc / Dist chart.  ``times`` is every session (1W ... 1Y) or every 1- / 5-minute bucket
    of the sessions (1D / 2D); each stock's ``bought`` / ``sold`` has one value per time.
    Sessions are the newest dates any of the stocks has a floorsheet for.  Without
    ``broker``, opens on the most active broker across the stocks.
    """
    if exclude_self is None:
        exclude_self = exclude_self_trades_default()
    ids = [company.pk for company in companies]
    dates = (
        _base_queryset(company_ids=ids).order_by("-date").values_list("date", flat=True).distinct()
        [:RANGE_SESSIONS[range_key]]
    )
    sessions = sorted(dates)
    minutes = INTRADAY_MINUTES.get(range_key)
    payload = {
        "broker": broker,
        "range": range_key,
        "mode": "intraday" if minutes else "daily",
        "bucket_minutes": minutes,
        "exclude_self": exclude_self,
        "sessions": len(sessions),
        "start_date": sessions[0] if sessions else None,
        "end_date": sessions[-1] if sessions else None,
        "times": [],
        "series": [],
        "top_brokers": [],
        "warnings": [],
    }
    if not sessions:
        return payload

    queryset = _base_queryset(company_ids=ids, start_date=sessions[0], end_date=sessions[-1])
    if exclude_self:
        queryset = queryset.exclude(_buyer_broker_clean=F("_seller_broker_clean"))
    payload["top_brokers"] = top_brokers(queryset)
    if not broker:
        if not payload["top_brokers"]:
            return payload
        broker = payload["broker"] = payload["top_brokers"][0]["broker"]

    times = session_buckets(sessions, minutes) if minutes else sessions
    index = {t: i for i, t in enumerate(times)}
    flows = {
        pk: {"bought": [0] * len(times), "sold": [0] * len(times), "buy_value": ZERO, "sell_value": ZERO, "trades": 0}
        for pk in ids
    }

    if minutes:
        untimed = 0
        trades = queryset.filter(Q(_buyer_broker_clean=broker) | Q(_seller_broker_clean=broker)).values_list(
            "company_id", "date", "trade_time", "quantity", "rate", "_buyer_broker_clean", "_seller_broker_clean",
        )
        for pk, day, moment, quantity, rate, buyer, seller in trades:
            if moment is None:
                untimed += 1
                continue
            slot = index[bucket_start_for(moment, minutes, day)]
            flow = flows[pk]
            if buyer == broker:
                flow["bought"][slot] += quantity
                flow["buy_value"] += quantity * rate
            if seller == broker:
                flow["sold"][slot] += quantity
                flow["sell_value"] += quantity * rate
            flow["trades"] += 1
        if untimed:
            payload["warnings"].append(
                f"{untimed} trades of broker {broker} have no trade time (ShareSansar-only day) and are not in the intraday chart."
            )
    else:
        sides = (("bought", "buy_value", "_buyer_broker_clean"), ("sold", "sell_value", "_seller_broker_clean"))
        for side, value_key, field in sides:
            rows = (
                queryset.filter(**{field: broker}).order_by().values("company_id", "date")
                .annotate(quantity_sum=Sum("quantity"), value_sum=Sum(_transaction_value()), trade_count=Count("id"))
            )
            for row in rows:
                flow = flows[row["company_id"]]
                flow[side][index[row["date"]]] += row["quantity_sum"] or 0
                flow[value_key] += row["value_sum"] or ZERO
                flow["trades"] += row["trade_count"]

    payload["times"] = times
    for company in companies:
        flow = flows[company.pk]
        bought, sold = sum(flow["bought"]), sum(flow["sold"])
        payload["series"].append({
            "symbol": company.symbol,
            "name": company.name,
            "bought": flow["bought"],
            "sold": flow["sold"],
            "totals": {
                "bought": bought,
                "sold": sold,
                "net": bought - sold,
                "buy_value": flow["buy_value"],
                "sell_value": flow["sell_value"],
                "avg_buy_price": _avg(flow["buy_value"], bought),
                "avg_sell_price": _avg(flow["sell_value"], sold),
                "trades": flow["trades"],
            },
        })
    return payload
