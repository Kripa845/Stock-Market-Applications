"""
Market Overview card: header quote, session stats and chart series.

Stats cover the tracked companies only ("Your Companies").  They are counted
from the buckets services.movers assigns, so the rules are the project's single
definition: ShareSansar's adjusted % when stored, possible corporate actions
excluded, circuit at movers.CIRCUIT_THRESHOLD_PCT.

The header and the chart follow the instrument picked in the card: the NEPSE
index or one tracked company.
"""

from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.utils import timezone

from apps.market_data.models import DailyPrice, IntradayCandle
from apps.market_data.services import movers
from apps.market_data.services.intraday_candles import NPT, SESSION_CLOSE, latest_candle_date
from apps.market_data.services.market_stats import PRICE_SOURCE, tracked_companies
from apps.market_data.services.trading_days import is_market_open
from apps.market_indices.models import IndexDaily, IndexIntradayPoint

INDEX_SYMBOL = "NEPSE"
STATS_LABEL = "Your Companies"
INTRADAY_INTERVAL = "5m"

# Calendar months back from the latest session (same idea as the frontend's chartRanges).
RANGE_MONTHS = {"1W": None, "1M": 1, "3M": 3, "6M": 6, "1Y": 12, "5Y": 60}
RANGES = ("1D", "1W", "1M", "3M", "6M", "1Y", "5Y", "ALL")


# ----------------------------------------------------------------------
# Formatting
# ----------------------------------------------------------------------

def nepali_grouping(value, decimals=2):
    """4465246360.73 -> '4,46,52,46,360.73' (last three digits, then pairs). None -> None."""
    if value is None:
        return None
    number = Decimal(str(value)).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
    sign = "-" if number < 0 else ""
    whole, _, fraction = f"{abs(number):.{decimals}f}".partition(".")
    head, tail = whole[:-3], whole[-3:]
    pairs = []
    while len(head) > 2:
        pairs.insert(0, head[-2:])
        head = head[:-2]
    grouped = ",".join(([head] if head else []) + pairs + [tail])
    return f"{sign}{grouped}" + (f".{fraction}" if decimals else "")


# ----------------------------------------------------------------------
# Stats (pure)
# ----------------------------------------------------------------------

def compute_market_stats(rows):
    """
    Session stats from movers rows (dicts with bucket, change_pct, volume, turnover, transactions).

    Only companies that traded count as scrips traded; advanced / declined / unchanged
    are the movers buckets, so rows without a usable previous close or with a possible
    corporate action are traded but not ranked.  Pure: no database access.
    """
    threshold = movers.CIRCUIT_THRESHOLD_PCT
    traded = [row for row in rows if row.get("bucket") not in movers.NOT_RANKABLE_TODAY]

    def total(field):
        values = [row[field] for row in traded if row.get(field) is not None]
        return sum(values) if values else None

    def pct(row):
        return None if row.get("change_pct") is None else Decimal(str(row["change_pct"]))

    gainers = [row for row in traded if row["bucket"] == "gainer"]
    losers = [row for row in traded if row["bucket"] == "loser"]
    turnover = total("turnover")
    return {
        "advanced": len(gainers),
        "declined": len(losers),
        "unchanged": sum(1 for row in traded if row["bucket"] == "unchanged"),
        "positive_circuit": sum(1 for row in gainers if pct(row) is not None and pct(row) >= threshold),
        "negative_circuit": sum(1 for row in losers if pct(row) is not None and pct(row) <= -threshold),
        "not_ranked": sum(1 for row in traded if row["bucket"] not in movers.RANKED),
        "total_turnover": turnover,
        "total_turnover_display": nepali_grouping(turnover),
        "total_traded_shares": total("volume"),
        "total_transactions": total("transactions"),
        "transactions_reported": sum(1 for row in traded if row.get("transactions") is not None),
        "total_scrips_traded": len(traded),
        "tracked_count": len(rows),
        "circuit_threshold_pct": threshold,
    }


# ----------------------------------------------------------------------
# Instruments and the header quote
# ----------------------------------------------------------------------

def instruments(company_ids=None):
    """What the card's dropdown offers: the NEPSE index, then the tracked companies."""
    companies = tracked_companies(company_ids).order_by("symbol").values("symbol", "name")
    return [{"symbol": INDEX_SYMBOL, "name": "NEPSE Index", "kind": "index"}] + [
        {"symbol": c["symbol"], "name": c["name"], "kind": "company"} for c in companies
    ]


def _session_close(day):
    return datetime.combine(day, SESSION_CLOSE, tzinfo=NPT) if day else None


def _index_rows():
    return IndexDaily.objects.filter(index__code=INDEX_SYMBOL, source="crawled")


def index_quote():
    """NEPSE index value now: today's live snapshot if newer than the latest stored session."""
    latest_two = list(_index_rows().order_by("-date")[:2])
    point = (
        IndexIntradayPoint.objects.filter(index__code=INDEX_SYMBOL).order_by("-recorded_at").first()
    )
    session = latest_two[0] if latest_two else None
    if point and (session is None or point.recorded_at.astimezone(NPT).date() > session.date):
        return {
            "symbol": INDEX_SYMBOL, "name": "NEPSE Index", "kind": "index", "live": True,
            "value": point.value, "change": point.change, "change_pct": point.change_pct,
            "as_of": point.recorded_at,
        }
    if session is None:
        return {"symbol": INDEX_SYMBOL, "name": "NEPSE Index", "kind": "index", "live": False,
                "value": None, "change": None, "change_pct": None, "as_of": None}
    previous = latest_two[1] if len(latest_two) > 1 else None
    change = session.close - previous.close if previous else None
    change_pct = session.source_change_pct
    if change_pct is None and previous and previous.close:
        change_pct = change * 100 / previous.close
    return {
        "symbol": INDEX_SYMBOL, "name": "NEPSE Index", "kind": "index", "live": False,
        "value": session.close, "change": change, "change_pct": change_pct,
        "as_of": _session_close(session.date),
    }


