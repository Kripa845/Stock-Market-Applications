"""
Live (intraday) prices for the tracked companies from NEPSE's own live-market feed.

Source: nepalstock.com.np ``/api/nots/lives-market`` through the ``nepse-data-api``
package.  The feed lists every security that has traded in the current session
with its last traded price (LTP), NEPSE's previous close and the time of its
last trade.  It is unofficial until the session closes; the official day's
numbers remain the crawled ``DailyPrice`` rows used by services.movers.

Stored on ``Company``:
    ltp                last traded price
    previous_close     NEPSE's previous close (already adjusted by the exchange)
    prices_updated_at  NEPSE's time of that last trade (NOT when we fetched it)

A company that has not traded yet today is absent from the feed, so its stored
values keep their older timestamp; ``live_movers`` lists it as not traded
instead of ranking a stale price.

``LiveFeedStatus.last_successful_fetch`` records when OUR fetch last worked, so a
stopped worker shows up as ``stale`` during market hours instead of old prices
still labelled live.
"""

import logging
import time
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from apps.market_data.models import LiveFeedStatus
from apps.market_data.services.market_stats import tracked_companies
from apps.market_data.services.trading_days import is_market_open

logger = logging.getLogger(__name__)

NPT = ZoneInfo("Asia/Kathmandu")
SOURCE = "NEPSE live market (nepalstock.com.np, via nepse-data-api)"
TWO_PLACES = Decimal("0.01")
TIMEOUT_SECONDS = 15
USER_AGENT = "NepseStockMarketApp/1.0 (personal market-data research; polls every few minutes during NEPSE trading hours only)"
# The task runs every 2 minutes; this allows a few missed runs before warning.
STALE_AFTER = timedelta(minutes=10)


class LivePriceError(Exception):
    """The live feed could not be read or returned nothing usable."""


def _decimal(value):
    try:
        return None if value is None else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _trade_time(value):
    """NEPSE's ``lastUpdatedDateTime`` ("2026-10-12 11:59:17.628619"), Nepal time."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).strip().replace(" ", "T")).replace(tzinfo=NPT)
    except ValueError:
        return None


def _nepse_client():
    """
    A ``nepse_data_api.Nepse`` whose every request has a timeout, our User-Agent and
    TLS certificate verification ON.

    The library sets ``session.verify = False`` and, on import, silences urllib3's
    InsecureRequestWarning for the whole process.  nepalstock.com.np serves a valid
    certificate chain (checked 2026-10-15), so both are undone here.
    """
    import warnings

    import requests
    import urllib3
    from nepse_data_api import Nepse  # imported lazily: it authenticates on construction

    warnings.simplefilter("default", urllib3.exceptions.InsecureRequestWarning)

    class TimeoutSession(requests.Session):
        def request(self, *args, **kwargs):
            kwargs.setdefault("timeout", TIMEOUT_SECONDS)
            return super().request(*args, **kwargs)

    class TimeoutNepse(Nepse):
        # The library sets no timeout, so a hung NEPSE server would block the Celery
        # worker.  Nepse.__init__ builds its session and then calls authenticate(), so
        # swapping the session here covers every request, including the first.
        def authenticate(self):
            if not isinstance(self.session, TimeoutSession):
                session = TimeoutSession()
                session.verify = True  # never inherit the library's verify=False
                session.headers.update(self.session.headers)
                session.headers["User-Agent"] = USER_AGENT
                self.session = session
            return super().authenticate()

    return TimeoutNepse(enable_cache=False)


# One logged-in client per worker process, shared by the frequent polls (live prices
# every 2 minutes, live index every 5), so a run costs one request instead of a login
# plus a request.  Dropped after any failure and after NEPSE_CLIENT_REUSE_SECONDS;
# 0 disables reuse (the test settings do).
_shared_client = {"client": None, "created": 0.0}


def shared_nepse_client():
    """(client, reused): the process's logged-in client, logging in when there is none or it is too old."""
    max_age = getattr(settings, "NEPSE_CLIENT_REUSE_SECONDS", 15 * 60)
    now = time.monotonic()
    client = _shared_client["client"]
    if client is not None and max_age > 0 and now - _shared_client["created"] < max_age:
        return client, True
    client = _nepse_client()
    _shared_client.update(client=client if max_age > 0 else None, created=now)
    return client, False


def discard_shared_nepse_client():
    """Forget the shared client so the next call logs in again (after an error or an empty answer)."""
    _shared_client["client"] = None


def fetch_live_rows():
    """All securities traded so far in the current session, keyed by symbol."""
    while True:
        try:
            client, reused = shared_nepse_client()
            rows = client.get_stocks()
        except Exception as exc:  # network, auth, timeout or parsing failure inside the library
            discard_shared_nepse_client()
            raise LivePriceError(f"NEPSE live feed failed: {exc}") from exc
        # The library swallows request errors (timeouts and an expired token included)
        # and returns [], so empty means "nothing usable"; non-dict rows mean the format changed.
        by_symbol = {
            str(row.get("symbol", "")).upper(): row
            for row in (rows if isinstance(rows, list) else [])
            if isinstance(row, dict) and row.get("symbol")
        }
        if by_symbol:
            return by_symbol
        discard_shared_nepse_client()
        if not reused:
            raise LivePriceError("NEPSE live feed returned no rows")
        logger.info("NEPSE live feed empty with a reused login; logging in again once")


