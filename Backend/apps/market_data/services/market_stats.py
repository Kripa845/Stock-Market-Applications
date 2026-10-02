"""
Statistics for the tracked-companies dashboard.

SCOPE: only the active, tracked companies (``Company.tracking.is_tracked``)
and only crawled prices (``DailyPrice.source == "crawled"``).  Nothing here
describes the whole NEPSE market; callers must label results
"Tracked companies".

Definitions (all computed in SQL through annotations / aggregates):

  change      = ltp - prev_close
  change_pct  = (ltp - prev_close) * 100 / prev_close
                NULL when prev_close is NULL or 0 (or ltp is NULL); such rows
                are counted as ``no_prev_close``, never as unchanged.
  circuit     = abs(change_pct) >= CIRCUIT_THRESHOLD_PCT (9.9).  A tolerance,
                not an exact 10%, because the exchange rounds the circuit
                price to the tick size (e.g. -10.19% is a lower circuit).
  trade_date  = defaults to the latest date with tracked crawled prices.

Python is used only to arrange already-aggregated rows into the response
(sparkline grouping, merging the buy-side and sell-side broker tables);
no per-trade or per-price arithmetic happens in Python loops.
"""

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db.models import (
    Avg,
    Case,
    Count,
    DecimalField,
    Exists,
    ExpressionWrapper,
    F,
    Max,
    Min,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
    When,
    Window,
)
from django.db.models.functions import RowNumber, Trim

from apps.companies.models import Company
from apps.market_data.models import Broker, DailyPrice, DividendAnnouncement
from apps.market_data.services.price_fields import real_floorsheet
from apps.market_intelligence.models import ProxyIndexSnapshot


PRICE_SOURCE = "crawled"
CIRCUIT_THRESHOLD_PCT = Decimal("9.9")
SPARKLINE_SESSIONS = 7
BROKER_WINDOWS = (5, 20)
CONCENTRATION_TOP_N = 5

CORPORATE_ACTION_NOTE = (
    "prev_close is the previous stored close and is NOT adjusted for bonus, "
    "right or cash-dividend book closures. On the first session after a book "
    "closure the change can reflect the exchange's price adjustment rather "
    "than trading. Rows where a recorded DividendAnnouncement book closure "
    "falls after the previous session and on or before trade_date are marked "
    "book_closure_in_window=true."
)

UNITS = {
    "price": "NPR",
    "change": "NPR",
    "change_pct": "percent",
    "turnover": "NPR",
    "volume": "shares",
    "transactions": "trades",
}

PCT_FIELD = DecimalField(max_digits=24, decimal_places=6)
MONEY_FIELD = DecimalField(max_digits=30, decimal_places=4)


# ----------------------------------------------------------------------
# Scope helpers
# ----------------------------------------------------------------------

def tracked_companies(company_ids=None):
    """Active tracked companies, optionally narrowed to ``company_ids`` (None = no narrowing)."""
    companies = Company.objects.filter(is_active=True, tracking__is_tracked=True)
    if company_ids is not None:
        companies = companies.filter(id__in=company_ids)
    return companies


def tracked_prices(company_ids=None):
    return DailyPrice.objects.filter(
        source=PRICE_SOURCE,
        company__in=tracked_companies(company_ids),
    )


def latest_trade_date(company_ids=None):
    return tracked_prices(company_ids).aggregate(day=Max("date"))["day"]


def previous_trade_date(trade_date, company_ids=None):
    return tracked_prices(company_ids).filter(date__lt=trade_date).aggregate(day=Max("date"))["day"]


def with_change(prices):
    """Annotate ``change`` and ``change_pct`` (NULL without a usable prev_close)."""
    has_reference = Q(prev_close__gt=0, ltp__isnull=False)
    return prices.annotate(
        change=Case(
            When(has_reference, then=ExpressionWrapper(F("ltp") - F("prev_close"), output_field=PCT_FIELD)),
            default=Value(None),
            output_field=PCT_FIELD,
        ),
        change_pct=Case(
            When(
                has_reference,
                then=ExpressionWrapper(
                    (F("ltp") - F("prev_close")) * Value(100) / F("prev_close"),
                    output_field=PCT_FIELD,
                ),
            ),
            default=Value(None),
            output_field=PCT_FIELD,
        ),
    )


PRICE_ROW_FIELDS = (
    "company_id", "symbol", "name", "sector", "date",
    "ltp", "prev_close", "change", "change_pct",
    "open", "high", "low", "close", "volume", "turnover", "transactions",
)


