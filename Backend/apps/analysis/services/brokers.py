# """
# Broker net buy/sell analysis over ``FloorsheetTransaction``.

# This is a *separate* concern from the OHLCV pressure proxy in
# ``daily_metrics``.  Floorsheet data records who actually stood on each
# side of a settled trade, so a broker's net position is an observation,
# not an inference.  The two must not be merged or compared as if they
# measured the same thing.

# Every broker that appears on either side of any transaction gets exactly
# one row in the combined structure, with buy-side and sell-side totals
# side by side.  Returning two separate lists would make it impossible to
# tell a broker that bought 10,000 and sold 9,900 (net +100, barely
# committed) from one that bought 10,000 and sold nothing (net +10,000).
# """

# from __future__ import annotations

# from decimal import Decimal

# from django.db.models import (
#     Count,
#     DecimalField,
#     ExpressionWrapper,
#     F,
#     Sum,
#     Value,
# )
# from django.db.models.functions import Coalesce

# from apps.market_data.models import FloorsheetTransaction


# ZERO = Decimal("0")

# def _transaction_value():
#     """
#     ``quantity x rate``, computed in the database rather than trusting the
#     nullable ``amount`` column, which the crawler may not have populated.

#     Built fresh on every call: Django mutates expression instances while
#     resolving them against a query, so a module-level singleton shared
#     between the buy-side and sell-side aggregates gets corrupted after
#     the first use.
#     """
#     return ExpressionWrapper(
#         F("quantity") * F("rate"),
#         output_field=DecimalField(max_digits=30, decimal_places=4),
#     )


# def _decimal_zero():
#     return Value(
#         ZERO,
#         output_field=DecimalField(max_digits=30, decimal_places=4),
#     )


# def _base_queryset(company=None, start_date=None, end_date=None, date=None):
#     queryset = FloorsheetTransaction.objects.all()

#     if company is not None:
#         queryset = queryset.filter(company=company)

#     if date is not None:
#         queryset = queryset.filter(date=date)

#     if start_date is not None:
#         queryset = queryset.filter(date__gte=start_date)

#     if end_date is not None:
#         queryset = queryset.filter(date__lte=end_date)

#     return queryset


# def _clean_broker(value):
#     """
#     Normalise a broker identifier, or return ``None`` if unusable.

#     Brokers arrive as free text from the floorsheet, so blanks, ``None``
#     and whitespace-only values all have to be dropped rather than being
#     aggregated together into a phantom broker.
#     """
#     if value is None:
#         return None

#     text = str(value).strip()

#     if not text or text.lower() in {"none", "null", "-", "n/a"}:
#         return None

#     return text


# def _aggregate_side(queryset, broker_field):
#     """
#     One grouped aggregate per side.  Two queries total, regardless of how
#     many brokers or transactions exist — no per-broker follow-up query,
#     so no N+1.
#     """
#     # NOTE: the aliases are deliberately NOT ``quantity``/``value``.
#     # An annotation alias that matches a model field name shadows that
#     # field, so ``F("quantity")`` inside the value expression would
#     # resolve to ``Sum("quantity")`` and Django rejects a Sum of a Sum.
#     return (
#         queryset
#         .values(broker_field)
#         .annotate(
#             quantity_sum=Coalesce(Sum("quantity"), Value(0)),
#             value_sum=Coalesce(Sum(_transaction_value()), _decimal_zero()),
#             trade_count=Count("id"),
#         )
#     )


# def build_broker_activity(
#     company=None,
#     start_date=None,
#     end_date=None,
#     date=None,
# ):
#     """
#     Return one combined row per broker plus the derived headline metrics.

#     Formulas::

#         buy_value    = SUM(quantity x rate)  where broker is the buyer
#         sell_value   = SUM(quantity x rate)  where broker is the seller
#         net_quantity = buy_quantity - sell_quantity
#         net_value    = buy_value - sell_value

#     Gross activity and net position are reported separately and must not
#     be conflated:

#         most_active_buyer  = highest gross buy_quantity
#         most_active_seller = highest gross sell_quantity
#         top_net_buyer      = highest positive net_quantity
#         top_net_seller     = lowest (most negative) net_quantity

#     Rows are ordered by net_quantity descending, then broker ascending,
#     so the ordering is total and stable across runs and databases.
#     """
#     queryset = _base_queryset(
#         company=company,
#         start_date=start_date,
#         end_date=end_date,
#         date=date,
#     )

