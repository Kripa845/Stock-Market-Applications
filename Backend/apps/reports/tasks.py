import logging

from celery import shared_task

from apps.reports.services import nepsetrading

logger = logging.getLogger(__name__)


@shared_task(name="apps.reports.tasks.crawl_quarterly_reports")
def crawl_quarterly_reports():
    """Daily: latest quarterly reports of the tracked companies (nepsetrading.com)."""
    results = nepsetrading.crawl()
    summary = {r.sector: r.error or len(r.symbols) for r in results}
    logger.info("crawl_quarterly_reports: %s", summary)
    return summary
