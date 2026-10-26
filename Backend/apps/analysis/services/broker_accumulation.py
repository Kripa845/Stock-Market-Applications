"""
Broker accumulation / distribution for one stock over a window of sessions.

Net quantity per broker (bought - sold) says who is building a position
(accumulating) and who is unloading one (distributing).  The stock-level
signal compares how much the five biggest net buyers absorbed against how
much the five biggest net sellers released:

    ratio = top5_buy_net / |top5_sell_net|
    > BROKER_SIGNAL_ACCUMULATION_RATIO  -> accumulation
    < BROKER_SIGNAL_DISTRIBUTION_RATIO  -> distribution
    otherwise                           -> neutral

Every number is aggregated in the database (grouped Sum / Count); Python
only walks the per-broker or per-(day, broker) aggregates, never raw trades.

Windows count floorsheet SESSIONS held for the stock, not calendar days, so
holidays and missing crawl days never shrink a "1w" window to three sessions.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.db.models import Count, F, Q, Sum, Value
from django.db.models.functions import Coalesce

from apps.market_data.models import DailyPrice

from .brokers import _base_queryset, _clean_broker, _decimal_zero, _transaction_value

logger = logging.getLogger(__name__)

ZERO = Decimal("0")

# Window -> number of floorsheet sessions it covers, newest first.
WINDOW_SESSIONS = {"1d": 1, "1w": 5, "1m": 21, "3m": 63}
DEFAULT_WINDOW = "1w"
TOP_N = 5
# How far back a broker's buying / selling streak is followed.
STREAK_LOOKBACK_SESSIONS = 63

ACCUMULATION = "accumulation"
DISTRIBUTION = "distribution"
NEUTRAL = "neutral"
NO_DATA = "no_data"


def accumulation_ratio():
    return Decimal(str(getattr(settings, "BROKER_SIGNAL_ACCUMULATION_RATIO", "1.2")))


def distribution_ratio():
    return Decimal(str(getattr(settings, "BROKER_SIGNAL_DISTRIBUTION_RATIO", "0.8")))


def exclude_self_trades_default():
    return bool(getattr(settings, "BROKER_EXCLUDE_SELF_TRADES", False))


@dataclass(frozen=True)
class Window:
    """The resolved range: ``sessions`` are the floorsheet dates inside it, newest first."""

    key: str
    start_date: date | None
    end_date: date | None
    sessions: tuple[date, ...]


def _session_dates(company, end_date=None, start_date=None, limit=None):
    queryset = _base_queryset(company=company, start_date=start_date, end_date=end_date)
    dates = queryset.order_by("-date").values_list("date", flat=True).distinct()
    return list(dates[:limit] if limit else dates)


def resolve_window(company, window=None, start_date=None, end_date=None) -> Window:
    """
    ``start_date`` / ``end_date`` give a custom range.  Otherwise ``window``
    (1d / 1w / 1m / 3m) counts back that many sessions from ``end_date`` or,
    without one, from the latest session held for the stock.
    """
    if start_date is not None:
        sessions = _session_dates(company, start_date=start_date, end_date=end_date)
        return Window("custom", start_date, end_date or (sessions[0] if sessions else start_date), tuple(sessions))

    key = window if window in WINDOW_SESSIONS else DEFAULT_WINDOW
    sessions = _session_dates(company, end_date=end_date, limit=WINDOW_SESSIONS[key])
    if not sessions:
        return Window(key, None, end_date, ())
    return Window(key, sessions[-1], sessions[0], tuple(sessions))


def _window_queryset(company, window: Window, exclude_self_trades: bool):
    queryset = _base_queryset(company=company, start_date=window.start_date, end_date=window.end_date)
    if exclude_self_trades:
        queryset = queryset.exclude(_buyer_broker_clean=F("_seller_broker_clean"))
    return queryset


def _side_totals(queryset, broker_field, group_by_date=False):
    """One grouped aggregate per side: quantity, value and trade count per broker (and day)."""
    fields = ("date", broker_field) if group_by_date else (broker_field,)
    return (
        queryset
        .order_by()
        .values(*fields)
        .annotate(
            quantity_sum=Coalesce(Sum("quantity"), Value(0)),
            value_sum=Coalesce(Sum(_transaction_value()), _decimal_zero()),
            trade_count=Count("id"),
        )
    )


def _ratio(numerator, denominator):
    """``numerator / denominator`` as a Decimal, or ``None`` when the denominator is zero."""
    if not denominator:
        return None
    return Decimal(numerator) / Decimal(denominator)


def _pct(numerator, denominator):
    value = _ratio(numerator, denominator)
    return None if value is None else (value * 100).quantize(Decimal("0.01"))


def _price(value):
    return None if value is None else value.quantize(Decimal("0.01"))


def broker_rows(company, window: Window, exclude_self_trades=None):
    """
    Per-broker buy / sell / net for the window, biggest net buyer first, plus
    the window totals.  ``net_pct_of_volume`` is the broker's net as a share of
    every share traded in the window (each trade counted once).
    """
    if exclude_self_trades is None:
        exclude_self_trades = exclude_self_trades_default()
    queryset = _window_queryset(company, window, exclude_self_trades)

    rows: dict[str, dict] = {}

    def row(name):
        return rows.setdefault(name, {
            "broker": name,
            "buy_qty": 0, "sell_qty": 0,
            "buy_amount": ZERO, "sell_amount": ZERO,
            "buy_trades": 0, "sell_trades": 0,
        })

    for side, field in (("buy", "buyer_broker"), ("sell", "seller_broker")):
        for entry in _side_totals(queryset, field):
            name = _clean_broker(entry[field])
            if name is None:
                continue
            target = row(name)
            target[f"{side}_qty"] += int(entry["quantity_sum"] or 0)
            target[f"{side}_amount"] += Decimal(entry["value_sum"] or ZERO)
            target[f"{side}_trades"] += int(entry["trade_count"] or 0)

    # Aliases must not reuse a model field name (``quantity``), or Sum("quantity") resolves to the alias.
    totals = queryset.aggregate(
        quantity_sum=Coalesce(Sum("quantity"), Value(0)),
        amount_sum=Coalesce(Sum(_transaction_value()), _decimal_zero()),
        trade_count=Count("id"),
        self_trade_qty=Coalesce(Sum("quantity", filter=Q(_buyer_broker_clean=F("_seller_broker_clean"))), Value(0)),
    )
    total_qty = int(totals["quantity_sum"] or 0)

    for item in rows.values():
        item["net_qty"] = item["buy_qty"] - item["sell_qty"]
        item["net_amount"] = item["buy_amount"] - item["sell_amount"]
        item["avg_buy"] = _price(_ratio(item["buy_amount"], item["buy_qty"]))
        item["avg_sell"] = _price(_ratio(item["sell_amount"], item["sell_qty"]))
        item["net_pct_of_volume"] = _pct(item["net_qty"], total_qty)

    ordered = sorted(rows.values(), key=lambda item: (-item["net_qty"], item["broker"]))
    return ordered, {
        "total_qty": total_qty,
        "total_amount": totals["amount_sum"] or ZERO,
        "trade_count": totals["trade_count"],
        "self_trade_qty": int(totals["self_trade_qty"] or 0),
        "exclude_self_trades": exclude_self_trades,
    }


def classify(top_buy_net, top_sell_net):
    """``(signal, ratio)`` from the top-N net totals; ``top_sell_net`` is <= 0."""
    if not top_buy_net and not top_sell_net:
        return NEUTRAL, None
    ratio = _ratio(top_buy_net, abs(top_sell_net))
    if ratio is None:
        # Nobody net sold: all buying, no distribution to weigh it against.
        return ACCUMULATION, None
    if ratio > accumulation_ratio():
        return ACCUMULATION, ratio
    if ratio < distribution_ratio():
        return DISTRIBUTION, ratio
    return NEUTRAL, ratio


def top_brokers(rows, n=TOP_N):
    accumulators = [item for item in rows if item["net_qty"] > 0][:n]
    distributors = sorted((item for item in rows if item["net_qty"] < 0), key=lambda item: (item["net_qty"], item["broker"]))[:n]
    return accumulators, distributors


def latest_close(company, on_or_before=None):
    """The latest crawled close on or before the date, with its date (synthetic prices are ignored)."""
    queryset = DailyPrice.objects.filter(company=company, source="crawled")
    if on_or_before is not None:
        queryset = queryset.filter(date__lte=on_or_before)
    price = queryset.order_by("-date").values("date", "close").first()
    return (price["close"], price["date"]) if price else (None, None)


def _daily_broker_net(company, start_date, end_date, exclude_self_trades, brokers=None):
    """``{date: {broker: net_qty}}`` from two grouped queries, optionally limited to some brokers."""
    queryset = _base_queryset(company=company, start_date=start_date, end_date=end_date)
    if exclude_self_trades:
        queryset = queryset.exclude(_buyer_broker_clean=F("_seller_broker_clean"))
    if brokers is not None:
        queryset = queryset.filter(Q(_buyer_broker_clean__in=brokers) | Q(_seller_broker_clean__in=brokers))

    net: dict[date, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    side_qty: dict[date, dict[str, int]] = defaultdict(lambda: {"buy": 0, "sell": 0})
    for side, field, sign in (("buy", "buyer_broker", 1), ("sell", "seller_broker", -1)):
        for entry in _side_totals(queryset, field, group_by_date=True):
            name = _clean_broker(entry[field])
            if name is None or (brokers is not None and name not in brokers):
                continue
            quantity = int(entry["quantity_sum"] or 0)
            net[entry["date"]][name] += sign * quantity
            side_qty[entry["date"]][side] += quantity
    return net, side_qty


def streaks(company, brokers, end_date, exclude_self_trades=None, lookback=STREAK_LOOKBACK_SESSIONS):
    """
    ``{broker: {"direction": "buying" | "selling" | None, "days": n}}``: how
    many sessions in a row, ending at ``end_date``, the broker has been net
    buying or net selling.  A session without a trade by the broker ends it.
    """
    if exclude_self_trades is None:
        exclude_self_trades = exclude_self_trades_default()
    if not brokers or end_date is None:
        return {}
    sessions = _session_dates(company, end_date=end_date, limit=lookback)
    if not sessions:
        return {}
    net, _ = _daily_broker_net(company, sessions[-1], sessions[0], exclude_self_trades, brokers=set(brokers))

    result = {}
    for broker in brokers:
        direction, days = None, 0
        for session in sessions:  # newest first
            value = net.get(session, {}).get(broker, 0)
            sign = "buying" if value > 0 else "selling" if value < 0 else None
            if sign is None or (direction is not None and sign != direction):
                break
            direction, days = sign, days + 1
        result[broker] = {"direction": direction, "days": days}
    return result


def _vs_close(close, average):
    """How far the latest close is from a broker's average price, in %."""
    if close is None or average is None:
        return None
    return _pct(Decimal(close) - average, average)


