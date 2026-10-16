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
    from apps.market_data.services.circuit_breaker import broker_redis

    return broker_redis()


def _run_spider(name, crawl_run_id):
    """Run one spider as a subprocess (same approach as crawler_runs.runner)."""
    result = subprocess.run(
        # crawl_run_id: CrawlRunPipeline reuses this run instead of creating a
        # default (news-typed) one that would block the hourly news crawl.
        [sys.executable, "-m", "scrapy", "crawl", name, "-a", f"crawl_run_id={crawl_run_id}"],
        cwd=CRAWLERS_DIR,
        capture_output=True,
        text=True,
        timeout=SPIDER_TIMEOUT_SECONDS,
    )
    ok = result.returncode == 0
    if not ok:
        logger.error("spider %s failed (code %s): %s", name, result.returncode, result.stderr[-2000:])
    return {"spider": name, "ok": ok, "returncode": result.returncode, "stderr": result.stderr[-2000:]}


@shared_task(name="apps.market_indices.tasks.crawl_market_wide")
def crawl_market_wide():
    """Runs on trading days only; re-running is safe (update_or_create)."""
    from apps.crawler_runs.models import CrawlRun

    reason = market_closed_reason()
    if reason:
        return {"skipped": True, "reason": reason}

    crawl_run = CrawlRun.objects.create(
        crawl_type=CrawlRun.CrawlType.MARKET_WIDE,
        source="market_wide",
        target="All listed stocks + indices",
        status=CrawlRun.Status.RUNNING,
        started_at=timezone.now(),
        sources=list(SPIDERS),
    )

    results = []
    try:
        for spider in SPIDERS:
            try:
                results.append(_run_spider(spider, crawl_run.id))
            except subprocess.TimeoutExpired:
                logger.error("spider %s timed out", spider)
                results.append({"spider": spider, "ok": False, "returncode": "timeout", "stderr": ""})
    finally:
        # Always close the run here: the pipeline marks it SUCCESS per spider,
        # but a crashed or timed-out spider would otherwise leave it RUNNING.
        failed = [r for r in results if not r["ok"]]
        crawl_run.refresh_from_db()
        crawl_run.status = (
            CrawlRun.Status.FAILED if failed or len(results) < len(SPIDERS) else CrawlRun.Status.SUCCESS
        )
        crawl_run.completed_at = timezone.now()
        crawl_run.errors = [f"{r['spider']} (exit {r['returncode']}): {r['stderr']}" for r in failed]
        crawl_run.save(update_fields=["status", "completed_at", "errors"])
    results = [{key: value for key, value in r.items() if key != "stderr"} for r in results]

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
    from apps.market_data.services.circuit_breaker import CircuitBreaker

    breaker = CircuitBreaker(_breaker(), "snapshot_live_index", BREAKER_THRESHOLD, BREAKER_PAUSE_SECONDS)
    if breaker.is_open():
        logger.warning("snapshot_live_index: circuit open, NEPSE not called (%ss left)", breaker.seconds_left())
        return {"skipped": True, "reason": "circuit breaker open"}
    try:
        result = snapshot_live_index()
    except IndexFeedError as exc:
        logger.warning("snapshot_live_index: fetch failed, no ticks saved: %s", exc)
        breaker.record_failure()
        return {"skipped": True, "reason": str(exc)}
    breaker.record_success()
    nepse = result.get("nepse") or {}
    logger.info(
        "snapshot_live_index: NEPSE %s at %s | %d new, %d updated, %d unchanged rows",
        nepse.get("value", "?"), nepse.get("recorded_at", "?"),
        result["saved"], result["updated"], result["unchanged"],
    )
    return result


@shared_task(name="apps.market_indices.tasks.verify_index_replication")
def verify_index_replication():
    """
    After the close: store today's company snapshot for the calibrated indices, then
    compare each reproduced value with NEPSE's published close for the same day
    (IndexCheck; |diff| > 0.5 is flagged, share changes flag a recalibration).
    """
    from apps.market_data.services.live_prices import NPT
    from apps.market_indices.models import IndexCalibration, IndexDaily
    from apps.market_indices.services import index_replication as rep
    from apps.market_indices.services.nepse_indices import IndexFeedError, sync_index_history

    reason = market_closed_reason()
    if reason:
        return {"skipped": True, "reason": reason}
    today = timezone.now().astimezone(NPT).date()
    codes = sorted(set(IndexCalibration.objects.values_list("index__code", flat=True)))
    if not codes:
        return {"skipped": True, "reason": "no index calibrated yet (manage.py replicate_index calibrate ...)"}
    if not IndexDaily.objects.filter(date=today).exists():
        try:
            sync_index_history(today)
        except IndexFeedError as exc:
            logger.error("verify_index_replication: published closes for %s unavailable: %s", today, exc)
            return {"skipped": True, "reason": str(exc)}
    try:
        snapshot = rep.snapshot_company_daily(today, sectors=rep.sectors_for(codes))
    except rep.ReplicationError as exc:
        logger.error("verify_index_replication: company snapshot failed, nothing verified: %s", exc)
        return {"skipped": True, "reason": str(exc)}
    checks = rep.verify_day(today, codes)
    summary = [
        check if isinstance(check, dict) else
        {"index": check.index.code, "computed": str(check.computed), "published": str(check.published),
         "diff": str(check.diff), "flagged": check.flagged, "needs_recalibration": check.needs_recalibration}
        for check in checks
    ]
    logger.info("verify_index_replication %s: %s", today, summary)
    return {"skipped": False, "date": today.isoformat(), "snapshot": snapshot, "checks": summary}
