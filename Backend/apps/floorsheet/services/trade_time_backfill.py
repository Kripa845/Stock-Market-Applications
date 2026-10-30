"""
Fill missing floorsheet trade times from ShareHub.

Rows from the date-only ShareSansar floorsheet have trade_time NULL.  ShareHub serves the same
contracts with their times, so a NULL row gets ShareHub's time when the contract number matches
and the quantity and rate agree.  Nothing else is touched: no inserts, no other fields, and a
row that already has a time is never changed (so re-running is safe).  Unmatched rows stay NULL;
times are never invented.
"""

from decimal import Decimal

from django.db import transaction

from apps.floorsheet.models import FloorsheetTransaction
from apps.floorsheet.services.sharehub_floorsheet import ShareHubError, fetch_company_day
from apps.floorsheet.services.sharehub_time import parse_sharehub_time


def plan_company_day(company, day, fetch=None):
    """
    What filling ``company``'s untimed trades on ``day`` would change.  Returns
    {"untimed", "changes": [(pk, transaction_id, trade_time)], "missing": [...], "mismatched": [...]}.
    """
    rows = list(
        FloorsheetTransaction.objects
        .filter(company=company, date=day, trade_time__isnull=True)
        .order_by("transaction_id")
        .values_list("pk", "transaction_id", "quantity", "rate")
    )
    plan = {"untimed": len(rows), "changes": [], "missing": [], "mismatched": []}
    if not rows:
        return plan

    source = {}
    for item in (fetch or fetch_company_day)(day, company.symbol):
        if str(item.get("symbol", "")).upper() != company.symbol.upper():
            continue
        if str(item.get("businessDate", ""))[:10] != day.isoformat():
            raise ShareHubError(f"Asked ShareHub for {day} but got {item.get('businessDate')}; nothing planned.")
        source[str(item.get("contractId"))] = item

    for pk, txn_id, quantity, rate in rows:
        item = source.get(txn_id)
        if item is None or not item.get("tradeTime"):
            plan["missing"].append(txn_id)
            continue
        try:
            same = int(item["contractQuantity"]) == quantity and Decimal(str(item["contractRate"])) == rate
            when = parse_sharehub_time(item["tradeTime"])
        except (KeyError, TypeError, ValueError, ArithmeticError):
            same = False
        if not same:
            plan["mismatched"].append(txn_id)
            continue
        plan["changes"].append((pk, txn_id, when))
    return plan


def apply_changes(changes):
    """Set trade_time on rows that are still NULL; returns how many were written."""
    if not changes:
        return 0
    with transaction.atomic():
        still_null = set(
            FloorsheetTransaction.objects.select_for_update()
            .filter(pk__in=[pk for pk, _, _ in changes], trade_time__isnull=True)
            .values_list("pk", flat=True)
        )
        objs = [FloorsheetTransaction(pk=pk, trade_time=when) for pk, _, when in changes if pk in still_null]
        FloorsheetTransaction.objects.bulk_update(objs, ["trade_time"], batch_size=2000)
    return len(objs)


def undo_changes(pks):
    """Clear trade_time again on the given rows (restores the NULL a backup recorded)."""
    with transaction.atomic():
        return FloorsheetTransaction.objects.filter(pk__in=pks).update(trade_time=None)
