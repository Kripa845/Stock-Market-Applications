"""
Market-wide accumulation / distribution: which broker is net buying or net
selling which stock over a period.

For every (stock, broker) pair in the period:

    net_qty    = shares bought - shares sold
    net_amount = value bought  - value sold        (quantity x rate)

Pairs with net_qty > 0 are accumulation, net_qty < 0 distribution.  Each side
is ranked by net_amount (largest absolute first).  ``avg_rate`` is the broker's
average buy price on the accumulation side and average sell price on the
distribution side.  ``float_qty_pct`` is net_qty as a share of the stock's
public (non-promoter) shares from the latest CompanyDaily row, the free-float
stand-in used elsewhere.  CompanyDaily only covers some stocks, so without it
the denominator falls back to Company.listed_shares (a smaller %, since listed
includes promoter shares) and ``float_basis`` says which was used; both
missing gives null.

Like broker_accumulation, periods count floorsheet SESSIONS, newest first,
across the stocks in scope.  A period longer than the collected history simply
covers all of it; ``sessions`` / ``start_date`` in the result say how much.
"""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce

from apps.companies.models import Company
from apps.market_indices.models import CompanyDaily

from .broker_accumulation import _price, _ratio
from .brokers import _base_queryset, _clean_broker, _decimal_zero, _transaction_value

ZERO = Decimal("0")
FLOAT_PCT_PLACES = Decimal("0.0001")

PERIOD_SESSIONS = {
    "1D": 1, "2D": 2, "1W": 5, "2W": 10, "1M": 21,
    "3M": 63, "6M": 126, "1Y": 250, "2Y": 500, "3Y": 750,
}
DEFAULT_PERIOD = "1D"


def period_sessions(period, company_ids=None):
    """The floorsheet dates the period covers, newest first."""
    dates = (
        _base_queryset(company_ids=company_ids)
        .order_by("-date")
        .values_list("date", flat=True)
        .distinct()
    )
    return list(dates[:PERIOD_SESSIONS[period]])


def _pair_totals(queryset, broker_field):
    """Quantity and value per (stock, broker) for one side, aggregated in the database."""
    return (
        queryset
        .order_by()
        .values("company_id", broker_field)
        .annotate(
            quantity_sum=Coalesce(Sum("quantity"), Value(0)),
            value_sum=Coalesce(Sum(_transaction_value()), _decimal_zero()),
            trade_count=Count("id"),
        )
    )


def _companies(company_ids):
    """symbol, sector, listed shares and latest public shares for each stock id."""
    latest_public = (
        CompanyDaily.objects
        .filter(symbol=OuterRef("symbol"), public_shares__isnull=False)
        .order_by("-date")
        .values("public_shares")[:1]
    )
    return {
        row["id"]: row
        for row in Company.objects
        .filter(id__in=company_ids)
        .annotate(public_shares=Subquery(latest_public))
        .values("id", "symbol", "sector", "listed_shares", "public_shares")
    }


def _float_base(company):
    """(shares, basis) for the float % denominator."""
    if company["public_shares"]:
        return company["public_shares"], "public"
    if company["listed_shares"]:
        return company["listed_shares"], "listed"
    return None, None


def build_acc_dist(period=DEFAULT_PERIOD, company_ids=None):
    """
    ``company_ids`` limits the stocks (None = all).  Returns the resolved
    period plus ``accumulation`` / ``distribution`` row lists, rank 1 first.
    """
    sessions = period_sessions(period, company_ids)
    result = {
        "period": period,
        "sessions": len(sessions),
        "start_date": sessions[-1] if sessions else None,
        "end_date": sessions[0] if sessions else None,
        "accumulation": [],
        "distribution": [],
    }
    if not sessions:
        return result

    queryset = _base_queryset(company_ids=company_ids, start_date=sessions[-1], end_date=sessions[0])

    pairs: dict[tuple[int, str], dict] = {}
    for side, field in (("buy", "buyer_broker"), ("sell", "seller_broker")):
        for entry in _pair_totals(queryset, field):
            broker = _clean_broker(entry[field])
            if broker is None:
                continue
            pair = pairs.setdefault((entry["company_id"], broker), {
                "buy_qty": 0, "sell_qty": 0, "buy_amount": ZERO, "sell_amount": ZERO,
            })
            pair[f"{side}_qty"] += int(entry["quantity_sum"] or 0)
            pair[f"{side}_amount"] += Decimal(entry["value_sum"] or ZERO)

    companies = _companies({company_id for company_id, _ in pairs})

    for (company_id, broker), pair in pairs.items():
        net_qty = pair["buy_qty"] - pair["sell_qty"]
        if net_qty == 0:
            continue
        side = "buy" if net_qty > 0 else "sell"
        company = companies[company_id]
        float_shares, float_basis = _float_base(company)
        float_pct = _ratio(net_qty * 100, float_shares)
        result["accumulation" if net_qty > 0 else "distribution"].append({
            "symbol": company["symbol"],
            "sector": company["sector"],
            "broker": broker,
            "net_qty": net_qty,
            "net_amount": pair["buy_amount"] - pair["sell_amount"],
            "avg_rate": _price(_ratio(pair[f"{side}_amount"], pair[f"{side}_qty"])),
            "float_qty_pct": None if float_pct is None else float_pct.quantize(FLOAT_PCT_PLACES),
            "float_basis": float_basis,
        })

    for key, sign in (("accumulation", -1), ("distribution", 1)):
        rows = sorted(result[key], key=lambda row: (sign * row["net_amount"], row["symbol"], row["broker"]))
        for rank, row in enumerate(rows, start=1):
            row["rank"] = rank
        result[key] = rows
    return result