def _price_rows(trade_date, company_ids):
    return with_change(tracked_prices(company_ids).filter(date=trade_date)).annotate(
        symbol=F("company__symbol"),
        name=F("company__name"),
        sector=F("company__sector"),
    )


# ----------------------------------------------------------------------
# Movers / rankings
# ----------------------------------------------------------------------

def ranked_by_change(trade_date=None, company_ids=None):
    """Every tracked company on ``trade_date`` by change_pct (NULLs last), with a 7-close sparkline."""
    trade_date = trade_date or latest_trade_date(company_ids)
    if trade_date is None:
        return {"trade_date": None, "rows": []}

    previous_date = previous_trade_date(trade_date, company_ids)
    if previous_date is not None:
        book_closure = Exists(
            DividendAnnouncement.objects.filter(
                company=OuterRef("company"),
                book_closure_date__gt=previous_date,
                book_closure_date__lte=trade_date,
            )
        )
    else:
        book_closure = Value(False)

    rows = list(
        _price_rows(trade_date, company_ids)
        .annotate(book_closure_in_window=book_closure)
        .order_by(F("change_pct").desc(nulls_last=True), "company__symbol")
        .values(*PRICE_ROW_FIELDS, "book_closure_in_window")
    )

    recent_closes = (
        tracked_prices(company_ids)
        .filter(date__lte=trade_date, company_id__in=[row["company_id"] for row in rows])
        .annotate(position=Window(RowNumber(), partition_by=[F("company_id")], order_by=F("date").desc()))
        .filter(position__lte=SPARKLINE_SESSIONS)
        .order_by("company_id", "date")
        .values_list("company_id", "date", "close")
    )
    sparklines = defaultdict(list)
    for company_id, day, close in recent_closes:
        sparklines[company_id].append({"date": day, "close": close})
    for row in rows:
        row["sparkline"] = sparklines[row["company_id"]]

    return {"trade_date": trade_date, "previous_trade_date": previous_date, "rows": rows}


TOP_FIELDS = {
    "turnover": "turnover",
    "volume": "volume",
    "transactions": "transactions",
}


def top_by(metric, trade_date=None, company_ids=None, limit=10):
    """Tracked companies on ``trade_date`` by turnover / volume / transactions, descending (NULLs last)."""
    field = TOP_FIELDS[metric]
    trade_date = trade_date or latest_trade_date(company_ids)
    if trade_date is None:
        return {"trade_date": None, "metric": metric, "rows": []}
    rows = list(
        _price_rows(trade_date, company_ids)
        .order_by(F(field).desc(nulls_last=True), "company__symbol")
        .values(*PRICE_ROW_FIELDS)[:limit]
    )
    return {"trade_date": trade_date, "metric": metric, "rows": rows}


# ----------------------------------------------------------------------
# Summary
# ----------------------------------------------------------------------

def tracked_summary(trade_date=None, company_ids=None):
    """
    One ``aggregate()`` over the tracked companies' rows for ``trade_date``.

    advanced + declined + unchanged + no_prev_close == tracked_count, where
    tracked_count is the number of tracked companies with a crawled price on
    that date.  ``total_transactions`` sums only rows whose floorsheet has been
    crawled; ``transactions_reported`` says how many that is.
    """
    trade_date = trade_date or latest_trade_date(company_ids)
    if trade_date is None:
        return {"trade_date": None}

    totals = with_change(tracked_prices(company_ids).filter(date=trade_date)).aggregate(
        tracked_count=Count("id"),
        advanced=Count("id", filter=Q(change__gt=0)),
        declined=Count("id", filter=Q(change__lt=0)),
        unchanged=Count("id", filter=Q(change=0)),
        no_prev_close=Count("id", filter=Q(change__isnull=True)),
        positive_circuit=Count("id", filter=Q(change_pct__gte=CIRCUIT_THRESHOLD_PCT)),
        negative_circuit=Count("id", filter=Q(change_pct__lte=-CIRCUIT_THRESHOLD_PCT)),
        total_turnover=Sum("turnover"),
        total_traded_shares=Sum("volume"),
        total_transactions=Sum("transactions"),
        transactions_reported=Count("transactions"),
    )
    return {"trade_date": trade_date, **totals}


# ----------------------------------------------------------------------
# Brokers
# ----------------------------------------------------------------------

