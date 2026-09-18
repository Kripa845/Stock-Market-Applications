
import json
import os
import re
import sys
from pathlib import Path

import django
import scrapy
from asgiref.sync import sync_to_async


# ============================================================
# DJANGO SETUP
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[3]

sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings",
)

django.setup()


from apps.companies.models import Company
from crawlers.items import DailyTradingDataItem


# ============================================================
# SPIDER
# ============================================================

class TradingDataSpider(scrapy.Spider):
    """
    Collects daily OHLCV + turnover price history from ShareSansar
    for every active company in the database.

    Rolling window design
    ---------------------
    The spider requests the most recent LOOKBACK_ROWS rows from the
    website's DataTables price-history endpoint.  Because NEPSE trades
    ~22 days per calendar month, using 50 rows guarantees we always
    cover at least a full 31-day rolling window (≈2+ months of buffer).

    On every scheduled run the pipeline uses ``update_or_create`` so:
    - New trading dates are inserted.
    - Already-stored dates are updated (idempotent).
    - No historical records are ever deleted.

    Pagination
    ----------
    If the API returns a ``recordsTotal`` larger than the current
    ``start + LOOKBACK_ROWS`` offset the spider automatically fetches
    the next page.  This ensures we never miss data even if the website
    changes its row limit.
    """

    name = "trading_data"

    allowed_domains = [
        "sharesansar.com",
        "www.sharesansar.com",
    ]

    SOURCE = "ShareSansar"

    PRICE_HISTORY_URL = (
        "https://www.sharesansar.com/"
        "company-price-history"
    )

    # Number of rows requested per page.
    # 50 rows ≈ 2+ months of trading days which guarantees the
    # 31-day rolling window is always fully covered.
    LOOKBACK_ROWS = 50

    custom_settings = {
        "ROBOTSTXT_OBEY": True,

        "CONCURRENT_REQUESTS": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,

        "DOWNLOAD_DELAY": 2,

        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 2,
        "AUTOTHROTTLE_MAX_DELAY": 10,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 0.5,

        # Required: the price-history endpoint uses session cookies.
        "COOKIES_ENABLED": True,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.prices_found = 0
        self.prices_created = 0
        self.prices_updated = 0

    async def start(self):
        """Bridge Scrapy's async start hook to the Django-backed request generator."""
        requests = await sync_to_async(list)(self.start_requests())
        for request in requests:
            yield request

    def start_requests(self):
        # Get all active companies from the Django database.
        companies = Company.objects.filter(
            is_active=True
        ).order_by("symbol")

        if not companies.exists():
            self.logger.error(
                "No active companies found in Company table."
            )
            return

        self.logger.info(
            "Found %s active companies to crawl.",
            companies.count(),
        )

        for company in companies:
            symbol = company.symbol.lower()
            url = (
                "https://www.sharesansar.com/"
                f"company/{symbol}"
            )

            self.logger.info(
                "Opening company page for %s: %s",
                company.symbol,
                url,
            )

            yield scrapy.Request(
                url=url,
                callback=self.parse_company,
                cb_kwargs={
                    "symbol": company.symbol,
                },
                errback=self.handle_error,
                dont_filter=True,
            )


    def parse_company(
        self,
        response,
        symbol,
    ):
        self.logger.info(
            "%s company page status: %s",
            symbol,
            response.status,
        )

        # ------------------------------------------------------------------
        # Extract the ShareSansar internal company ID from the page.
        # ------------------------------------------------------------------
        company_id = response.css("#companyid::text").get()

        if company_id:
            company_id = company_id.strip()

        if not company_id:
            match = re.search(
                r'id=["\']companyid["\'][^>]*>\s*(\d+)',
                response.text,
                re.I,
            )
            if match:
                company_id = match.group(1)

        if not company_id:
            self.logger.error(
                "Could not determine ShareSansar "
                "company ID for %s",
                symbol,
            )
            return

        self.logger.info("%s company ID: %s", symbol, company_id)

        # ------------------------------------------------------------------
        # CSRF token
        # ------------------------------------------------------------------
        csrf_token = (
            response.css('meta[name="csrf-token"]::attr(content)').get()
            or response.css('meta[name="_token"]::attr(content)').get()
            or response.css('input[name="_token"]::attr(value)').get()
        )

        if csrf_token:
            csrf_token = csrf_token.strip()

        if not csrf_token:
            self.logger.error("CSRF token not found for %s", symbol)
            return

        # ------------------------------------------------------------------
        # First page — start=0
        # ------------------------------------------------------------------
        yield from self._make_price_request(
            symbol=symbol,
            company_id=company_id,
            csrf_token=csrf_token,
            referer=response.url,
            start=0,
        )

    def _make_price_request(
        self,
        symbol,
        company_id,
        csrf_token,
        referer,
        start=0,
    ):
        """Build and yield a DataTables POST for price history at the given offset."""
        form_data = self.build_form_data(
            company_id=company_id,
            start=start,
        )

        self.logger.info(
            "Sending price-history POST for %s (start=%s, length=%s)",
            symbol,
            start,
            self.LOOKBACK_ROWS,
        )

        yield scrapy.FormRequest(
            url=self.PRICE_HISTORY_URL,
            method="POST",
            formdata=form_data,
            headers={
                "X-CSRF-TOKEN": csrf_token,
                "X-Requested-With": "XMLHttpRequest",
                "Referer": referer,
                "Origin": "https://www.sharesansar.com",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            },
            callback=self.parse_history,
            cb_kwargs={
                "symbol": symbol,
                "company_id": company_id,
                "csrf_token": csrf_token,
                "referer": referer,
                "start": start,
            },
            errback=self.handle_error,
            dont_filter=True,
        )

    def build_form_data(
        self,
        company_id,
        start=0,
    ):
        """
        Build the DataTables POST body for the price-history endpoint.

        ``length`` is driven by ``LOOKBACK_ROWS`` (default 50).
        50 rows covers ≈2 calendar months of trading days, guaranteeing
        the 31-day rolling window is always fully populated.
        """
        columns = [
            "DT_Row_Index",
            "published_date",
            "open",
            "high",
            "low",
            "close",
            "per_change",
            "traded_quantity",
            "traded_amount",
        ]

        data = {
            "draw": "1",
            "start": str(start),
            "length": str(self.LOOKBACK_ROWS),   # ← was hardcoded "20"
            "search[value]": "",
            "search[regex]": "false",
            "company": str(company_id),
        }

        for index, column in enumerate(columns):
            data[f"columns[{index}][data]"] = column
            data[f"columns[{index}][name]"] = ""
            data[f"columns[{index}][searchable]"] = (
                "true" if column == "published_date" else "false"
            )
            data[f"columns[{index}][orderable]"] = "false"
            data[f"columns[{index}][search][value]"] = ""
            data[f"columns[{index}][search][regex]"] = "false"

        return data

    def parse_history(
        self,
        response,
        symbol,
        company_id,
        csrf_token,
        referer,
        start,
    ):
        self.logger.info(
            "Price history response for %s: HTTP %s (start=%s)",
            symbol,
            response.status,
            start,
        )

        if response.status not in (200, 202):
            self.logger.error("Price history failed for %s", symbol)
            return

        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON for %s", symbol)
            self.logger.error(response.text[:3000])
            return

        records_total = payload.get("recordsTotal", 0)
        records_filtered = payload.get("recordsFiltered", 0)
        rows = payload.get("data", [])

        self.logger.info(
            "%s recordsTotal=%s recordsFiltered=%s rows_received=%s",
            symbol,
            records_total,
            records_filtered,
            len(rows),
        )

        if not rows:
            self.logger.warning("No trading data returned for %s (start=%s)", symbol, start)
            return

        # ------------------------------------------------------------------
        # Yield items for every row on this page
        # ------------------------------------------------------------------
        for row in rows:
            self.logger.info("Trading row: %s", row)

            yield DailyTradingDataItem(
                item_type="daily_price",
                company=symbol,
                date=row.get("published_date"),
                open=row.get("open"),
                high=row.get("high"),
                low=row.get("low"),
                close=row.get("close"),
                volume=row.get("traded_quantity"),
                turnover=row.get("traded_amount"),
                source=self.SOURCE,
            )

        # ------------------------------------------------------------------
        # Pagination: if the server has more rows beyond what we received,
        # request the next page — but only up to LOOKBACK_ROWS total rows
        # so we do not accidentally download the entire historical database.
        # ------------------------------------------------------------------
        next_start = start + self.LOOKBACK_ROWS

        try:
            total_available = int(records_filtered or records_total or 0)
        except (TypeError, ValueError):
            total_available = 0

        if next_start < total_available and next_start < self.LOOKBACK_ROWS:
            # We never go beyond one extra page because LOOKBACK_ROWS is
            # already generous (50 rows ≈ 2 months).  This guard prevents
            # accidentally fetching hundreds of pages of historical data.
            self.logger.info(
                "%s: fetching next page (start=%s of %s)",
                symbol,
                next_start,
                total_available,
            )
            yield from self._make_price_request(
                symbol=symbol,
                company_id=company_id,
                csrf_token=csrf_token,
                referer=referer,
                start=next_start,
            )

    # ========================================================
    # ERROR HANDLER
    # ========================================================

    def handle_error(
        self,
        failure,
    ):

        self.logger.error(
            "REQUEST FAILED"
        )

        self.logger.error(
            "%r",
            failure,
        )

        response = getattr(
            failure.value,
            "response",
            None,
        )

        if response:

            self.logger.error(
                "URL: %s",
                response.url,
            )

            self.logger.error(
                "STATUS: %s",
                response.status,
            )

            self.logger.error(
                "BODY:"
            )

            self.logger.error(
                response.text[:3000]
            )

