import logging

from celery import shared_task
from django.utils import timezone

from crawlers.runner import (
    FLOORSHEET_SPIDERS,
    MARKET_DATA_SPIDERS,
    NEWS_SPIDERS,
    run_spiders,
)

from .models import CrawlRun


logger = logging.getLogger(__name__)


# ============================================================
# HELPER: FINISH CRAWL RUN
# ============================================================

def _finish_run(
    crawl_run_id,
    *,
    success,
    results=None,
    logs="",
):
    crawl_run = CrawlRun.objects.get(
        pk=crawl_run_id
    )

    results = results or []

    crawl_run.logs = logs

    # Collect failed spider errors
    failed = []

    for result in results:
        if not result.ok:
            failed.append(
                f"{result.spider_name}: {result.stderr}"
            )

    if failed:
        crawl_run.errors = [
            *crawl_run.errors,
            *failed,
        ]

    crawl_run.status = (
        CrawlRun.Status.SUCCESS
        if success
        else CrawlRun.Status.FAILED
    )

    crawl_run.completed_at = timezone.now()

    crawl_run.save(
        update_fields=[
            "status",
            "completed_at",
            "logs",
            "errors",
        ]
    )


# ============================================================
# MAIN CRAWL TASK
# ============================================================

@shared_task(bind=True)
def run_crawl(self, crawl_run_id, spider_name=None, spider_args=None):

    crawl_run = CrawlRun.objects.get(
        pk=crawl_run_id
    )

    crawl_run.task_id = self.request.id
    crawl_run.status = CrawlRun.Status.RUNNING

    if not crawl_run.started_at:
        crawl_run.started_at = timezone.now()

    crawl_run.save(
        update_fields=[
            "task_id",
            "status",
            "started_at",
        ]
    )

    try:

        # ------------------------------------------------
        # Determine spiders
        # ------------------------------------------------

        if spider_name:
            spider_names = [spider_name]

        elif crawl_run.crawl_type == CrawlRun.CrawlType.NEWS:

            spider_names = crawl_run.sources

        elif crawl_run.crawl_type == CrawlRun.CrawlType.TRADING:

            spider_names = MARKET_DATA_SPIDERS

        elif crawl_run.crawl_type == CrawlRun.CrawlType.FLOORSHEET:

            spider_names = FLOORSHEET_SPIDERS

        elif crawl_run.crawl_type == CrawlRun.CrawlType.ALL:

            spider_names = (
                NEWS_SPIDERS
                + MARKET_DATA_SPIDERS
                + FLOORSHEET_SPIDERS
            )

        else:
            raise ValueError(
                f"Unsupported crawl type: "
                f"{crawl_run.crawl_type}"
            )

        # ------------------------------------------------
        # Save Scrapy PID
        # ------------------------------------------------

        def save_process_id(pid):

            CrawlRun.objects.filter(
                pk=crawl_run_id
            ).update(
                process_id=pid
            )

            logger.info(
                "CrawlRun %s started Scrapy PID %s",
                crawl_run_id,
                pid,
            )

        # ------------------------------------------------
        # Run spiders
        # ------------------------------------------------

        results = run_spiders(
            spider_names,
            spider_args={
                "crawl_run_id": crawl_run_id,
                **(spider_args or {}),
            },
            on_process_started=save_process_id,
        )

        # ------------------------------------------------
        # Clear PID
        # ------------------------------------------------

        CrawlRun.objects.filter(
            pk=crawl_run_id
        ).update(
            process_id=None
        )

        # ------------------------------------------------
        # Check cancellation
        # ------------------------------------------------

        crawl_run.refresh_from_db()

        if crawl_run.status == CrawlRun.Status.CANCELLED:

            logger.info(
                "CrawlRun %s was cancelled.",
                crawl_run_id,
            )

            return {
                "crawl_run_id": crawl_run_id,
                "success": False,
                "cancelled": True,
            }

        # ------------------------------------------------
        # Determine success
        # ------------------------------------------------

        success = all(
            result.ok
            for result in results
        )

        # ------------------------------------------------
        # Build logs
        # ------------------------------------------------

        logs = []

        logs.append(
            f"Crawl Run: {crawl_run_id}"
        )

        logs.append(
            f"Crawl Type: {crawl_run.crawl_type}"
        )

        logs.append(
            "========================================"
        )

        for result in results:

            logs.append(
                f"{result.spider_name}: "
                f"{'SUCCESS' if result.ok else 'FAILED'}"
            )

            if result.stdout:
                logs.append(
                    f"\nSTDOUT:\n{result.stdout}"
                )

            if result.stderr:
                logs.append(
                    f"\nSTDERR:\n{result.stderr}"
                )

            logs.append(
                "----------------------------------------"
            )

        # ------------------------------------------------
        # Finish
        # ------------------------------------------------

        _finish_run(
            crawl_run_id,
            success=success,
            results=results,
            logs="\n".join(logs),
        )

        return {
            "crawl_run_id": crawl_run_id,
            "success": success,
            "spiders": list(spider_names),
        }

    except Exception as exc:

        logger.exception(
            "Crawl %s failed.",
            crawl_run_id,
        )

        crawl_run = CrawlRun.objects.get(
            pk=crawl_run_id
        )

        # Don't overwrite CANCELLED
        if crawl_run.status == CrawlRun.Status.CANCELLED:
            return {
                "crawl_run_id": crawl_run_id,
                "success": False,
                "cancelled": True,
            }

        crawl_run.status = CrawlRun.Status.FAILED
        crawl_run.completed_at = timezone.now()

        crawl_run.errors = [
            *crawl_run.errors,
            str(exc),
        ]

        crawl_run.process_id = None

        crawl_run.save(
            update_fields=[
                "status",
                "completed_at",
                "errors",
                "process_id",
            ]
        )

        raise