def _broker_window(trades):
    """
    Broker table for one window of floorsheet trades.

    turnover per broker = buy amount + sell amount, where amount = quantity * rate.
    share_pct           = (buy amount + sell amount) * 100 / (2 * company turnover)
    company turnover    = sum of quantity * rate over the same trades.
    Every trade has one buyer and one seller, so the denominator counts each
    rupee twice, exactly as the numerators do, and the shares sum to 100%.
    volume_share_pct uses quantities the same way.
    """
    trades = trades.annotate(
        buyer=Trim("buyer_broker"),
        seller=Trim("seller_broker"),
        value=ExpressionWrapper(F("quantity") * F("rate"), output_field=MONEY_FIELD),
    )
    totals = trades.aggregate(
        total_quantity=Sum("quantity"),
        total_amount=Sum("value"),
        total_trades=Count("id"),
    )
    if not totals["total_trades"]:
        return {**totals, "brokers": [], "top_buyers": [], "top_sellers": [], "concentration": None}

    buys = trades.order_by().values("buyer").annotate(quantity=Sum("quantity"), amount=Sum("value"), trades=Count("id"))
    sells = trades.order_by().values("seller").annotate(quantity=Sum("quantity"), amount=Sum("value"), trades=Count("id"))

    # Merge the two grouped tables (one row per broker each, at most ~90).
    empty = {"buy_quantity": 0, "buy_amount": Decimal("0"), "buy_trades": 0,
             "sell_quantity": 0, "sell_amount": Decimal("0"), "sell_trades": 0}
    brokers = defaultdict(lambda: dict(empty))
    for row in buys:
        brokers[row["buyer"]].update(buy_quantity=row["quantity"], buy_amount=row["amount"], buy_trades=row["trades"])
    for row in sells:
        brokers[row["seller"]].update(sell_quantity=row["quantity"], sell_amount=row["amount"], sell_trades=row["trades"])

    names = dict(Broker.objects.filter(broker_code__in=list(brokers)).values_list("broker_code", "name"))
    double_amount = 2 * totals["total_amount"]
    double_quantity = 2 * totals["total_quantity"]

    rows = []
    for code, side in brokers.items():
        turnover = side["buy_amount"] + side["sell_amount"]
        traded = side["buy_quantity"] + side["sell_quantity"]
        rows.append({
            "broker": code,
            "broker_name": names.get(code, ""),
            **side,
            "turnover": turnover,
            "net_quantity": side["buy_quantity"] - side["sell_quantity"],
            "net_amount": side["buy_amount"] - side["sell_amount"],
            "share_pct": turnover * 100 / double_amount if double_amount else None,
            "volume_share_pct": Decimal(traded) * 100 / double_quantity if double_quantity else None,
        })
    rows.sort(key=lambda row: (-row["turnover"], row["broker"]))

    by_volume = sorted(rows, key=lambda row: -(row["buy_quantity"] + row["sell_quantity"]))
    top_volume = by_volume[:CONCENTRATION_TOP_N]
    concentration = {
        "top_n": CONCENTRATION_TOP_N,
        "brokers": [row["broker"] for row in top_volume],
        "volume_share_pct": sum((row["volume_share_pct"] for row in top_volume), Decimal("0")),
    }

    return {
        **totals,
        "brokers": rows,
        "top_buyers": sorted(rows, key=lambda row: -row["buy_quantity"])[:CONCENTRATION_TOP_N],
        "top_sellers": sorted(rows, key=lambda row: -row["sell_quantity"])[:CONCENTRATION_TOP_N],
        "concentration": concentration,
    }


def broker_activity(company_id, windows=BROKER_WINDOWS, anchor_date=None):
    """
    Broker activity for one tracked company over its last N floorsheet sessions.

    A window of N means the company's latest N dates that have real floorsheet
    trades (on or before ``anchor_date``), not N calendar days; ``dates`` in
    each window lists them so a gap is visible.
    """
    trades = real_floorsheet().filter(company_id=company_id)
    if anchor_date is not None:
        trades = trades.filter(date__lte=anchor_date)
    session_dates = list(
        trades.order_by("-date").values_list("date", flat=True).distinct()[: max(windows)]
    )

    result = []
    for sessions in windows:
        dates = session_dates[:sessions]
        window = _broker_window(trades.filter(date__in=dates))
        result.append({
            "sessions": sessions,
            "sessions_available": len(dates),
            "start_date": min(dates) if dates else None,
            "end_date": max(dates) if dates else None,
            "dates": sorted(dates),
            **window,
        })
    return result


# ----------------------------------------------------------------------
# Signals
# ----------------------------------------------------------------------

