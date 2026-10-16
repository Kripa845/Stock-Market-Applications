"""
Fallback index history from ShareSansar, for when NEPSE's own feed (nepse_indices) fails.

Source (checked against the live page 2026-10-16): ShareSansar "Index History", a
DataTables table filled from a JSON endpoint on the same URL.  One request per index:

    GET /index-history-data?index_id=<id>&from=YYYY-MM-DD&to=YYYY-MM-DD&start=0&length=50
        (X-Requested-With: XMLHttpRequest, after loading the page once for its session cookie)
    row keys: open, high, low, current (= close), change_, per_change, turnover, published_date

Compared with NEPSE for 15 Oct 2026: close and % change identical, open a few hundredths
off (2621.49 vs 2621.41), turnover ~1.6% higher (4.717 vs 4.644 Arab), and no volume or
transaction counts.  So NEPSE always wins:

    * a session NEPSE already stored is never touched;
    * rows stored from here carry source="sharesansar" (the indices page labels them), and
      the next successful NEPSE sync overwrites them (update_or_create sets source="crawled");
    * volume / transactions stay empty, which the verification shows as "missing".

A row whose close is 0 or missing is an unfinished session (the same rule as nepse_indices)
and is never stored.
"""

import logging
import time
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

import requests
from django.utils import timezone

from apps.market_data.services.live_prices import NPT
from apps.market_indices.models import IndexDaily, MarketIndex

logger = logging.getLogger(__name__)

SOURCE = "sharesansar"
PAGE_URL = "https://www.sharesansar.com/index-history-data"
# ShareSansar's <select id="index"> option values -> MarketIndex.code.  Its "Insurance" (7)
# has no NEPSE counterpart in the catalogue and is not fetched.
SHARESANSAR_INDEX_IDS = {
    12: "NEPSE", 16: "SENSITIVE", 4: "FLOAT", 15: "SENSITIVE_FLOAT",
    1: "BANKING", 2: "DEVBANK", 3: "FINANCE", 5: "HOTELS", 6: "HYDROPOWER", 18: "INVESTMENT",
    8: "LIFEINSU", 9: "MANUFACTURE", 10: "MICROFINANCE", 11: "MUTUAL", 13: "NONLIFEINSU",
    14: "OTHERS", 17: "TRADING",
}
# DataTables columns in the page's order; the server answers 500 unless they are all named.
COLUMNS = ["DT_Row_Index", "open", "high", "low", "current", "change_", "per_change", "turnover", "published_date"]
PAGE_SIZE = 50                  # the page's own maximum ("lengthMenu": [10, 20, 50])
DEFAULT_DAYS = 10
REQUEST_DELAY_SECONDS = 0.5
TIMEOUT_SECONDS = 20
HEADERS = {"User-Agent": "personal-stock-project/1.0"}
AJAX_HEADERS = {**HEADERS, "X-Requested-With": "XMLHttpRequest", "Accept": "application/json, text/javascript, */*"}


class ShareSansarIndexError(Exception):
    """ShareSansar's index history could not be read or returned nothing usable."""


def _decimal(value):
    try:
        return None if value in (None, "") else Decimal(str(value).replace(",", ""))
    except (InvalidOperation, TypeError, ValueError):
        return None


def parse_row(row):
    """(date, IndexDaily field values) for one ShareSansar row, or None when unusable or unfinished."""
    try:
        day = date.fromisoformat(str(row.get("published_date"))[:10])
    except (TypeError, ValueError):
        return None
    close = _decimal(row.get("current"))
    if close is None or close <= 0:
        return None
    return day, {
        "open": _decimal(row.get("open")), "high": _decimal(row.get("high")), "low": _decimal(row.get("low")),
        "close": close, "turnover": _decimal(row.get("turnover")),
        "volume": None, "transactions": None,
        "source_change_pct": _decimal(row.get("per_change")),
    }


def fetch_index_history(since, until=None, session=None, sleep=time.sleep):
    """{index code: [ShareSansar rows]} for every mapped index from ``since`` to ``until`` (today)."""
    until = until or timezone.now().astimezone(NPT).date()
    session = session or requests.Session()
    try:
        session.get(PAGE_URL, headers=HEADERS, timeout=TIMEOUT_SECONDS).raise_for_status()
    except requests.RequestException as exc:
        raise ShareSansarIndexError(f"ShareSansar index page failed: {exc}") from exc

    history = {}
    for index_id, code in SHARESANSAR_INDEX_IDS.items():
        params = {
            "draw": "1", "start": "0", "length": str(PAGE_SIZE),
            "order[0][column]": str(COLUMNS.index("published_date")), "order[0][dir]": "desc",
            "index_id": str(index_id), "from": since.isoformat(), "to": until.isoformat(),
            **{f"columns[{position}][data]": name for position, name in enumerate(COLUMNS)},
        }
        try:
            response = session.get(PAGE_URL, params=params, headers=AJAX_HEADERS, timeout=TIMEOUT_SECONDS)
            response.raise_for_status()
            rows = response.json().get("data")
        except (requests.RequestException, ValueError, AttributeError) as exc:
            logger.warning("ShareSansar index %s (%s) failed: %s", code, index_id, exc)
            rows = None
        if isinstance(rows, list):
            history[code] = rows
        sleep(REQUEST_DELAY_SECONDS)
    if not any(history.values()):
        raise ShareSansarIndexError("ShareSansar returned no index rows")
    return history


def backfill_index_history(since=None, history=None):
    """
    Store ShareSansar sessions that NEPSE has not stored.  Rows from NEPSE are never changed;
    earlier ShareSansar rows are refreshed.  Returns counts.
    """
    since = since or (timezone.now().astimezone(NPT).date() - timedelta(days=DEFAULT_DAYS))
    history = history if history is not None else fetch_index_history(since)
    catalogue = {index.code: index for index in MarketIndex.objects.all()}

    counts = {"saved": 0, "refreshed": 0, "kept_nepse": 0, "skipped": 0}
    dates = set()
    for code, rows in history.items():
        index = catalogue.get(code)
        for row in rows if index is not None else []:
            parsed = parse_row(row) if isinstance(row, dict) else None
            if parsed is None:
                counts["skipped"] += 1
                continue
            day, values = parsed
            if day < since:
                continue
            existing = IndexDaily.objects.filter(index=index, date=day).first()
            if existing is not None and existing.source != SOURCE:
                counts["kept_nepse"] += 1
                continue
            IndexDaily.objects.update_or_create(index=index, date=day, defaults={**values, "source": SOURCE})
            counts["refreshed" if existing else "saved"] += 1
            dates.add(day)
    return {**counts, "since": since.isoformat(), "sessions": sorted(day.isoformat() for day in dates)}