# ============================================================
# SCHEDULED NEWS CRAWL
# ============================================================

@shared_task
def crawl_all_news():
    """
    Automatically crawl all news sources.

    Creates a CrawlRun and then dispatches run_crawl().
    """

    crawl_run = CrawlRun.objects.create(
        crawl_type=CrawlRun.CrawlType.NEWS,
        source="all",
        target="All tracked companies",
        status=CrawlRun.Status.PENDING,
        sources=list(NEWS_SPIDERS),
    )

    task = run_crawl.delay(
        crawl_run.id
    )

    crawl_run.task_id = task.id
    crawl_run.status = CrawlRun.Status.RUNNING
    crawl_run.started_at = timezone.now()

    crawl_run.save(
        update_fields=[
            "task_id",
            "status",
            "started_at",
        ]
    )

    return {
        "crawl_run_id": crawl_run.id,
        "task_id": task.id,
        "type": "news",
    }


# ============================================================
# SCHEDULED TRADING DATA CRAWL
# ============================================================

@shared_task
def crawl_daily_prices():
    """
    Automatically crawl daily trading data.
    """

    crawl_run = CrawlRun.objects.create(
        crawl_type=CrawlRun.CrawlType.TRADING,
        source="trading_data",
        target="All tracked companies",
        status=CrawlRun.Status.PENDING,
        sources=list(MARKET_DATA_SPIDERS),
    )

    task = run_crawl.delay(
        crawl_run.id
    )

    crawl_run.task_id = task.id
    crawl_run.status = CrawlRun.Status.RUNNING
    crawl_run.started_at = timezone.now()

    crawl_run.save(
        update_fields=[
            "task_id",
            "status",
            "started_at",
        ]
    )

    return {
        "crawl_run_id": crawl_run.id,
        "task_id": task.id,
        "type": "trading",
    }


# ============================================================
# SCHEDULED FLOORSHEET CRAWL
# ============================================================

@shared_task
def crawl_floorsheet():
    """
    Automatically crawl floorsheet data.
    """

    crawl_run = CrawlRun.objects.create(
        crawl_type=CrawlRun.CrawlType.FLOORSHEET,
        source="floorsheet",
        target="All tracked companies",
        status=CrawlRun.Status.PENDING,
        sources=list(FLOORSHEET_SPIDERS),
    )

    task = run_crawl.delay(
        crawl_run.id
    )

    crawl_run.task_id = task.id
    crawl_run.status = CrawlRun.Status.RUNNING
    crawl_run.started_at = timezone.now()

    crawl_run.save(
        update_fields=[
            "task_id",
            "status",
            "started_at",
        ]
    )

    return {
        "crawl_run_id": crawl_run.id,
        "task_id": task.id,
        "type": "floorsheet",
    }


# ============================================================
# FULL CRAWL
# ============================================================

@shared_task
def run_full_crawl_pipeline(crawl_run_id):
    """
    Kept for compatibility with the existing API.

    The actual crawling is handled by run_crawl().
    """

    return run_crawl(
        crawl_run_id
    )