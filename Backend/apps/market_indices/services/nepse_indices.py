"""
Daily index history from NEPSE's own feed (nepalstock.com.np, via nepse-data-api).

Uses the same timeout-protected client as market_data.services.live_prices.
``get_index_history("all", start_date=...)`` returns, per index and session:
    businessDate, openIndex, highIndex, lowIndex, closingIndex,
    turnoverValue, turnoverVolume, totalTransaction, absChange, percentageChange
Every session is stored as its own IndexDaily row (update_or_create), so CH and
the turnover / volume / transaction changes come from consecutive real rows.
percentageChange is kept as ``source_change_pct``: NEPSE computes it from unrounded
values, which differs visibly for tiny indices (Mutual Fund ~19.5 points).

While a session is still trading the feed already lists it, as a placeholder:
closingIndex 0, percentageChange -100 and open = high = low (checked 2026-10-16, 12:59).
Such a row is not a session result, so it is never stored; the after-close syncs store it.
"""

import logging
import random
import re
import time
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

import requests
from django.utils import timezone

from apps.market_data.services.live_prices import (
    NPT,
    _nepse_client,
    discard_shared_nepse_client,
    shared_nepse_client,
)
from apps.market_indices.models import IndexDaily, IndexIntradayPoint, MarketIndex

# NEPSE's exchangeIndexId -> MarketIndex.code.  Names differ between feeds
# ("Manufacturing" vs "Manufacturing And Processing"); the id does not.
NEPSE_INDEX_IDS = {
    58: "NEPSE", 57: "SENSITIVE", 62: "FLOAT", 63: "SENSITIVE_FLOAT",
    51: "BANKING", 52: "HOTELS", 53: "OTHERS", 54: "HYDROPOWER", 55: "DEVBANK",
    56: "MANUFACTURE", 59: "NONLIFEINSU", 60: "FINANCE", 61: "TRADING",
    64: "MICROFINANCE", 65: "LIFEINSU", 66: "MUTUAL", 67: "INVESTMENT",
}
DEFAULT_DAYS = 10
# Live index fetch: retry only throttling / blocking / server errors and timeouts,
# backing off 5s then 10s (plus jitter).  Worst case stays well inside the 5-minute schedule.
LIVE_INDEX_MAX_RETRIES = 2
LIVE_INDEX_BACKOFF_SECONDS = 5

logger = logging.getLogger(__name__)


class IndexFeedError(Exception):
    """The NEPSE index feed could not be read or returned nothing usable."""


def _decimal(value):
    try:
        return None if value is None else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _int(value):
    number = _decimal(value)
    return None if number is None else int(number)


def normalise_index_name(text):
    """'Banking SubIndex' / 'BANKING' / 'NEPSE Index' -> 'banking' / 'banking' / 'nepse'."""
    text = re.sub(r"[^a-z0-9]+", "", (text or "").lower())
    for noise in ("subindex", "index"):
        text = text.replace(noise, "")
    return text


def fetch_index_history(since):
    """{index name: [history rows]} for every NEPSE index from ``since`` to today."""
    try:
        data = _nepse_client().get_index_history("all", start_date=since.isoformat())
    except Exception as exc:  # network, auth, timeout or parsing failure inside the library
        raise IndexFeedError(f"NEPSE index feed failed: {exc}") from exc
    if not isinstance(data, dict) or not any(isinstance(rows, list) and rows for rows in data.values()):
        raise IndexFeedError("NEPSE index feed returned no rows")
    return data


def _catalogue():
    catalogue = {index.code: index for index in MarketIndex.objects.all()}
    if not catalogue:
        raise IndexFeedError("MarketIndex catalogue is empty: run `manage.py seed_market_indices`")
    by_name = {}
    for index in catalogue.values():
        for label in (index.code, index.name, index.sector_name):
            by_name[normalise_index_name(label)] = index
    return catalogue, by_name


def _closing_index(value):
    """closingIndex, or None while the session is unfinished (the feed sends 0 until the close)."""
    close = _decimal(value)
    return close if close is not None and close > 0 else None


def iter_history(history, catalogue=None):
    """
    Yield (feed name, MarketIndex or None, date or None, IndexDaily field values) per feed row.
    The values are exactly what sync_index_history stores, so the verifier compares like with like.
    ``close`` is None for a session still in progress (see the module docstring).
    """
    catalogue, by_name = catalogue or _catalogue()
    for name, rows in history.items():
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            index = catalogue.get(NEPSE_INDEX_IDS.get(_int(row.get("exchangeIndexId")))) \
                or by_name.get(normalise_index_name(name))
            try:
                day = date.fromisoformat(str(row.get("businessDate"))[:10])
            except ValueError:
                day = None
            yield str(name), index, day, {
                "open": _decimal(row.get("openIndex")), "high": _decimal(row.get("highIndex")),
                "low": _decimal(row.get("lowIndex")), "close": _closing_index(row.get("closingIndex")),
                "turnover": _decimal(row.get("turnoverValue")), "volume": _int(row.get("turnoverVolume")),
                "transactions": _int(row.get("totalTransaction")),
                "source_change_pct": _decimal(row.get("percentageChange")),
            }


