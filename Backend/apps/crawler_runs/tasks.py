import logging

from celery import shared_task

from crawlers.runner import (
    FLOORSHEET_SPIDERS,
    MARKET_DATA_SPIDERS,
    NEWS_SPIDERS,
    run_spider,
    run_spiders,
)

logger = logging.getLogger(__name__)


def _log_results(label, results):
    ok = [r.spider_name for r in results if r.ok]
    failed = [r for r in results if not r.ok]

    logger.info(
        "%s finished | ok=%s | failed=%s",
        label,
        ok,
        [r.spider_name for r in failed],
    )

    for result in failed:
        logger.error(
            "%s: spider '%s' exited with code %s\nSTDERR:\n%s",
            label,
            result.spider_name,
            result.returncode,
            result.stderr,
        )

    return {
        "ok": ok,
        "failed": [r.spider_name for r in failed],
    }


# ======================================================================
# INDIVIDUAL SPIDER TASKS
#
# Exposed individually (not just as part of the "crawl everything"
# tasks below) so a single portal can be re-run on demand from the
# admin "trigger crawl" screen (Section 5 / POST /api/admin/crawl-runs)
# without re-running the whole pipeline.
# ======================================================================

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=2,
)
def crawl_single_spider(self, spider_name, spider_args=None):
    """
    Generic single-spider task. `POST /api/admin/crawl-runs` can call
    this with any spider name from crawlers.runner.ALL_SPIDERS instead
    of needing one hard-coded task per portal.
    """

    result = run_spider(spider_name, spider_args=spider_args)

    if not result.ok:
        logger.error(
            "Spider '%s' failed (code=%s):\n%s",
            spider_name,
            result.returncode,
            result.stderr,
        )

    return {
        "spider": spider_name,
        "ok": result.ok,
        "returncode": result.returncode,
    }


# ======================================================================
# GROUPED / SCHEDULED TASKS
#
# These are the ones wired into CELERY_BEAT_SCHEDULE (config/settings.py)
# so the dataset stays current without anyone running a script by hand.
# ======================================================================

@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=2,
)
def crawl_all_news():
    """
    Runs every configured news spider (ShareSansar, MeroLagani,
    Bizmandu, NepseAlpha, ArthaKhabar, FiscalNepal).

    Scheduled every few hours (see CELERY_BEAT_SCHEDULE) so freshly
    published articles get categorized and analyzed the same day they
    come out, rather than only once per day.
    """

    results = run_spiders(NEWS_SPIDERS)
    return _log_results("crawl_all_news", results)


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=2,
)
def crawl_daily_prices():
    """
    Runs the OHLCV trading-data spider(s) for every active/tracked
    company. Scheduled once a day, shortly after NEPSE's market close
    (Sun-Thu ~15:00 NPT), since intraday values aren't final until
    then.
    """

    results = run_spiders(MARKET_DATA_SPIDERS)
    return _log_results("crawl_daily_prices", results)


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=2,
)
def crawl_floorsheet():
    """
    Runs the floorsheet spider(s) for a sample of trading days per
    company (feeds the buyer/seller broker behavior analysis).
    Scheduled once a day, same window as crawl_daily_prices.
    """

    results = run_spiders(FLOORSHEET_SPIDERS)
    return _log_results("crawl_floorsheet", results)


@shared_task
def run_full_crawl_pipeline():
    """
    Orchestrator: news -> prices -> floorsheet, run one after another
    (not in parallel) so a slow/rate-limited news crawl doesn't compete
    for the same outbound bandwidth/IP as the price crawl that runs
    right after market close.

    This is the task Celery beat calls for the once-a-day "full
    refresh" entry; the more frequent `crawl_all_news` entry keeps news
    current between full refreshes.
    """

    news_summary = _log_results("crawl_all_news", run_spiders(NEWS_SPIDERS))
    prices_summary = _log_results(
        "crawl_daily_prices", run_spiders(MARKET_DATA_SPIDERS)
    )
    floorsheet_summary = _log_results(
        "crawl_floorsheet", run_spiders(FLOORSHEET_SPIDERS)
    )

    return {
        "news": news_summary,
        "prices": prices_summary,
        "floorsheet": floorsheet_summary,
    }