def fetch_day_summary(day, client=None):
    """
    NEPSE's end-of-day row per security for ``day`` (``/api/nots/nepse-data/today-price``),
    keyed by symbol: closePrice, previousDayClosePrice, totalTradedQuantity,
    totalTradedValue, totalTrades, ...  Empty dict for a day NEPSE has no data for.
    Rows for another business date (NEPSE falls back to the latest day) are dropped.
    """
    try:
        rows = (client or _nepse_client()).get_today_price(size=500, date=day.isoformat(), use_cache=False)
    except Exception as exc:
        raise LivePriceError(f"NEPSE day summary failed for {day}: {exc}") from exc
    if isinstance(rows, dict):
        rows = rows.get("content", [])
    return {
        str(row["symbol"]).upper(): row
        for row in (rows if isinstance(rows, list) else [])
        if isinstance(row, dict) and row.get("symbol") and str(row.get("businessDate", ""))[:10] == day.isoformat()
    }


def day_summary_fetcher():
    """
    ``fetch_day_summary`` bound to one lazily created, authenticated client (for many dates).

    NEPSE's token expires during a long run and the library then returns [] instead of
    raising, so an empty day is retried once with a fresh login before it counts as empty.
    """
    client = None

    def login():
        try:
            return _nepse_client()
        except Exception as exc:
            raise LivePriceError(f"NEPSE login failed: {exc}") from exc

    def fetch(day):
        nonlocal client
        if client is None:
            client = login()
        rows = fetch_day_summary(day, client)
        if not rows:
            client = login()
            rows = fetch_day_summary(day, client)
        return rows

    return fetch


def sync_live_prices(companies=None, rows=None):
    """Copy LTP / previous close / last-trade time onto the tracked companies."""
    companies = list(companies if companies is not None else tracked_companies())
    rows = rows if rows is not None else fetch_live_rows()
    changed = []
    for company in companies:
        row = rows.get(company.symbol.upper())
        if row is None:
            continue
        ltp = _decimal(row.get("lastTradedPrice"))
        previous_close = _decimal(row.get("previousClose"))
        traded_at = _trade_time(row.get("lastUpdatedDateTime"))
        if ltp is None or traded_at is None:
            continue
        company.ltp, company.previous_close, company.prices_updated_at = ltp, previous_close, traded_at
        volume = _decimal(row.get("totalTradeQuantity"))
        company.session_volume = None if volume is None else int(volume)
        company.session_turnover = _decimal(row.get("totalTradeValue"))
        changed.append(company)
    if changed:
        type(changed[0]).objects.bulk_update(
            changed, ["ltp", "previous_close", "prices_updated_at", "session_volume", "session_turnover"]
        )
    record_successful_fetch()  # reached only when the fetch and the save both succeeded
    return {
        "feed_rows": len(rows),
        "tracked": len(companies),
        "updated": len(changed),
        "not_in_feed": sorted(c.symbol for c in companies if c.symbol.upper() not in rows),
    }


def record_successful_fetch(moment=None):
    LiveFeedStatus.objects.update_or_create(pk=1, defaults={"last_successful_fetch": moment or timezone.now()})


def last_successful_fetch():
    return LiveFeedStatus.objects.filter(pk=1).values_list("last_successful_fetch", flat=True).first()


def is_stale(last_fetch, now=None):
    """While the market is open, True when no fetch has succeeded in the last STALE_AFTER."""
    now = now or timezone.now()
    if not is_market_open(now):
        return False
    return last_fetch is None or now - last_fetch > STALE_AFTER


def live_movers(company_ids=None, limit=10):
    """Live gainers / losers for the latest session seen in the feed (same rules as services.movers)."""
    companies = list(
        tracked_companies(company_ids)
        .only("id", "symbol", "name", "sector", "logo_url", "ltp", "previous_close", "prices_updated_at")
    )
    stamps = [c.prices_updated_at for c in companies if c.prices_updated_at]
    as_of = max(stamps) if stamps else None
    session_date = as_of.astimezone(NPT).date() if as_of else None

    ranked, not_traded = [], []
    for c in companies:
        traded_today = (
            c.prices_updated_at is not None
            and c.prices_updated_at.astimezone(NPT).date() == session_date
            and c.ltp is not None
            and c.previous_close is not None
            and c.previous_close > 0
        )
        if not traded_today:
            not_traded.append(c.symbol)
            continue
        change = c.ltp - c.previous_close
        ranked.append({
            "company_id": c.id, "symbol": c.symbol, "name": c.name, "sector": c.sector,
            "logo_url": c.logo_url, "close": c.ltp, "prev_close": c.previous_close,
            "change": change.quantize(TWO_PLACES),
            "change_pct": (change * 100 / c.previous_close).quantize(TWO_PLACES),
            "last_traded_at": c.prices_updated_at,
        })

    gainers = sorted((r for r in ranked if r["change_pct"] > 0), key=lambda r: (-r["change_pct"], r["symbol"]))
    losers = sorted((r for r in ranked if r["change_pct"] < 0), key=lambda r: (r["change_pct"], r["symbol"]))
    last_fetch = last_successful_fetch()
    result = {
        "live": True,
        "source": SOURCE,
        "as_of": as_of,
        "last_successful_fetch": last_fetch,
        "stale": is_stale(last_fetch),
        "session_date": session_date,
        "tracked_count": len(companies),
        "gainers_count": len(gainers),
        "losers_count": len(losers),
        "unchanged_count": sum(1 for r in ranked if r["change_pct"] == 0),
        "gainers": gainers[:limit],
        "losers": losers[:limit],
        "not_traded": sorted(not_traded),
    }
    if as_of is None:
        result["reason"] = "No live prices stored yet. They are fetched every 2 minutes during market hours."
        result["action"] = "Run `python manage.py update_live_prices` (works while the NEPSE live feed has data)."
    return result
