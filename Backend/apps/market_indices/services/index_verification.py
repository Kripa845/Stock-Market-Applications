"""
Is every index value on the indices page really in the database, and does it still match NEPSE?

For one session, each catalogued index's stored IndexDaily row is compared field by field with
NEPSE's own index feed (the same feed and parser sync_index_history uses):

    scraped   -- stored, every field present and equal to the feed
    missing   -- no stored row for the session, or a field the feed has is empty in the database
                 (also: no previous session stored, so CH / turnover-change columns cannot be computed)
    mismatch  -- stored but different from the feed (both values are returned)

When the feed cannot be reached, rows are only checked for presence and ``feed_ok`` is False,
so the page never claims a value was verified when it was not.  Nothing here writes to the database;
``resync_session`` does that, through sync_index_history (update_or_create, no duplicates).
"""

from datetime import timedelta
from decimal import Decimal

from django.db.models import Max
from django.utils import timezone

from apps.market_indices.models import IndexDaily, MarketIndex
from apps.market_indices.services.aggregates import index_session
from apps.market_indices.services.nepse_indices import (
    IndexFeedError,
    fetch_index_history,
    iter_history,
    sync_index_history,
)

FIELDS = ("open", "high", "low", "close", "turnover", "volume", "transactions", "source_change_pct")
# Feed values are rounded to 2 dp (index points, NPR) or whole numbers (shares, trades).
TOLERANCE = Decimal("0.005")
# Ask the feed for a few days before the session so a holiday gap still returns the previous session.
FEED_LOOKBACK_DAYS = 7

SCRAPED, MISSING, MISMATCH = "scraped", "missing", "mismatch"


def _same(stored, source):
    return abs(Decimal(stored) - Decimal(source)) <= TOLERANCE


def _feed_rows(history, session):
    """{index code: field values} for ``session`` from a feed response."""
    return {
        index.code: values
        for _, index, day, values in iter_history(history)
        if index is not None and day == session
    }


def compare_index(stored, previous_exists, source):
    """Status, missing fields and mismatches for one index (``source`` is None when not checked)."""
    if stored is None:
        return MISSING, list(FIELDS), []
    missing = [
        field for field in FIELDS
        if getattr(stored, field) is None and (source is None or source.get(field) is not None)
    ]
    if not previous_exists:
        missing.append("previous_session")
    mismatches = []
    if source is not None:
        for field in FIELDS:
            value, expected = getattr(stored, field), source.get(field)
            if value is not None and expected is not None and not _same(value, expected):
                mismatches.append({"field": field, "stored": value, "source": expected})
    status = MISMATCH if mismatches else MISSING if missing else SCRAPED
    return status, missing, mismatches


def verify_session(day=None, history=None):
    """Per-index status for the latest stored session on or before ``day``."""
    session = index_session(day)
    if session is None:
        return {"session": None, "feed_ok": False, "feed_error": "No index sessions stored yet.", "rows": [], "summary": {}}

    feed_error = None
    source_rows = None
    try:
        history = history if history is not None else fetch_index_history(session - timedelta(days=FEED_LOOKBACK_DAYS))
        source_rows = _feed_rows(history, session)
        if not source_rows:
            feed_error = f"The NEPSE feed has no rows for {session}."
            source_rows = None
    except IndexFeedError as exc:
        feed_error = str(exc)

    stored = {
        row.index.code: row
        for row in IndexDaily.objects.filter(date=session).select_related("index")
    }
    with_previous = set(
        IndexDaily.objects.filter(date__lt=session).values_list("index__code", flat=True).distinct()
    )

    rows = []
    for index in MarketIndex.objects.all():
        source = source_rows.get(index.code) if source_rows is not None else None
        status, missing, mismatches = compare_index(stored.get(index.code), index.code in with_previous, source)
        note = None
        if source is None and stored.get(index.code) is not None:
            note = "Stored; not re-checked against NEPSE." if source_rows is None else "Stored; NEPSE's feed has no row for it."
        rows.append({
            "code": index.code,
            "name": index.name,
            "kind": index.kind,
            "status": status,
            "verified": source is not None,
            "note": note,
            "missing": missing,
            "mismatches": mismatches,
        })

    summary = {status: sum(row["status"] == status for row in rows) for status in (SCRAPED, MISSING, MISMATCH)}
    summary["total"] = len(rows)
    last_updated = IndexDaily.objects.filter(date=session).aggregate(at=Max("updated_at"))["at"]
    return {
        "session": session,
        "feed_ok": source_rows is not None,
        "feed_error": feed_error,
        "source": "NEPSE index history (nepalstock.com.np)",
        "checked_at": timezone.now(),
        "last_updated": last_updated,
        "rows": rows,
        "summary": summary,
    }


def resync_session(day=None):
    """Re-scrape ``day``'s session (and the days before it) from NEPSE, then verify again."""
    session = index_session(day) or timezone.localdate()
    since = session - timedelta(days=FEED_LOOKBACK_DAYS)
    history = fetch_index_history(since)
    result = sync_index_history(since, history=history)
    return result, verify_session(session, history=history)
