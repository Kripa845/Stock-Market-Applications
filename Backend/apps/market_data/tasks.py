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


@shared_task(name="apps.market_data.tasks.derive_price_fields_task")
def derive_price_fields_task():
    """Fill DailyPrice ltp / prev_close / transactions after a price or floorsheet crawl."""
    from apps.market_data.services.price_fields import derive_price_fields

    result = derive_price_fields()
    logger.info("derive_price_fields_task: %s", result)
    return result