def company_quote(company, as_of, row):
    """Live NEPSE LTP when it is from a session after the stored one, else the movers row."""
    live_day = company.prices_updated_at.astimezone(NPT).date() if company.prices_updated_at else None
    if company.ltp is not None and company.previous_close and live_day and (as_of is None or live_day > as_of):
        change = company.ltp - company.previous_close
        return {
            "symbol": company.symbol, "name": company.name, "kind": "company", "live": True,
            "value": company.ltp, "change": change, "change_pct": change * 100 / company.previous_close,
            "as_of": company.prices_updated_at,
        }
    row = row or {}
    return {
        "symbol": company.symbol, "name": company.name, "kind": "company", "live": False,
        "value": row.get("close"), "change": row.get("change"), "change_pct": row.get("change_pct"),
        "as_of": _session_close(as_of),
    }


def market_overview(symbol=INDEX_SYMBOL, company_ids=None, company=None, now=None):
    """Header quote for ``symbol`` (NEPSE or ``company``) plus the tracked-company session stats."""
    as_of, rows_by_company = movers.company_rows(company_ids)
    rows = list(rows_by_company.values())
    if company is not None:
        quote = company_quote(company, as_of, rows_by_company.get(company.id))
    else:
        quote = index_quote()
    open_now = is_market_open(now or timezone.now())
    return {
        "instrument": quote,
        "status": "OPEN" if open_now else "CLOSE",
        "timestamp": quote["as_of"],
        "stats_label": STATS_LABEL,
        "trade_date": as_of,
        "stats": compute_market_stats(rows) if as_of else None,
        "instruments": instruments(company_ids),
        "reason": None if as_of else "no completed trading day in DailyPrice (source=crawled)",
    }


# ----------------------------------------------------------------------
# Chart series
# ----------------------------------------------------------------------

def _months_before(day, months):
    year, month = divmod(day.year * 12 + day.month - 1 - months, 12)
    month += 1
    for candidate in (31, 30, 29, 28):
        try:
            return date(year, month, min(day.day, candidate))
        except ValueError:
            continue
    raise ValueError(day)


def range_start(latest, earliest, range_id):
    """First date (inclusive) of a daily range, or None when the data does not reach that far."""
    if range_id == "ALL":
        return earliest
    months = RANGE_MONTHS[range_id]
    start = latest - timedelta(days=7) if months is None else _months_before(latest, months)
    return start if earliest <= start else None


def _intraday_points(company):
    if company is None:
        points = IndexIntradayPoint.objects.filter(index__code=INDEX_SYMBOL)
        last = points.order_by("-recorded_at").first()
        if last is None:
            return None, []
        day = last.recorded_at.astimezone(NPT).date()
        start = datetime.combine(day, datetime.min.time(), tzinfo=NPT)
        rows = points.filter(recorded_at__gte=start, recorded_at__lt=start + timedelta(days=1)).order_by("recorded_at")
        return day, [{"t": p.recorded_at, "open": None, "high": None, "low": None, "close": p.value, "volume": None}
                     for p in rows]
    day = latest_candle_date(company)
    if day is None:
        return None, []
    start = datetime.combine(day, datetime.min.time(), tzinfo=NPT)
    candles = IntradayCandle.objects.filter(
        company=company, interval=INTRADAY_INTERVAL,
        bucket_start__gte=start, bucket_start__lt=start + timedelta(days=1),
    ).order_by("bucket_start")
    return day, [{"t": c.bucket_start, "open": c.open, "high": c.high, "low": c.low, "close": c.close,
                  "volume": c.volume} for c in candles]


def chart_series(range_id="1D", company=None):
    """Points for the card's chart; ``available_ranges`` lists the ranges the stored data covers."""
    symbol = company.symbol if company else INDEX_SYMBOL
    if company is None:
        daily = _index_rows()
    else:
        daily = DailyPrice.objects.filter(company=company, source=PRICE_SOURCE)
    dates = daily.order_by("date").values_list("date", flat=True)
    earliest, latest = dates.first(), dates.last()

    intraday_day, intraday = _intraday_points(company)    # one session: cheap
    available = ["1D"] if intraday else []
    if latest is not None:
        available += [r for r in RANGES[1:] if range_start(latest, earliest, r) is not None]

    result = {"symbol": symbol, "range": range_id, "available_ranges": available, "points": []}
    if range_id == "1D":
        result.update(interval="intraday", date=intraday_day, points=intraday)
        if not intraday:
            result["reason"] = (
                "No intraday NEPSE index values stored yet: they are saved during market hours."
                if company is None else "No intraday candles stored for this company yet."
            )
        return result

    start = range_start(latest, earliest, range_id) if latest else None
    if start is None:
        result.update(interval="daily", reason="The stored history does not reach back this far.")
        return result
    rows = daily.filter(date__gte=start).order_by("date").values("date", "open", "high", "low", "close", "volume")
    result.update(interval="daily", points=[
        {"t": r["date"], "open": r["open"], "high": r["high"], "low": r["low"], "close": r["close"], "volume": r["volume"]}
        for r in rows
    ])
    return result
