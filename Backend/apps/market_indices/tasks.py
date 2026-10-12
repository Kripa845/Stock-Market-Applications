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