def build_broker_summary(company, window: Window, exclude_self_trades=None):
    """Every broker's row for the window, with the window totals."""
    rows, totals = broker_rows(company, window, exclude_self_trades)
    return {"rows": rows, **totals}


def build_broker_signal(company, window: Window, exclude_self_trades=None):
    """The stock-level signal, the top-N lists with P/L vs the latest close and streaks, and totals."""
    if exclude_self_trades is None:
        exclude_self_trades = exclude_self_trades_default()
    rows, totals = broker_rows(company, window, exclude_self_trades)
    accumulators, distributors = top_brokers(rows)
    top_buy_net = sum(item["net_qty"] for item in accumulators)
    top_sell_net = sum(item["net_qty"] for item in distributors)
    signal, ratio = classify(top_buy_net, top_sell_net) if rows else (NO_DATA, None)

    close, close_date = latest_close(company, window.end_date)
    runs = streaks(company, [item["broker"] for item in accumulators + distributors], window.end_date, exclude_self_trades)

    def enrich(item):
        return {
            **item,
            "close_vs_avg_buy_pct": _vs_close(close, item["avg_buy"]),
            "close_vs_avg_sell_pct": _vs_close(close, item["avg_sell"]),
            "streak": runs.get(item["broker"], {"direction": None, "days": 0}),
        }

    return {
        "signal": signal,
        "ratio": None if ratio is None else ratio.quantize(Decimal("0.01")),
        "thresholds": {"accumulation": accumulation_ratio(), "distribution": distribution_ratio()},
        "top5_buy_net": top_buy_net,
        "top5_sell_net": top_sell_net,
        "accumulators": [enrich(item) for item in accumulators],
        "distributors": [enrich(item) for item in distributors],
        "latest_close": close,
        "latest_close_date": close_date,
        "broker_count": len(rows),
        **totals,
    }


