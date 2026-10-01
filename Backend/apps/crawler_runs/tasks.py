"""
Celery tasks for crawl-run management.

Architecture note
-----------------
Each CrawlRun has EXACTLY ONE owning Celery task (``run_crawl``).

For news crawls that include multiple spiders (e.g. sharesansar,
merolagani, …) we iterate the spiders *sequentially inside the single
task* rather than dispatching a ``celery.group``.  Using a group would
share one CrawlRun id across N independent workers — each worker would
then race to update ``status``, ``task_id``, ``process_id``, and
``completed_at`` on the same row, producing the "stuck RUNNING" symptom.

One task → one CrawlRun → no races.
"""

import logging

from celery import chain, shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.db import transaction
from django.utils import timezone

from crawlers.runner import (
    FLOORSHEET_SPIDERS,
    MARKET_DATA_SPIDERS,
    NEWS_SPIDERS,
    run_spiders,
)

from .models import CrawlRun

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Time limits
# A news crawl over 6 sources typically takes 20-30 minutes.
# Soft limit fires SoftTimeLimitExceeded so we can tidy up gracefully.
# Hard limit terminates the worker process unconditionally.
# ---------------------------------------------------------------------------
CRAWL_SOFT_TIME_LIMIT = 60 * 55   # 55 minutes  → graceful shutdown
CRAWL_HARD_TIME_LIMIT = 60 * 60   # 60 minutes  → kill worker if still alive


# ---------------------------------------------------------------------------
# Duplicate-run guard (used by scheduled tasks)
# ---------------------------------------------------------------------------

def _has_active_crawl(crawl_type: str) -> bool:
    """
    Return True if there is already a PENDING or RUNNING crawl of this type.

    Wrapped in a transaction + select_for_update to be race-condition safe.
    """
    with transaction.atomic():
        return (
            CrawlRun.objects
            .select_for_update(skip_locked=True)
            .filter(
                crawl_type=crawl_type,
                status__in=[
                    CrawlRun.Status.PENDING,
                    CrawlRun.Status.RUNNING,
                ],
            )
            .exists()
        )


# ---------------------------------------------------------------------------
# Finish helper
# ---------------------------------------------------------------------------

def _finish_run(crawl_run_id, *, success, results=None, logs=""):
    """Write final status + completed_at to the CrawlRun."""
    try:
        crawl_run = CrawlRun.objects.get(pk=crawl_run_id)
    except CrawlRun.DoesNotExist:
        logger.error("CrawlRun #%s not found in _finish_run.", crawl_run_id)
        return

    # Don't overwrite a user-initiated CANCELLED state.
    if crawl_run.status == CrawlRun.Status.CANCELLED:
        return

    results = results or []
    crawl_run.logs = logs

    failed_errors = [
        f"{r.spider_name}: {r.stderr[-2000:]}"
        for r in results
        if not r.ok
    ]
    if failed_errors:
        crawl_run.errors = list(crawl_run.errors or []) + failed_errors

    crawl_run.status = (
        CrawlRun.Status.SUCCESS if success else CrawlRun.Status.FAILED
    )
    crawl_run.completed_at = timezone.now()

    crawl_run.save(
        update_fields=["status", "completed_at", "logs", "errors"]
    )


