"""
Saves DividendItem, CompanyFaceValueItem and CompanyEpsItem rows (spider ``dividends``).

Register in the spider's custom_settings (done in spiders/dividends.py):
    "crawlers.dividend_pipeline.DividendPipeline": 450

The upsert rules live in apps.market_data.services.dividends so they are tested
without Scrapy: (symbol, fiscal_year) for dividends, (symbol, fiscal_year, quarter)
for EPS.  Re-running a crawl updates, never duplicates.  Items with another
item_type pass through untouched.
"""

from crawlers.market_wide_pipeline import _ensure_django, parse_decimal


class DividendPipeline:
    # Scrapy runs on the asyncio reactor, where Django refuses synchronous ORM
    # calls; like MarketWidePipeline, every database call runs in a thread.

    def open_spider(self, spider):
        from twisted.internet.threads import deferToThread

        return deferToThread(self._setup)

    def _setup(self):
        _ensure_django()
        self.counters = {"created": 0, "updated": 0, "incomplete": 0, "skipped": 0, "face_values": 0, "eps": 0}

    def close_spider(self, spider):
        spider.logger.info("DividendPipeline: %s", self.counters)

    def process_item(self, item, spider):
        from twisted.internet.threads import deferToThread

        return deferToThread(self._process_sync, item, spider)

    def _process_sync(self, item, spider):
        from apps.market_data.services import dividends

        kind = item.get("item_type")
        if kind == "dividend":
            self._save_dividend(item, spider, dividends)
        elif kind == "company_face_value":
            self.counters["face_values"] += dividends.save_face_value(item.get("symbol"), parse_decimal(item.get("face_value")))
        elif kind == "company_eps":
            saved = dividends.save_eps(item.get("symbol"), item.get("fiscal_year"), item.get("quarter"),
                                       parse_decimal(item.get("eps")), source=item.get("source") or "Merolagani")
            self.counters["eps" if saved else "skipped"] += 1
        return item

    def _save_dividend(self, item, spider, dividends):
        data = {
            **dict(item),
            "bonus_pct": parse_decimal(item.get("bonus_pct")),
            "cash_pct": parse_decimal(item.get("cash_pct")),
        }
        outcome = dividends.upsert_dividend(data, source=item.get("source") or spider.source)
        self.counters[outcome] += 1
        if outcome != "skipped" and not (item.get("symbol") and dividends.normalise_fiscal_year(item.get("fiscal_year"))):
            self.counters["incomplete"] += 1
            spider.logger.warning("Dividend row without symbol / fiscal year (stored, marked): %r", dict(item))
