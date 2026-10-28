"""
Saves IpoIssueItem rows (spider ``ipo_issues``).

Register in the spider's custom_settings (done in spiders/ipo_issues.py):
    "crawlers.ipo_pipeline.IpoIssuePipeline": 450

The upsert lives in apps.reports.services.ipo_issues so it is tested without Scrapy.
"""

from crawlers.market_wide_pipeline import _ensure_django, parse_decimal


class IpoIssuePipeline:
    # Scrapy runs on the asyncio reactor, where Django refuses synchronous ORM calls,
    # so every database call runs in a thread (as in DividendPipeline).

    def open_spider(self, spider):
        from twisted.internet.threads import deferToThread

        return deferToThread(self._setup)

    def _setup(self):
        _ensure_django()
        self.counters = {"created": 0, "updated": 0, "skipped": 0}

    def close_spider(self, spider):
        spider.logger.info("IpoIssuePipeline: %s", self.counters)

    def process_item(self, item, spider):
        from twisted.internet.threads import deferToThread

        return deferToThread(self._process_sync, item, spider)

    def _process_sync(self, item, spider):
        from apps.reports.services import ipo_issues

        data = {**dict(item), "price": parse_decimal(item.get("price"))}
        outcome = ipo_issues.upsert_issue(data, source=item.get("source") or spider.source)
        self.counters[outcome] += 1
        if outcome == "skipped":
            spider.logger.warning("Issue without type / key, not stored: %r", dict(item))
        return item