# ---------------------------------------------------------------------------
# Main crawl task  — ONE task, ONE CrawlRun, sequential spiders
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    soft_time_limit=CRAWL_SOFT_TIME_LIMIT,
    time_limit=CRAWL_HARD_TIME_LIMIT,
    name="apps.crawler_runs.tasks.run_crawl",
)
def run_crawl(self, crawl_run_id, spider_name=None, spider_args=None):
    """
    Execute all spiders belonging to a CrawlRun.

    Guarantees that ``completed_at`` is always written, even when the
    task raises an exception or is killed by the Celery time limit.
    """
    try:
        crawl_run = CrawlRun.objects.get(pk=crawl_run_id)
    except CrawlRun.DoesNotExist:
        logger.error("run_crawl called with unknown CrawlRun #%s.", crawl_run_id)
        return {"error": "CrawlRun not found."}

    # ------------------------------------------------------------------
    # Mark as RUNNING
    # ------------------------------------------------------------------
    crawl_run.task_id = self.request.id
    crawl_run.status = CrawlRun.Status.RUNNING
    if not crawl_run.started_at:
        crawl_run.started_at = timezone.now()
    crawl_run.save(update_fields=["task_id", "status", "started_at"])

    results = []
    success = False

    try:
        # ----------------------------------------------------------------
        # Determine which spiders to run
        # ----------------------------------------------------------------
        if spider_name:
            spider_names = [spider_name]
        elif crawl_run.crawl_type == CrawlRun.CrawlType.NEWS:
            spider_names = list(crawl_run.sources) or list(NEWS_SPIDERS)
        elif crawl_run.crawl_type == CrawlRun.CrawlType.TRADING:
            spider_names = list(MARKET_DATA_SPIDERS)
        elif crawl_run.crawl_type in (
            CrawlRun.CrawlType.FLOORSHEET,
            CrawlRun.CrawlType.FLOORSHEET_SAMPLE,
        ):
            spider_names = list(FLOORSHEET_SPIDERS)
        elif crawl_run.crawl_type == CrawlRun.CrawlType.ALL:
            spider_names = (
                list(NEWS_SPIDERS)
                + list(MARKET_DATA_SPIDERS)
                + list(FLOORSHEET_SPIDERS)
            )
        else:
            raise ValueError(
                f"Unsupported crawl type: {crawl_run.crawl_type}"
            )

        # ----------------------------------------------------------------
        # PID callback — stores the Scrapy process ID so cancellation
        # can kill the right process.  With sequential spiders only the
        # currently running spider's PID is stored; the previous one is
        # already dead by the time the next starts.
        # ----------------------------------------------------------------
        def _save_pid(pid):
            CrawlRun.objects.filter(pk=crawl_run_id).update(process_id=pid)
            logger.info("CrawlRun #%s: Scrapy PID=%s", crawl_run_id, pid)

        # ----------------------------------------------------------------
        # Run spiders sequentially.
        # All spiders share the same crawl_run_id so the pipeline can
        # update article/price/floorsheet counters on the right record.
        # ----------------------------------------------------------------
        results = run_spiders(
            spider_names,
            spider_args={
                "crawl_run_id": crawl_run_id,
                **(spider_args or {}),
            },
            on_process_started=_save_pid,
        )

        # Clear PID once all spiders are done.
        CrawlRun.objects.filter(pk=crawl_run_id).update(process_id=None)

        # Check whether the user cancelled during the run.
        crawl_run.refresh_from_db()
        if crawl_run.status == CrawlRun.Status.CANCELLED:
            logger.info("CrawlRun #%s was cancelled.", crawl_run_id)
            return {"crawl_run_id": crawl_run_id, "cancelled": True}

        success = all(r.ok for r in results)

        # ----------------------------------------------------------------
        # Build logs
        # ----------------------------------------------------------------
        log_lines = [
            f"CrawlRun: #{crawl_run_id}",
            f"Type: {crawl_run.crawl_type}",
            "=" * 48,
        ]
        for r in results:
            outcome = "OK" if r.ok else f"FAILED (exit {r.returncode})"
            log_lines.append(f"{r.spider_name}: {outcome}")
            if r.stdout:
                log_lines.append(f"\nSTDOUT:\n{r.stdout[-3000:]}")
            if r.stderr:
                log_lines.append(f"\nSTDERR:\n{r.stderr[-3000:]}")
            log_lines.append("-" * 48)

        _finish_run(
            crawl_run_id,
            success=success,
            results=results,
            logs="\n".join(log_lines),
        )

        return {
            "crawl_run_id": crawl_run_id,
            "success": success,
            "spiders": spider_names,
        }

    except SoftTimeLimitExceeded:
        # Celery soft time limit: we have a moment to write to the DB.
        logger.warning(
            "CrawlRun #%s hit the soft time limit (%ds).",
            crawl_run_id,
            CRAWL_SOFT_TIME_LIMIT,
        )
        _mark_failed(
            crawl_run_id,
            f"Crawl exceeded the {CRAWL_SOFT_TIME_LIMIT}s soft time limit "
            "and was terminated by Celery.",
        )
        raise  # re-raise so Celery marks the task as REVOKED/terminated

    except Exception as exc:
        logger.exception("CrawlRun #%s failed: %s", crawl_run_id, exc)
        _mark_failed(crawl_run_id, str(exc))
        raise

    finally:
        # ------------------------------------------------------------------
        # SAFETY NET — always clear the PID so the record is never left
        # pointing at a dead process.  _finish_run already sets
        # completed_at; this guard is a second line of defence.
        # ------------------------------------------------------------------
        try:
            CrawlRun.objects.filter(pk=crawl_run_id).update(process_id=None)
        except Exception:
            pass


