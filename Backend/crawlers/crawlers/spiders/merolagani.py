"""
Whole-market daily stock table (every listed stock, one request).

Source default: ShareSansar "today share price" page.
VERIFY BEFORE USE (I could not open the site from the authoring environment):
  1. URL                 -> START_URL (or pass -a url=...)
  2. the table selector  -> TABLE_SELECTOR
  3. where the trade date is shown -> DATE_REGEX (or pass -a date=YYYY-MM-DD)
Column positions are NOT hard-coded: columns are found by their header text
(HEADER_ALIASES), so a re-ordered table still works.  If the date cannot be
determined the spider yields nothing rather than guessing.

Respects the project's ROBOTSTXT_OBEY = True.  Manual run:
    scrapy crawl market_stocks
    scrapy crawl market_stocks -a date=2026-10-09
"""

import re
from datetime import date

import scrapy

from crawlers.items import MarketStockDailyItem

START_URL = "https://www.sharesansar.com/today-share-price"
TABLE_SELECTOR = "table"                      # VERIFY: tighten to the real table, e.g. "table#headFixed"
DATE_REGEX = re.compile(r"(\d{4}-\d{2}-\d{2})")

# canonical field -> header texts (lower-case, punctuation stripped) that mean it
HEADER_ALIASES = {
    "symbol": ("symbol", "scrip", "stock symbol"),
    "close": ("close", "ltp", "closing price"),
    "prev_close": ("prev close", "previous close", "prev. close"),
    "volume": ("vol", "volume", "traded shares", "total traded quantity"),
    "turnover": ("turnover", "total traded value"),
    "transactions": ("trans", "transactions", "no of transactions", "total transactions"),
}


def _clean_header(text):
    return re.sub(r"[^a-z ]+", "", (text or "").lower()).strip()


class MarketStocksSpider(scrapy.Spider):
    name = "market_stocks"
    custom_settings = {
        "ITEM_PIPELINES": {
            "crawlers.pipelines.CrawlRunPipeline": 100,
            "crawlers.market_wide_pipeline.MarketWidePipeline": 450,
        },
    }

    def __init__(self, url=None, date=None, **kwargs):
        super().__init__(**kwargs)
        self.start_url = url or START_URL
        self.forced_date = date

    def start_requests(self):
        yield scrapy.Request(self.start_url, callback=self.parse)

    # ------------------------------------------------------------------

    def parse(self, response):
        trade_date = self._trade_date(response)
        if trade_date is None:
            self.logger.error("Trade date not found on the page; pass -a date=YYYY-MM-DD. Nothing saved.")
            return

        table = response.css(TABLE_SELECTOR)
        if not table:
            self.logger.error("Table %r not found: check TABLE_SELECTOR", TABLE_SELECTOR)
            return
        table = table[0]

        headers = [_clean_header(" ".join(th.css("*::text").getall())) for th in table.css("thead th")]
        columns = self._column_positions(headers)
        missing = [field for field in ("symbol", "close", "volume", "turnover") if field not in columns]
        if missing:
            self.logger.error("Required columns not found %s in headers %s", missing, headers)
            return
        if "transactions" not in columns:
            self.logger.warning("No transactions column: transactions will be stored as NULL")

        count = 0
        for row in table.css("tbody tr"):
            cells = [" ".join(td.css("*::text").getall()).strip() for td in row.css("td")]
            if len(cells) <= max(columns.values()):
                continue

            def cell(field):
                position = columns.get(field)
                return cells[position] if position is not None else None

            symbol = (cell("symbol") or "").strip()
            if not symbol:
                continue
            yield MarketStockDailyItem(
                item_type="market_stock_daily",
                symbol=symbol,
                sector_raw=None,                 # sector comes from the StockSector table
                date=trade_date,
                close=cell("close"),
                prev_close=cell("prev_close"),
                volume=cell("volume"),
                turnover=cell("turnover"),
                transactions=cell("transactions"),
                source="crawled",
            )
            count += 1
        self.logger.info("market_stocks: %s rows for %s", count, trade_date)

    # ------------------------------------------------------------------

    def _trade_date(self, response):
        if self.forced_date:
            return date.fromisoformat(self.forced_date)
        match = DATE_REGEX.search(" ".join(response.css("body *::text").getall()))
        return date.fromisoformat(match.group(1)) if match else None

    @staticmethod
    def _column_positions(headers):
        positions = {}
        for field, aliases in HEADER_ALIASES.items():
            for position, header in enumerate(headers):
                if header in aliases and field not in positions:
                    positions[field] = position
        return positions