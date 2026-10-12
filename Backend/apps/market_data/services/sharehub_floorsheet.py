"""
ShareHub floorsheet (trades with trade times).

``request_floorsheet`` is the ONLY code that talks to ShareHub: URL, User-Agent,
timeout, retries and error mapping live there, so swapping the source means
editing that one function.  Used by the intraday tasks (``sync_day``) and the
``load_sharehub_floorsheet`` command.
"""

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation

from apps.market_data.models import FloorsheetTransaction
from apps.market_data.services.sharehub_time import parse_sharehub_time

logger = logging.getLogger(__name__)

API = "https://sharehubnepal.com/live/api/v2/floorsheet"
USER_AGENT = "personal-stock-project/1.0"
TIMEOUT_SECONDS = 30
PAGE_SIZE = 100          # ShareHub's maximum
PAUSE_SECONDS = 1.0      # pause between requests. Do not lower it.
PAGE_PARAM = "Page"
MAX_PAGES = 300          # safety limit per company-day (30,000 trades)


class ShareHubError(Exception):
    """ShareHub refused or kept failing; the caller should stop, not retry in a loop."""


def request_floorsheet(params):
    """GET the floorsheet API with ``params``; returns its ``data`` dict or raises ShareHubError."""
    url = f"{API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
                body = json.load(resp)
            if not isinstance(body, dict):
                raise ShareHubError(f"Unexpected ShareHub response format for {url}.")
            return body.get("data") or {}
        except urllib.error.HTTPError as e:
            if e.code in (400, 401, 403, 429):
                raise ShareHubError(f"ShareHub refused {url} (HTTP {e.code}). Stop; do not retry in a loop.")
            time.sleep(2 * (attempt + 1))
        except json.JSONDecodeError:
            raise ShareHubError(f"ShareHub did not return JSON for {url}.")
        except (urllib.error.URLError, TimeoutError):
            time.sleep(2 * (attempt + 1))
    raise ShareHubError(f"Could not fetch {url} from ShareHub.")


def fetch_page(day, symbol, page=1):
    # ShareHub's own site sends the date without zero padding (2026-10-6).
    return request_floorsheet({
        "Size": PAGE_SIZE,
        "date": f"{day.year}-{day.month}-{day.day}",
        "symbol": symbol,
        PAGE_PARAM: page,
    })


def fetch_company_day(day, symbol, known_ids=frozenset()):
    """
    Every ShareHub trade for ``symbol`` on ``day``.

    With ``known_ids`` (contract numbers already stored), paging stops at the
    first page made only of known contracts: rows come newest first, so the
    rest are older trades already in the database.  The after-close run passes
    no ``known_ids`` and reads every page, which picks up late rows.
    """
    items = []
    page = 1
    while page <= MAX_PAGES:
        data = fetch_page(day, symbol, page)
        content = data.get("content") or []
        if data.get("pageIndex") not in (None, page):
            raise ShareHubError(f"Asked ShareHub for page {page} but got {data.get('pageIndex')}.")
        items.extend(content)
        if not content or not data.get("hasNext"):
            break
        if known_ids and all(str(item.get("contractId")) in known_ids for item in content):
            break
        page += 1
        time.sleep(PAUSE_SECONDS)
    return items


def build_transactions(company, day, items):
    """ShareHub items -> unsaved FloorsheetTransaction objects, one per contract number."""
    rows = {}
    for item in items:
        if str(item.get("symbol", "")).upper() != company.symbol.upper():
            continue
        if str(item.get("businessDate", ""))[:10] != day.isoformat():
            raise ShareHubError(
                f"Asked ShareHub for {day} but got {item.get('businessDate')}; nothing written."
            )
        try:
            txn_id = str(item["contractId"])
            rows[txn_id] = FloorsheetTransaction(
                company=company,
                date=day,
                transaction_id=txn_id,
                buyer_broker=str(item["buyerMemberId"]),
                seller_broker=str(item["sellerMemberId"]),
                quantity=int(item["contractQuantity"]),
                rate=Decimal(str(item["contractRate"])),
                amount=Decimal(str(item["contractAmount"])),
                trade_time=parse_sharehub_time(item["tradeTime"]),
            )
        except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
            # A renamed or missing field means ShareHub changed its format: skip this company, keep the rest.
            raise ShareHubError(f"Unexpected ShareHub trade format for {company.symbol} {day}: {exc!r}") from exc
    return list(rows.values())


def save_transactions(objs):
    """Bulk upsert on the contract number; existing rows only gain trade_time and amount."""
    FloorsheetTransaction.objects.bulk_create(
        objs,
        batch_size=2000,
        update_conflicts=True,
        unique_fields=["company", "date", "transaction_id"],
        update_fields=["trade_time", "amount"],
    )


def sync_company_day(company, day, incremental=False):
    """Fetch and store one company's ShareHub trades for ``day``. Returns counts."""
    existing = set(
        FloorsheetTransaction.objects
        .filter(company=company, date=day)
        .values_list("transaction_id", flat=True)
    )
    timed = set(
        FloorsheetTransaction.objects
        .filter(company=company, date=day, trade_time__isnull=False)
        .values_list("transaction_id", flat=True)
    )
    items = fetch_company_day(day, company.symbol, known_ids=timed if incremental else frozenset())
    objs = build_transactions(company, day, items)
    if objs:
        save_transactions(objs)
    created = sum(1 for obj in objs if obj.transaction_id not in existing)
    return {"found": len(objs), "created": created, "updated": len(objs) - created}


def sync_day(day, companies, incremental=False):
    """Sync every company in ``companies`` for ``day``; one failing company never stops the rest."""
    summary = {"date": day.isoformat(), "companies": 0, "found": 0, "created": 0, "updated": 0, "errors": []}
    for index, company in enumerate(companies):
        if index:
            time.sleep(PAUSE_SECONDS)
        try:
            counts = sync_company_day(company, day, incremental=incremental)
        except ShareHubError as exc:
            logger.warning("ShareHub sync %s %s failed: %s", company.symbol, day, exc)
            summary["errors"].append(f"{company.symbol}: {exc}")
            continue
        summary["companies"] += 1
        for key in ("found", "created", "updated"):
            summary[key] += counts[key]
    return summary
