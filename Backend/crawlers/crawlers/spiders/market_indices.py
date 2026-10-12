"""
Daily NEPSE index values (4 main + 13 sub-indices): open, high, low, close.

The data source is configurable because it must be confirmed in the browser:
open the site you want to use, DevTools -> Network -> XHR/Fetch, find the call
that returns the index table as JSON, and copy its URL.

    set NEPSE_INDEX_API_URL=https://.../indices          (or: -a url=...)
    scrapy crawl market_indices
    scrapy crawl market_indices -a date=2026-10-09

The JSON may be a list or {"data": [...]} / {"result": [...]}.  Field names are
mapped with FIELD_MAP below (first matching key wins); adjust to the real keys.
Index names are resolved against the MarketIndex catalogue in the pipeline
("Banking SubIndex", "BANKING", "Banking Sub-Index" all match).
Respects ROBOTSTXT_OBEY = True.
"""

import json
import os
from datetime import date, datetime

import scrapy

from crawlers.items import IndexDailyItem

FIELD_MAP = {
    "index_name": ("index", "indexName", "index_name", "name", "symbol", "code"),
    "open": ("open", "openValue", "open_value"),
    "high": ("high", "highValue", "high_value"),
    "low": ("low", "lowValue", "low_value"),
    "close": ("close", "closeValue", "current", "currentValue", "close_value", "value"),
    "date": ("date", "businessDate", "tradeDate", "asOf"),
}
LIST_KEYS = ("data", "result", "results", "indices", "items")
DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%Y-%m-%dT%H:%M:%S")


def _first(record, keys):
    for key in keys:
        if key in record and record[key] not in (None, ""):
            return record[key]
    return None


def _parse_date(value):
    if isinstance(value, str):
        text = value.strip()[:19]
        for fmt in DATE_FORMATS:
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
    return None


class MarketIndicesSpider(scrapy.Spider):
    name = "market_indices"
    custom_settings = {
        "ITEM_PIPELINES": {
            "crawlers.pipelines.CrawlRunPipeline": 100,
            "crawlers.market_wide_pipeline.MarketWidePipeline": 450,
        },
    }

    def __init__(self, url=None, date=None, **kwargs):
        super().__init__(**kwargs)
        self.api_url = url or os.environ.get("NEPSE_INDEX_API_URL", "")
        self.forced_date = date

    def start_requests(self):
        if not self.api_url:
            self.logger.error(
                "No index source configured: set NEPSE_INDEX_API_URL or pass -a url=... "
                "(find the JSON call in DevTools -> Network)."
            )
            return
        yield scrapy.Request(self.api_url, callback=self.parse, headers={"Accept": "application/json"})

    def parse(self, response):
        try:
            payload = json.loads(response.text)
        except ValueError:
            self.logger.error("Response is not JSON: check the URL / use the JSON endpoint")
            return

        records = payload
        if isinstance(payload, dict):
            records = next((payload[key] for key in LIST_KEYS if isinstance(payload.get(key), list)), [])
        if not records:
            self.logger.error("No index records found in the response")
            return

        forced = date.fromisoformat(self.forced_date) if self.forced_date else None
        count = 0
        for record in records:
            if not isinstance(record, dict):
                continue
            trade_date = forced or _parse_date(_first(record, FIELD_MAP["date"]))
            if trade_date is None:
                self.logger.warning("Skipping record without a date: %r", record)
                continue
            yield IndexDailyItem(
                item_type="index_daily",
                index_name=_first(record, FIELD_MAP["index_name"]),
                date=trade_date,
                open=_first(record, FIELD_MAP["open"]),
                high=_first(record, FIELD_MAP["high"]),
                low=_first(record, FIELD_MAP["low"]),
                close=_first(record, FIELD_MAP["close"]),
                source="crawled",
            )
            count += 1
        self.logger.info("market_indices: %s records", count)