def _window_average(prices, field, sessions):
    stats = prices.order_by("-date")[:sessions].aggregate(value=Avg(field), sessions=Count("id"))
    return {
        "value": stats["value"] if stats["sessions"] == sessions else None,
        "sessions": stats["sessions"],
        "required_sessions": sessions,
    }


def signals(company_id, anchor_date=None):
    """
    Price/volume signals for one tracked company at its latest session (<= anchor_date).

    Each value is NULL when there is not enough history; the session counts
    say how much was available.  The 52-week range covers only the stored
    history inside the last 365 days (``range_52w.sessions``).
    """
    prices = tracked_prices([company_id])
    if anchor_date is not None:
        prices = prices.filter(date__lte=anchor_date)
    latest = prices.order_by("-date").first()
    if latest is None:
        return None

    upto_latest = prices.filter(date__lte=latest.date)
    before_latest = prices.filter(date__lt=latest.date)

    volume_average = _window_average(before_latest, "volume", 20)
    ma5 = _window_average(upto_latest, "close", 5)
    ma20 = _window_average(upto_latest, "close", 20)
    range_52w = upto_latest.filter(date__gt=latest.date - timedelta(days=365)).aggregate(
        high=Max("high"),
        low=Min("low"),
        sessions=Count("id"),
        first_date=Min("date"),
    )

    price = latest.ltp if latest.ltp is not None else latest.close
    average_volume = volume_average["value"]

    def pct(numerator, denominator):
        return (Decimal(numerator) * 100 / Decimal(denominator)) if numerator is not None and denominator else None

    return {
        "symbol": latest.company.symbol,
        "trade_date": latest.date,
        "ltp": price,
        "volume": latest.volume,
        "volume_vs_20d_avg": {
            "average_volume": average_volume,
            "ratio": (Decimal(latest.volume) / Decimal(average_volume)) if average_volume else None,
            "sessions": volume_average["sessions"],
            "required_sessions": 20,
        },
        "moving_averages": {
            "ma5": ma5,
            "ma20": ma20,
            "ltp_vs_ma5_pct": pct(price - ma5["value"], ma5["value"]) if ma5["value"] else None,
            "ltp_vs_ma20_pct": pct(price - ma20["value"], ma20["value"]) if ma20["value"] else None,
        },
        "range_52w": {
            **range_52w,
            "distance_from_high_pct": pct(price - range_52w["high"], range_52w["high"]) if range_52w["high"] else None,
            "distance_from_low_pct": pct(price - range_52w["low"], range_52w["low"]) if range_52w["low"] else None,
        },
    }


# ----------------------------------------------------------------------
# Basket index, dividends, watchlist
# ----------------------------------------------------------------------

BASKET_LABEL = "Tracked Basket"


def basket_index(days=None):
    rows = ProxyIndexSnapshot.objects.order_by("-date").values(
        "date",
        "level",
        "daily_return_pct",
        "equal_weight_level",
        "equal_weight_return_pct",
        "eligible_company_count",
        "corporate_action_excluded_count",
        "methodology_version",
    )
    if days:
        rows = rows[:days]
    return {"label": BASKET_LABEL, "base_level": 1000, "rows": list(reversed(list(rows)))}


def dividend_rows(company_ids=None):
    return list(
        DividendAnnouncement.objects
        .filter(company__in=tracked_companies(company_ids))
        .annotate(
            symbol=F("company__symbol"),
            name=F("company__name"),
            total_pct=ExpressionWrapper(F("bonus_pct") + F("cash_pct"), output_field=PCT_FIELD),
        )
        .order_by(F("book_closure_date").desc(nulls_last=True), "company__symbol")
        .values("id", "company_id", "symbol", "name", "fiscal_year", "bonus_pct", "cash_pct", "total_pct", "book_closure_date")
    )


def watchlist_rows(items):
    """Annotate a WatchlistItem queryset with each company's latest crawled price and change."""
    latest = DailyPrice.objects.filter(company=OuterRef("company"), source=PRICE_SOURCE).order_by("-date")
    rows = items.annotate(
        symbol=F("company__symbol"),
        name=F("company__name"),
        trade_date=Subquery(latest.values("date")[:1]),
        ltp=Subquery(latest.values("ltp")[:1]),
        prev_close=Subquery(latest.values("prev_close")[:1]),
    )
    rows = with_change(rows)
    return list(rows.values(
        "id", "company_id", "symbol", "name", "trade_date",
        "ltp", "prev_close", "change", "change_pct", "created_at",
    ))