def _mark_failed(crawl_run_id, reason: str) -> None:
    """
    Unconditionally mark a CrawlRun as FAILED with a reason.

    Safe to call from exception handlers; never raises.
    """
    try:
        updated = CrawlRun.objects.filter(
            pk=crawl_run_id,
            status__in=[
                CrawlRun.Status.PENDING,
                CrawlRun.Status.RUNNING,
            ],
        ).update(
            status=CrawlRun.Status.FAILED,
            completed_at=timezone.now(),
        )
        if updated:
            # Append reason to errors list via a second query.
            run = CrawlRun.objects.get(pk=crawl_run_id)
            run.errors = list(run.errors or []) + [reason]
            run.save(update_fields=["errors"])
    except Exception:
        logger.exception("_mark_failed failed for CrawlRun #%s.", crawl_run_id)


# ---------------------------------------------------------------------------
# Scheduled: hourly news crawl
# ---------------------------------------------------------------------------

@shared_task(name="apps.crawler_runs.tasks.crawl_all_news")
def crawl_all_news():
    """
    Scheduled hourly news crawl.

    Skipped if a news crawl is already PENDING or RUNNING, so a slow
    crawl that overruns the 1-hour window doesn't create a duplicate.
    """
    if _has_active_crawl(CrawlRun.CrawlType.NEWS):
        logger.info(
            "crawl_all_news: skipping — a news crawl is already active."
        )
        return {"skipped": True, "reason": "news crawl already active"}

    with transaction.atomic():
        crawl_run = CrawlRun.objects.create(
            crawl_type=CrawlRun.CrawlType.NEWS,
            source="all",
            target="All tracked companies",
            status=CrawlRun.Status.PENDING,
            sources=list(NEWS_SPIDERS),
        )

    task = run_crawl.apply_async(args=[crawl_run.id])

    crawl_run.task_id = task.id
    crawl_run.status = CrawlRun.Status.RUNNING
    crawl_run.started_at = timezone.now()
    crawl_run.save(update_fields=["task_id", "status", "started_at"])

    logger.info("crawl_all_news: started CrawlRun #%s.", crawl_run.id)
    return {"crawl_run_id": crawl_run.id, "task_id": task.id, "type": "news"}


# ---------------------------------------------------------------------------
# Scheduled: daily prices
# ---------------------------------------------------------------------------