def sync_index_history(since=None, history=None):
    """Store every session of every catalogued index from ``since`` (default: last 10 days)."""
    since = since or (timezone.now().astimezone(NPT).date() - timedelta(days=DEFAULT_DAYS))
    history = history if history is not None else fetch_index_history(since)

    saved, unmatched, dates, in_progress = 0, set(), set(), set()
    # update_or_create on the unique (index, date) pair: re-running never duplicates rows,
    # it overwrites earlier values with NEPSE's latest (e.g. totals revised after the close).
    for name, index, day, values in iter_history(history):
        if index is not None and day is not None and values["close"] is None:
            in_progress.add(day)          # unfinished session: stored by a sync after the close
            continue
        if index is None or day is None:
            unmatched.add(name)
            continue
        IndexDaily.objects.update_or_create(index=index, date=day, defaults={**values, "source": "crawled"})
        saved += 1
        dates.add(day)
    return {
        "since": since.isoformat(),
        "saved": saved,
        "sessions": len(dates),
        "latest": max(dates).isoformat() if dates else None,
        "unmatched": sorted(unmatched),
        "skipped_in_progress": sorted(day.isoformat() for day in in_progress),
    }


def _nepse_time(value):
    """NEPSE's ``generatedTime`` ("2026-10-12T15:16:00.91"), Nepal time."""
    try:
        return datetime.fromisoformat(str(value).strip()).replace(tzinfo=NPT)
    except (TypeError, ValueError):
        return None


def _get_live_index():
    """
    One GET of ``/api/nots/nepse-index`` (after the client's token handshake).

    Not ``Nepse.get_nepse_index``: that swallows every error and returns ``{}``, which
    hides the status code we need to decide whether a retry is worthwhile.
    """
    client, _ = shared_nepse_client()
    try:
        response = client.session.get(f"{client.BASE_URL}/api/nots/nepse-index", headers=client._get_auth_headers())
        response.raise_for_status()
        return response.json()
    except Exception:
        discard_shared_nepse_client()  # the next attempt or run logs in again
        raise


def _retryable(exc):
    """
    429 / 403 / 5xx responses and timeouts are worth another try; so is 401, which is
    how NEPSE rejects an expired token on a reused login (the retry logs in again).
    Anything else is not.
    """
    if isinstance(exc, requests.Timeout):
        return True
    response = getattr(exc, "response", None)
    if isinstance(exc, requests.HTTPError) and response is not None:
        return response.status_code in (401, 403, 429) or response.status_code >= 500
    return False


def fetch_live_index(sleep=time.sleep):
    """NEPSE's live index rows, retried with exponential backoff (at most LIVE_INDEX_MAX_RETRIES)."""
    for attempt in range(LIVE_INDEX_MAX_RETRIES + 1):
        try:
            return _get_live_index()
        except Exception as exc:  # network, auth, timeout or parsing failure
            if attempt == LIVE_INDEX_MAX_RETRIES or not _retryable(exc):
                raise IndexFeedError(f"NEPSE live index failed: {exc}") from exc
            delay = LIVE_INDEX_BACKOFF_SECONDS * 2 ** attempt + random.uniform(0, 1)
            logger.warning("NEPSE live index attempt %d failed (%s); retrying in %.1fs", attempt + 1, exc, delay)
            sleep(delay)


def snapshot_live_index(rows=None):
    """
    Save NEPSE's current main-index values (``/api/nots/nepse-index``) as IndexIntradayPoint rows.

    Run only during the session; NEPSE keeps returning the last values after the close.
    A row is keyed on index + NEPSE's own timestamp: an identical repeat is skipped, and a
    changed value under the same timestamp updates the row.  Returns the three counts.
    """
    if rows is None:
        rows = fetch_live_index()
    if not isinstance(rows, list) or not rows:
        raise IndexFeedError("NEPSE live index returned no rows")

    catalogue = {index.code: index for index in MarketIndex.objects.all()}
    saved = updated = unchanged = 0
    latest = None
    for row in rows:
        if not isinstance(row, dict):
            continue
        index = catalogue.get(NEPSE_INDEX_IDS.get(_int(row.get("id"))))
        value = _decimal(row.get("currentValue"))
        recorded_at = _nepse_time(row.get("generatedTime"))
        if index is None or value is None or recorded_at is None:
            continue
        change = _decimal(row.get("change"))
        fields = {
            "value": value,
            # The feed's "previousClose" / "close" labels are unreliable (after the close
            # "previousClose" equals the current value), so derive it from the change.
            "previous_close": None if change is None else value - change,
            "change": change,
            "change_pct": _decimal(row.get("perChange")),
        }
        if index.code == "NEPSE":
            latest = {"recorded_at": recorded_at.isoformat(), "value": str(value)}
        existing = IndexIntradayPoint.objects.filter(index=index, recorded_at=recorded_at).first()
        if existing is None:
            IndexIntradayPoint.objects.create(index=index, recorded_at=recorded_at, **fields)
            saved += 1
        elif all(getattr(existing, name) == new for name, new in fields.items()):
            unchanged += 1
        else:
            for name, new in fields.items():
                setattr(existing, name, new)
            existing.save(update_fields=list(fields))
            updated += 1
    return {"saved": saved, "updated": updated, "unchanged": unchanged, "nepse": latest}