def build_broker_flow(company, window: Window, exclude_self_trades=None, n=TOP_N):
    """
    One point per session: the close, and the net of that day's top-N net
    buyers vs top-N net sellers.  All brokers' nets sum to zero by definition,
    so the concentrated top-N flow is what shows direction.

    Also checks that each day's bought quantity equals its sold quantity
    (every trade has one buyer and one seller); a gap means rows with an
    unusable broker code, logged and returned as ``warnings``.
    """
    if exclude_self_trades is None:
        exclude_self_trades = exclude_self_trades_default()
    if not window.sessions:
        return {"points": [], "warnings": []}

    net, side_qty = _daily_broker_net(company, window.start_date, window.end_date, exclude_self_trades)
    closes = dict(
        DailyPrice.objects
        .filter(company=company, source="crawled", date__gte=window.start_date, date__lte=window.end_date)
        .values_list("date", "close")
    )

    points, warnings = [], []
    for session in sorted(window.sessions):
        by_broker = net.get(session, {})
        values = sorted(by_broker.values(), reverse=True)
        buy_net = sum(v for v in values[:n] if v > 0)
        sell_net = sum(v for v in sorted(values)[:n] if v < 0)
        quantities = side_qty.get(session, {"buy": 0, "sell": 0})
        if quantities["buy"] != quantities["sell"]:
            message = f"{company.symbol} {session}: bought {quantities['buy']} != sold {quantities['sell']}"
            logger.warning("broker flow: %s", message)
            warnings.append(message)
        signal, ratio = classify(buy_net, sell_net)
        points.append({
            "date": session,
            "close": closes.get(session),
            "top5_buy_net": buy_net,
            "top5_sell_net": sell_net,
            "net_flow": buy_net + sell_net,
            "ratio": None if ratio is None else ratio.quantize(Decimal("0.01")),
            "signal": signal,
            "volume": quantities["buy"],
        })
    return {"points": points, "warnings": warnings}
