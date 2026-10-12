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
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from apps.market_data.services.live_prices import NPT, _nepse_client
from apps.market_indices.models import IndexDaily, MarketIndex

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
