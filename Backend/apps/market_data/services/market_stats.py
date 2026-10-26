"""
Statistics for the tracked-companies dashboard.

SCOPE: only the active, tracked companies (``Company.tracking.is_tracked``)
and only crawled prices (``DailyPrice.source == "crawled"``).  Nothing here
describes the whole NEPSE market; callers must label results
"Tracked companies".

Session change, movers, the summary and top lists live in services.movers
(one definition everywhere).  This module holds the scope helpers, broker
activity, price signals and the Tracked Basket (dividends: services.dividends).

Python is used only to arrange already-aggregated rows into the response
(merging the buy-side and sell-side broker tables); no per-trade or
per-price arithmetic happens in Python loops.
"""

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db.models import (
    Avg,
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    Max,
    Min,
    Sum,
)
from django.db.models.functions import Trim

from apps.companies.models import Company
from apps.floorsheet.models import Broker
from apps.market_data.models import DailyPrice
from apps.market_data.services.price_fields import real_floorsheet
from apps.market_intelligence.models import ProxyIndexSnapshot


PRICE_SOURCE = "crawled"
BROKER_WINDOWS = (5, 20)
CONCENTRATION_TOP_N = 5

CORPORATE_ACTION_NOTE = (
    "change_pct uses ShareSansar's published % change when stored; it is measured against the "
    "exchange's adjusted previous close, so bonus / right book closures do not show as drops "
    "(rows marked adjusted=true). Without it the change is close-to-close (unadjusted=true), and "
    "a close-to-close move beyond 10% is excluded as a possible corporate action because no "
    "corporate-action data is stored."
)

UNITS = {
    "price": "NPR",
    "change": "NPR",
    "change_pct": "percent",
    "turnover": "NPR",
    "volume": "shares",
    "transactions": "trades",
}

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

    price = latest.close
    average_volume = volume_average["value"]

    def pct(numerator, denominator):
        return (Decimal(numerator) * 100 / Decimal(denominator)) if numerator is not None and denominator else None

    return {
        "symbol": latest.company.symbol,
        "trade_date": latest.date,
        "close": price,
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
            "close_vs_ma5_pct": pct(price - ma5["value"], ma5["value"]) if ma5["value"] else None,
            "close_vs_ma20_pct": pct(price - ma20["value"], ma20["value"]) if ma20["value"] else None,
        },
        "range_52w": {
            **range_52w,
            "distance_from_high_pct": pct(price - range_52w["high"], range_52w["high"]) if range_52w["high"] else None,
            "distance_from_low_pct": pct(price - range_52w["low"], range_52w["low"]) if range_52w["low"] else None,
        },
    }


# ----------------------------------------------------------------------
# Basket index, watchlist
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