#     brokers = {}

#     def _row(name):
#         if name not in brokers:
#             brokers[name] = {
#                 "broker": name,
#                 "buy_quantity": 0,
#                 "sell_quantity": 0,
#                 "net_quantity": 0,
#                 "buy_value": ZERO,
#                 "sell_value": ZERO,
#                 "net_value": ZERO,
#                 "buy_trades": 0,
#                 "sell_trades": 0,
#             }
#         return brokers[name]

#     for entry in _aggregate_side(queryset, "buyer_broker"):
#         name = _clean_broker(entry["buyer_broker"])
#         if name is None:
#             continue
#         row = _row(name)
#         row["buy_quantity"] += int(entry["quantity_sum"] or 0)
#         row["buy_value"] += Decimal(entry["value_sum"] or ZERO)
#         row["buy_trades"] += int(entry["trade_count"] or 0)

#     for entry in _aggregate_side(queryset, "seller_broker"):
#         name = _clean_broker(entry["seller_broker"])
#         if name is None:
#             continue
#         row = _row(name)
#         row["sell_quantity"] += int(entry["quantity_sum"] or 0)
#         row["sell_value"] += Decimal(entry["value_sum"] or ZERO)
#         row["sell_trades"] += int(entry["trade_count"] or 0)

#     for row in brokers.values():
#         row["net_quantity"] = row["buy_quantity"] - row["sell_quantity"]
#         row["net_value"] = row["buy_value"] - row["sell_value"]
#         row["total_quantity"] = row["buy_quantity"] + row["sell_quantity"]
#         row["total_value"] = row["buy_value"] + row["sell_value"]
#         row["trades"] = row["buy_trades"] + row["sell_trades"]

#     combined = sorted(
#         brokers.values(),
#         key=lambda item: (-item["net_quantity"], item["broker"]),
#     )

#     return {
#         "brokers": combined,
#         "broker_count": len(combined),
#         "transaction_count": queryset.count(),
#         "total_buy_quantity": sum(r["buy_quantity"] for r in combined),
#         "total_sell_quantity": sum(r["sell_quantity"] for r in combined),
#         "total_buy_value": sum((r["buy_value"] for r in combined), ZERO),
#         "total_sell_value": sum((r["sell_value"] for r in combined), ZERO),
#         "most_active_buyer": _pick_most_active(combined, "buy_quantity"),
#         "most_active_seller": _pick_most_active(combined, "sell_quantity"),
#         "top_net_buyer": _pick_top_net_buyer(combined),
#         "top_net_seller": _pick_top_net_seller(combined),
#     }


# def _pick_most_active(rows, field):
#     """Highest gross quantity on one side; ties broken by broker name."""
#     candidates = [row for row in rows if row[field] > 0]

#     if not candidates:
#         return None

#     return min(candidates, key=lambda item: (-item[field], item["broker"]))


# def _pick_top_net_buyer(rows):
#     """Highest positive net quantity, or ``None`` if nobody is net long."""
#     candidates = [row for row in rows if row["net_quantity"] > 0]

#     if not candidates:
#         return None

#     return min(
#         candidates,
#         key=lambda item: (-item["net_quantity"], item["broker"]),
#     )


# def _pick_top_net_seller(rows):
#     """Lowest (most negative) net quantity, or ``None`` if nobody is net short."""
#     candidates = [row for row in rows if row["net_quantity"] < 0]

#     if not candidates:
#         return None

#     return min(
#         candidates,
#         key=lambda item: (item["net_quantity"], item["broker"]),
#     )


# def sampled_floorsheet_dates(company=None):
#     """
#     The trading dates we actually hold floorsheet rows for.

#     The floorsheet crawler collects a deliberate SAMPLE of sessions, not
#     a continuous history, so any consumer of broker analysis needs to
#     know which dates are genuinely represented before drawing a trend.
#     """
#     return list(
#         _base_queryset(company=company)
#         .order_by("-date")
#         .values_list("date", flat=True)
#         .distinct()
#     )
"""
Broker net buy/sell analysis over ``FloorsheetTransaction``.

This is a *separate* concern from the OHLCV pressure proxy in
``daily_metrics``.  Floorsheet data records who actually stood on each
side of a settled trade, so a broker's net position is an observation,
not an inference.  The two must not be merged or compared as if they
measured the same thing.

Every broker that appears on either side of any transaction gets exactly
one row in the combined structure, with buy-side and sell-side totals
side by side.  Returning two separate lists would make it impossible to
tell a broker that bought 10,000 and sold 9,900 (net +100, barely
committed) from one that bought 10,000 and sold nothing (net +10,000).
"""

