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
"""

import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from apps.market_data.services.live_prices import NPT, _nepse_client
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


def sync_index_history(since=None, history=None):
    """Store every session of every catalogued index from ``since`` (default: last 10 days)."""
    since = since or (timezone.now().astimezone(NPT).date() - timedelta(days=DEFAULT_DAYS))
    history = history if history is not None else fetch_index_history(since)

    catalogue = {index.code: index for index in MarketIndex.objects.all()}
    if not catalogue:
        raise IndexFeedError("MarketIndex catalogue is empty: run `manage.py seed_market_indices`")
    by_name = {}
    for index in catalogue.values():
        for label in (index.code, index.name, index.sector_name):
            by_name[normalise_index_name(label)] = index

    saved, unmatched, dates = 0, set(), set()
    for name, rows in history.items():
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            index = catalogue.get(NEPSE_INDEX_IDS.get(_int(row.get("exchangeIndexId")))) \
                or by_name.get(normalise_index_name(name))
            close = _decimal(row.get("closingIndex"))
            try:
                day = date.fromisoformat(str(row.get("businessDate"))[:10])
            except ValueError:
                day = None
            if index is None or close is None or day is None:
                unmatched.add(str(name))
                continue
            IndexDaily.objects.update_or_create(
                index=index, date=day,
                defaults={
                    "open": _decimal(row.get("openIndex")), "high": _decimal(row.get("highIndex")),
                    "low": _decimal(row.get("lowIndex")), "close": close,
                    "turnover": _decimal(row.get("turnoverValue")), "volume": _int(row.get("turnoverVolume")),
                    "transactions": _int(row.get("totalTransaction")),
                    "source_change_pct": _decimal(row.get("percentageChange")), "source": "crawled",
                },
            )
            saved += 1
            dates.add(day)
    return {
        "since": since.isoformat(),
        "saved": saved,
        "sessions": len(dates),
        "latest": max(dates).isoformat() if dates else None,
        "unmatched": sorted(unmatched),
    }


def _nepse_time(value):
    """NEPSE's ``generatedTime`` ("2026-10-12T15:16:00.91"), Nepal time."""
    try:
        return datetime.fromisoformat(str(value).strip()).replace(tzinfo=NPT)
    except (TypeError, ValueError):
        return None


def snapshot_live_index(rows=None):
    """
    Save NEPSE's current main-index values (``/api/nots/nepse-index``) as IndexIntradayPoint rows.

    Run only during the session; NEPSE keeps returning the last values after the close,
    and re-saving them is harmless (unique on index + NEPSE's own timestamp).
    """
    if rows is None:
        try:
            rows = _nepse_client().get_nepse_index(use_cache=False)
        except Exception as exc:
            raise IndexFeedError(f"NEPSE live index failed: {exc}") from exc
    if not isinstance(rows, list) or not rows:
        raise IndexFeedError("NEPSE live index returned no rows")

    catalogue = {index.code: index for index in MarketIndex.objects.all()}
    saved = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        index = catalogue.get(NEPSE_INDEX_IDS.get(_int(row.get("id"))))
        value = _decimal(row.get("currentValue"))
        recorded_at = _nepse_time(row.get("generatedTime"))
        if index is None or value is None or recorded_at is None:
            continue
        change = _decimal(row.get("change"))
        _, created = IndexIntradayPoint.objects.update_or_create(
            index=index, recorded_at=recorded_at,
            defaults={
                "value": value,
                # The feed's "previousClose" / "close" labels are unreliable (after the close
                # "previousClose" equals the current value), so derive it from the change.
                "previous_close": None if change is None else value - change,
                "change": change,
                "change_pct": _decimal(row.get("perChange")),
            },
        )
        saved += created
    return {"saved": saved}
