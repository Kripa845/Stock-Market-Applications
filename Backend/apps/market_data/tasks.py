"""
Kept for backward compatibility / discoverability from this app.

The actual crawl orchestration (subprocess-based `scrapy crawl`, retry
policy, beat schedule wiring) lives in apps.crawler_runs.tasks, which
is the single place responsible for running every spider in the
project (news, prices, floorsheet). This module just re-exports the
price-crawling task under the name Celery/beat previously referenced
here, so anything already pointing at
`apps.market_data.tasks.crawl_daily_prices` keeps working.

NOTE: the previous version of this file imported a
`crawlers.price.crawler.PriceCrawler` class that does not exist in this
project (trading data is collected via the Scrapy spider
`crawlers/crawlers/spiders/trading_data.py` instead) — that import
would have raised ModuleNotFoundError the first time this task ran.
"""

# from apps.crawler_runs.tasks import crawl_daily_prices  # noqa: F401

import logging

from celery import shared_task

logger = logging.getLogger(__name__)

# update_live_prices circuit breaker: after 3 failed runs in a row, stop calling NEPSE
# for 30 minutes (same policy as market_indices.tasks.snapshot_live_index).
LIVE_PRICES_BREAKER = "update_live_prices"
LIVE_PRICES_BREAKER_THRESHOLD = 3
LIVE_PRICES_BREAKER_PAUSE_SECONDS = 30 * 60


def _breaker_redis():
    from apps.market_data.services.circuit_breaker import broker_redis

    return broker_redis()


# Recent sessions still missing a trade count are retried from NEPSE on every run;
# older gaps are left to `manage.py backfill_price_fields --nepse`.
NEPSE_RECENT_SESSIONS = 10


@shared_task(name="apps.market_data.tasks.derive_price_fields_task")
def derive_price_fields_task():
    """Fill DailyPrice.transactions after a price or floorsheet crawl (floorsheet, then NEPSE)."""
    from apps.market_data.services.live_prices import LivePriceError
    from apps.market_data.services.price_fields import (
        derive_price_fields,
        fill_transactions_from_nepse,
        missing_transaction_dates,
    )

    result = {"floorsheet": derive_price_fields()}
    try:
        result["nepse"] = fill_transactions_from_nepse(missing_transaction_dates(limit=NEPSE_RECENT_SESSIONS))
    except LivePriceError as exc:
        # The floorsheet counts above still stand; the next run retries these dates.
        logger.warning("derive_price_fields_task: %s", exc)
        result["nepse"] = {"skipped": True, "reason": str(exc)}
    logger.info("derive_price_fields_task: %s", result)
    return result


# ---------------------------------------------------------------------------
# Intraday candles
# The live task polls ShareHub for the tracked companies during the session
# and rebuilds today's candles; the after-close task re-reads every page and
# recomputes the whole day, fixing late or out-of-order rows.
# ---------------------------------------------------------------------------

# Accept live runs from the open until a few minutes after the close.
INTRADAY_LIVE_GRACE = 10  # minutes after SESSION_CLOSE


def _sync_and_rebuild_today(task_name, incremental):
    from datetime import datetime, timedelta

    from django.utils import timezone

    from apps.companies.selection import tracked_active_companies
    from apps.market_data.services import intraday_candles
    from apps.market_data.services.sharehub_floorsheet import sync_day
    from apps.market_data.services.trading_days import market_closed_reason

    today = timezone.localdate()
    reason = market_closed_reason(today)
    if reason:
        logger.info("%s: skipping — %s.", task_name, reason)
        return {"skipped": True, "reason": reason}

    if incremental:
        session_open, session_close = intraday_candles.session_bounds(today)
        now = datetime.now(intraday_candles.NPT)
        if not session_open <= now <= session_close + timedelta(minutes=INTRADAY_LIVE_GRACE):
            return {"skipped": True, "reason": "outside market hours"}

    companies = list(tracked_active_companies())
    sync = sync_day(today, companies, incremental=incremental)
    candles = intraday_candles.rebuild_day(today, company_ids=[company.pk for company in companies])
    result = {"sync": sync, "candles": candles}
    logger.info("%s: %s", task_name, result)
    return result


@shared_task(name="apps.market_data.tasks.build_intraday_candles_live")
def build_intraday_candles_live():
    """Every few minutes in the session: new ShareHub trades + today's candles."""
    return _sync_and_rebuild_today("build_intraday_candles_live", incremental=True)


@shared_task(name="apps.market_data.tasks.finalize_intraday_candles")
def finalize_intraday_candles():
    """After the close: full ShareHub re-read and full recompute of today's candles."""
    return _sync_and_rebuild_today("finalize_intraday_candles", incremental=False)


@shared_task(name="apps.market_data.tasks.update_live_prices")
def update_live_prices():
    """Every 2 minutes in the session: NEPSE live LTP for the tracked companies."""
    from apps.market_data.services.live_prices import LivePriceError, sync_live_prices
    from apps.market_data.services.trading_days import market_closed_reason

    reason = market_closed_reason()
    if reason:
        logger.info("update_live_prices: skipping — %s.", reason)
        return {"skipped": True, "reason": reason}
    from apps.market_data.services.circuit_breaker import CircuitBreaker

    breaker = CircuitBreaker(_breaker_redis(), LIVE_PRICES_BREAKER,
                             LIVE_PRICES_BREAKER_THRESHOLD, LIVE_PRICES_BREAKER_PAUSE_SECONDS)
    if breaker.is_open():
        logger.warning("update_live_prices: circuit open, NEPSE not called (%ss left)", breaker.seconds_left())
        return {"skipped": True, "reason": "circuit breaker open"}
    try:
        result = sync_live_prices()
    except LivePriceError as exc:
        logger.warning("update_live_prices: %s; keeping old prices.", exc)
        breaker.record_failure()
        return {"skipped": True, "reason": str(exc)}
    breaker.record_success()
    logger.info("update_live_prices: %s", result)
    return result