@shared_task(name="apps.crawler_runs.tasks.crawl_daily_prices")
def crawl_daily_prices():
    """
    Scheduled daily trading-data crawl.

    Chains ``rebuild_all_analysis`` afterwards so VWAP / volume baseline /
    pressure are recomputed immediately after fresh prices land.
    """
    if _has_active_crawl(CrawlRun.CrawlType.TRADING):
        logger.info(
            "crawl_daily_prices: skipping — a trading crawl is already active."
        )
        return {"skipped": True, "reason": "trading crawl already active"}

    with transaction.atomic():
        crawl_run = CrawlRun.objects.create(
            crawl_type=CrawlRun.CrawlType.TRADING,
            source="trading_data",
            target="All tracked companies",
            status=CrawlRun.Status.PENDING,
            sources=list(MARKET_DATA_SPIDERS),
        )

    from apps.analysis.tasks import rebuild_all_analysis

    task = chain(
        run_crawl.si(crawl_run.id),
        rebuild_all_analysis.si(),
    ).apply_async()

    crawl_run.task_id = task.id
    crawl_run.status = CrawlRun.Status.RUNNING
    crawl_run.started_at = timezone.now()
    crawl_run.save(update_fields=["task_id", "status", "started_at"])

    logger.info("crawl_daily_prices: started CrawlRun #%s.", crawl_run.id)
    return {"crawl_run_id": crawl_run.id, "task_id": task.id, "type": "trading"}


@shared_task(name="apps.crawler_runs.tasks.crawl_brokers")
def crawl_brokers():
    """Refresh the broker directory with the weekly brokers spider."""
    if _has_active_crawl(CrawlRun.CrawlType.TRADING):
        logger.info("crawl_brokers: skipping because a trading crawl is active.")
        return {"skipped": True, "reason": "trading crawl already active"}

    with transaction.atomic():
        crawl_run = CrawlRun.objects.create(
            crawl_type=CrawlRun.CrawlType.TRADING,
            source="brokers",
            target="Broker directory",
            status=CrawlRun.Status.PENDING,
            sources=["brokers"],
        )

    task = run_crawl.apply_async(
        args=[crawl_run.id],
        kwargs={"spider_name": "brokers"},
    )
    crawl_run.task_id = task.id
    crawl_run.status = CrawlRun.Status.RUNNING
    crawl_run.started_at = timezone.now()
    crawl_run.save(update_fields=["task_id", "status", "started_at"])
    logger.info("crawl_brokers: started CrawlRun #%s.", crawl_run.id)
    return {"crawl_run_id": crawl_run.id, "task_id": task.id, "type": "brokers"}


# ---------------------------------------------------------------------------
# Scheduled: daily floorsheet top-up (latest session only)
# ---------------------------------------------------------------------------

@shared_task(name="apps.crawler_runs.tasks.crawl_floorsheet")
def crawl_floorsheet():
    """Scheduled daily floorsheet crawl (latest session only)."""
    if _has_active_crawl(CrawlRun.CrawlType.FLOORSHEET):
        logger.info(
            "crawl_floorsheet: skipping — a floorsheet crawl is already active."
        )
        return {"skipped": True, "reason": "floorsheet crawl already active"}

    with transaction.atomic():
        crawl_run = CrawlRun.objects.create(
            crawl_type=CrawlRun.CrawlType.FLOORSHEET,
            source="floorsheet",
            target="All tracked companies (latest session)",
            status=CrawlRun.Status.PENDING,
            sources=list(FLOORSHEET_SPIDERS),
            metadata={"mode": "latest"},
        )

    task = run_crawl.apply_async(
        args=[crawl_run.id],
        kwargs={"spider_args": {"mode": "latest"}},
    )

    crawl_run.task_id = task.id
    crawl_run.status = CrawlRun.Status.RUNNING
    crawl_run.started_at = timezone.now()
    crawl_run.save(update_fields=["task_id", "status", "started_at"])

    logger.info("crawl_floorsheet: started CrawlRun #%s.", crawl_run.id)
    return {
        "crawl_run_id": crawl_run.id,
        "task_id": task.id,
        "type": "floorsheet",
        "mode": "latest",
    }


# ---------------------------------------------------------------------------
# Scheduled: weekly floorsheet sample (historical sessions)
# ---------------------------------------------------------------------------

