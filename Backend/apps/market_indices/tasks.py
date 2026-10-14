"""Celery task: crawl whole-market stock rows + index values after the close."""

import logging
import subprocess
import sys
from pathlib import Path

from celery import shared_task
from django.utils import timezone

from apps.market_data.services.trading_days import market_closed_reason

logger = logging.getLogger(__name__)

# Backend/crawlers is the Scrapy project root (contains scrapy.cfg).
CRAWLERS_DIR = Path(__file__).resolve().parents[2] / "crawlers"
SPIDERS = ("market_stocks", "market_indices")
SPIDER_TIMEOUT_SECONDS = 600

# snapshot_live_index circuit breaker: after 3 failed runs in a row, stop calling NEPSE
# for 30 minutes.  Kept in Redis (the Celery broker), not Django's per-process cache,
# so every worker process sees the same count.
BREAKER_THRESHOLD = 3
BREAKER_PAUSE_SECONDS = 30 * 60
BREAKER_FAILURES_KEY = "snapshot_live_index:consecutive_failures"
BREAKER_OPEN_KEY = "snapshot_live_index:paused"


def _breaker():
    import redis
    from django.conf import settings

    return redis.Redis.from_url(settings.CELERY_BROKER_URL)


def _run_spider(name):
    """Run one spider as a subprocess (same approach as crawler_runs.runner)."""
    result = subprocess.run(
        [sys.executable, "-m", "scrapy", "crawl", name],
        cwd=CRAWLERS_DIR,
        capture_output=True,
        text=True,
        timeout=SPIDER_TIMEOUT_SECONDS,
    )
    ok = result.returncode == 0
    if not ok:
        logger.error("spider %s failed (code %s): %s", name, result.returncode, result.stderr[-2000:])
    return {"spider": name, "ok": ok, "returncode": result.returncode}


@shared_task(name="apps.market_indices.tasks.crawl_market_wide")
def crawl_market_wide():
    """Runs on trading days only; re-running is safe (update_or_create)."""
    reason = market_closed_reason()
    if reason:
        return {"skipped": True, "reason": reason}

    results = []
    for spider in SPIDERS:
        try:
            results.append(_run_spider(spider))
        except subprocess.TimeoutExpired:
            logger.error("spider %s timed out", spider)
            results.append({"spider": spider, "ok": False, "returncode": "timeout"})

    # Responses are cached for 60s; drop them so the page shows the new session.
    from django.core.cache import cache
    cache.delete_many([
        "mi:indices", "mi:sub-indices", "mi:analysis", "mi:tracked-sectors",
        "mi:top:turnover", "mi:top:volume", "mi:top:transactions",
    ])
    return {"skipped": False, "ran_at": timezone.now().isoformat(), "results": results}

@shared_task(name="apps.market_indices.tasks.sync_indices_from_nepse")
def sync_indices_from_nepse():
    """After the close: the last 10 days of NEPSE main + sub-index history from NEPSE's own feed."""
    from django.core.cache import cache

    from apps.market_indices.services.nepse_indices import IndexFeedError, sync_index_history

    reason = market_closed_reason()
    if reason:
        return {"skipped": True, "reason": reason}
    try:
        result = sync_index_history()
    except IndexFeedError as exc:
        logger.warning("sync_indices_from_nepse: %s", exc)
        return {"skipped": True, "reason": str(exc)}
    cache.delete_many(["mi:indices:latest", "mi:sub-indices:latest"])
    logger.info("sync_indices_from_nepse: %s", result)
    return result


@shared_task(name="apps.market_indices.tasks.snapshot_live_index")
def snapshot_live_index_task():
    """Every 5 minutes in the session: NEPSE's live index values (1D chart and overview header)."""
    from apps.market_indices.services.nepse_indices import IndexFeedError, snapshot_live_index

    reason = market_closed_reason()
    if reason:
        logger.info("snapshot_live_index: market closed (%s), nothing fetched", reason)
        return {"skipped": True, "reason": reason}
    breaker = _breaker()
    if breaker.exists(BREAKER_OPEN_KEY):
        logger.warning("snapshot_live_index: circuit open, NEPSE not called (%ss left)", breaker.ttl(BREAKER_OPEN_KEY))
        return {"skipped": True, "reason": "circuit breaker open"}
    try:
        result = snapshot_live_index()
    except IndexFeedError as exc:
        logger.warning("snapshot_live_index: fetch failed, no ticks saved: %s", exc)
        if breaker.incr(BREAKER_FAILURES_KEY) >= BREAKER_THRESHOLD:
            breaker.set(BREAKER_OPEN_KEY, 1, ex=BREAKER_PAUSE_SECONDS)
            breaker.delete(BREAKER_FAILURES_KEY)
            logger.error("snapshot_live_index: %d failures in a row, pausing for %d minutes",
                         BREAKER_THRESHOLD, BREAKER_PAUSE_SECONDS // 60)
        return {"skipped": True, "reason": str(exc)}
    breaker.delete(BREAKER_FAILURES_KEY)
    nepse = result.get("nepse") or {}
    logger.info(
        "snapshot_live_index: NEPSE %s at %s | %d new, %d updated, %d unchanged rows",
        nepse.get("value", "?"), nepse.get("recorded_at", "?"),
        result["saved"], result["updated"], result["unchanged"],
    )
    return result