from __future__ import annotations

from decimal import Decimal

from django.db.models import (
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    Q,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce, Trim

from apps.market_data.models import FloorsheetTransaction


ZERO = Decimal("0")

def _transaction_value():
    """
    ``quantity x rate``, computed in the database rather than trusting the
    nullable ``amount`` column, which the crawler may not have populated.

    Built fresh on every call: Django mutates expression instances while
    resolving them against a query, so a module-level singleton shared
    between the buy-side and sell-side aggregates gets corrupted after
    the first use.
    """
    return ExpressionWrapper(
        F("quantity") * F("rate"),
        output_field=DecimalField(max_digits=30, decimal_places=4),
    )


def _decimal_zero():
    return Value(
        ZERO,
        output_field=DecimalField(max_digits=30, decimal_places=4),
    )


def _base_queryset(
    company=None, start_date=None, end_date=None, date=None,
    company_ids=None, broker=None,
):
    queryset = FloorsheetTransaction.objects.all().annotate(
        _buyer_broker_clean=Trim("buyer_broker"),
        _seller_broker_clean=Trim("seller_broker"),
    ).exclude(transaction_id__startswith="TX-")

    if company is not None:
        queryset = queryset.filter(company=company)

    if date is not None:
        queryset = queryset.filter(date=date)

    if start_date is not None:
        queryset = queryset.filter(date__gte=start_date)

    if end_date is not None:
        queryset = queryset.filter(date__lte=end_date)

    if company_ids is not None:
        queryset = queryset.filter(company_id__in=company_ids)

    if broker is not None:
        queryset = queryset.filter(
            Q(_buyer_broker_clean=broker) | Q(_seller_broker_clean=broker)
        )

    return queryset


def _clean_broker(value):
    """
    Normalise a broker identifier, or return ``None`` if unusable.

    Brokers arrive as free text from the floorsheet, so blanks, ``None``
    and whitespace-only values all have to be dropped rather than being
    aggregated together into a phantom broker.
    """
    if value is None:
        return None

    text = str(value).strip()

    if not text or text.lower() in {"none", "null", "-", "n/a"}:
        return None

    return text


def _aggregate_side(queryset, broker_field):
    """
    One grouped aggregate per side.  Two queries total, regardless of how
    many brokers or transactions exist — no per-broker follow-up query,
    so no N+1.
    """
    # NOTE: the aliases are deliberately NOT ``quantity``/``value``.
    # An annotation alias that matches a model field name shadows that
    # field, so ``F("quantity")`` inside the value expression would
    # resolve to ``Sum("quantity")`` and Django rejects a Sum of a Sum.
    annotations = {
        "quantity_sum": Coalesce(Sum("quantity"), Value(0)),
        "value_sum": Coalesce(Sum(_transaction_value()), _decimal_zero()),
        "trade_count": Count("id"),
    }
    if broker_field == "buyer_broker":
        annotations["self_trade_count"] = Count(
            "id",
            filter=Q(_buyer_broker_clean=F("_seller_broker_clean")),
        )
    return (
        queryset
        .values(broker_field)
        .annotate(**annotations)
    )


def build_broker_activity(
    company=None,
    start_date=None,
    end_date=None,
    date=None,
    company_ids=None,
    broker=None,
):
    """
    Return one combined row per broker plus the derived headline metrics.

    Formulas::

        buy_value    = SUM(quantity x rate)  where broker is the buyer
        sell_value   = SUM(quantity x rate)  where broker is the seller
        net_quantity = buy_quantity - sell_quantity
        net_value    = buy_value - sell_value

    Gross activity and net position are reported separately and must not
    be conflated:

        most_active_buyer  = highest gross buy_quantity
        most_active_seller = highest gross sell_quantity
        top_net_buyer      = highest positive net_quantity
        top_net_seller     = lowest (most negative) net_quantity

    Rows are ordered by net_quantity descending, then broker ascending,
    so the ordering is total and stable across runs and databases.
    """
    queryset = _base_queryset(
        company=company,
        start_date=start_date,
        end_date=end_date,
        date=date,
        company_ids=company_ids,
        broker=broker,
    )

    brokers = {}

    def _row(name):
        if name not in brokers:
            brokers[name] = {
                "broker": name,
                "buy_quantity": 0,
                "sell_quantity": 0,
                "net_quantity": 0,
                "buy_value": ZERO,
                "sell_value": ZERO,
                "net_value": ZERO,
                "buy_trades": 0,
                "sell_trades": 0,
                "self_trades": 0,
            }
        return brokers[name]

    for entry in _aggregate_side(queryset, "buyer_broker"):
        name = _clean_broker(entry["buyer_broker"])
        if name is None:
            continue
        row = _row(name)
        row["buy_quantity"] += int(entry["quantity_sum"] or 0)
        row["buy_value"] += Decimal(entry["value_sum"] or ZERO)
        row["buy_trades"] += int(entry["trade_count"] or 0)
        row["self_trades"] += int(entry["self_trade_count"] or 0)

    for entry in _aggregate_side(queryset, "seller_broker"):
        name = _clean_broker(entry["seller_broker"])
        if name is None:
            continue
        row = _row(name)
        row["sell_quantity"] += int(entry["quantity_sum"] or 0)
        row["sell_value"] += Decimal(entry["value_sum"] or ZERO)
        row["sell_trades"] += int(entry["trade_count"] or 0)

    for row in brokers.values():
        row["net_quantity"] = row["buy_quantity"] - row["sell_quantity"]
        row["net_value"] = row["buy_value"] - row["sell_value"]
        row["total_quantity"] = row["buy_quantity"] + row["sell_quantity"]
        row["total_value"] = row["buy_value"] + row["sell_value"]
        row["trades"] = row["buy_trades"] + row["sell_trades"] - row["self_trades"]

    combined = sorted(
        brokers.values(),
        key=lambda item: (-item["net_quantity"], item["broker"]),
    )

    return {
        "brokers": combined,
        "broker_count": len(combined),
        "transaction_count": queryset.count(),
        "total_buy_quantity": sum(r["buy_quantity"] for r in combined),
        "total_sell_quantity": sum(r["sell_quantity"] for r in combined),
        "total_buy_value": sum((r["buy_value"] for r in combined), ZERO),
        "total_sell_value": sum((r["sell_value"] for r in combined), ZERO),
        "most_active_buyer": _pick_most_active(combined, "buy_quantity"),
        "most_active_seller": _pick_most_active(combined, "sell_quantity"),
        "top_net_buyer": _pick_top_net_buyer(combined),
        "top_net_seller": _pick_top_net_seller(combined),
    }


def _pick_most_active(rows, field):
    """Highest gross quantity on one side; ties broken by broker name."""
    candidates = [row for row in rows if row[field] > 0]

    if not candidates:
        return None

    return min(candidates, key=lambda item: (-item[field], item["broker"]))


def _pick_top_net_buyer(rows):
    """Highest positive net quantity, or ``None`` if nobody is net long."""
    candidates = [row for row in rows if row["net_quantity"] > 0]

    if not candidates:
        return None

    return min(
        candidates,
        key=lambda item: (-item["net_quantity"], item["broker"]),
    )


def _pick_top_net_seller(rows):
    """Lowest (most negative) net quantity, or ``None`` if nobody is net short."""
    candidates = [row for row in rows if row["net_quantity"] < 0]

    if not candidates:
        return None

    return min(
        candidates,
        key=lambda item: (item["net_quantity"], item["broker"]),
    )


def sampled_floorsheet_dates(
    company=None, start_date=None, end_date=None,
    company_ids=None, broker=None,
):
    """
    The trading dates we actually hold floorsheet rows for.

    The floorsheet crawler collects a deliberate SAMPLE of sessions, not
    a continuous history, so any consumer of broker analysis needs to
    know which dates are genuinely represented before drawing a trend.
    """
    return list(
        _base_queryset(
            company=company,
            start_date=start_date,
            end_date=end_date,
            company_ids=company_ids,
            broker=broker,
        )
        .order_by("-date")
        .values_list("date", flat=True)
        .distinct()
    )