@shared_task(name="apps.crawler_runs.tasks.crawl_floorsheet_sample")
def crawl_floorsheet_sample(sample_offsets=None):
    """Scheduled weekly floorsheet historical sample."""
    if _has_active_crawl(CrawlRun.CrawlType.FLOORSHEET_SAMPLE):
        logger.info(
            "crawl_floorsheet_sample: skipping — already active."
        )
        return {"skipped": True, "reason": "floorsheet_sample crawl already active"}

    with transaction.atomic():
        crawl_run = CrawlRun.objects.create(
            crawl_type=CrawlRun.CrawlType.FLOORSHEET_SAMPLE,
            source="floorsheet",
            target="All tracked companies (historical sample)",
            status=CrawlRun.Status.PENDING,
            sources=list(FLOORSHEET_SPIDERS),
            metadata={"mode": "sample"},
        )

    spider_args = {"mode": "sample"}
    if sample_offsets:
        spider_args["sample_offsets"] = ",".join(
            str(int(o)) for o in sample_offsets
        )

    task = run_crawl.apply_async(
        args=[crawl_run.id],
        kwargs={"spider_args": spider_args},
    )

    crawl_run.task_id = task.id
    crawl_run.status = CrawlRun.Status.RUNNING
    crawl_run.started_at = timezone.now()
    crawl_run.save(update_fields=["task_id", "status", "started_at"])

    logger.info("crawl_floorsheet_sample: started CrawlRun #%s.", crawl_run.id)
    return {
        "crawl_run_id": crawl_run.id,
        "task_id": task.id,
        "type": "floorsheet_sample",
        "mode": "sample",
    }


# ---------------------------------------------------------------------------
# Backwards-compat alias kept for the existing API
# ---------------------------------------------------------------------------

@shared_task(name="apps.crawler_runs.tasks.run_full_crawl_pipeline")
def run_full_crawl_pipeline(crawl_run_id):
    """Alias — calls run_crawl() directly."""
    return run_crawl(crawl_run_id)


# ---------------------------------------------------------------------------
# Periodic stale-run recovery task
# Called by Celery Beat every 2 hours (see settings.CELERY_BEAT_SCHEDULE).
# ---------------------------------------------------------------------------

@shared_task(name="apps.crawler_runs.tasks.recover_stale_crawls")
def recover_stale_crawls(max_age_minutes: int = 90) -> dict:
    """
    Celery-callable version of ``manage.py recover_crawls``.

    Marks RUNNING/PENDING CrawlRuns that are older than
    ``max_age_minutes`` as FAILED.  Runs that are newer than the
    threshold are left untouched.
    """
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(minutes=max_age_minutes)

    stale = list(
        CrawlRun.objects.filter(
            status__in=[CrawlRun.Status.RUNNING, CrawlRun.Status.PENDING],
            started_at__lt=cutoff,
        )
    ) + list(
        CrawlRun.objects.filter(
            status=CrawlRun.Status.PENDING,
            started_at__isnull=True,
            created_at__lt=cutoff,
        )
    )

    recovered = 0
    for run in stale:
        age_mins = round(
            (timezone.now() - (run.started_at or run.created_at)).total_seconds() / 60,
            1,
        )
        errors = list(run.errors or [])
        errors.append(
            f"Auto-recovered by recover_stale_crawls: "
            f"was {run.status} for {age_mins:.1f}m "
            f"(threshold={max_age_minutes}m)."
        )
        CrawlRun.objects.filter(pk=run.pk).update(
            status=CrawlRun.Status.FAILED,
            completed_at=timezone.now(),
            errors=errors,
            process_id=None,
        )
        recovered += 1
        logger.warning(
            "Recovered stale CrawlRun #%s (%s, age=%sm).",
            run.pk,
            run.crawl_type,
            age_mins,
        )

    logger.info(
        "recover_stale_crawls: recovered %d run(s) (threshold=%dm).",
        recovered,
        max_age_minutes,
    )
    return {"recovered": recovered, "max_age_minutes": max_age_minutes}
