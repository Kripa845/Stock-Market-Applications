import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import django
import scrapy
from asgiref.sync import sync_to_async


BASE_DIR = Path(__file__).resolve()

while not (BASE_DIR / "manage.py").exists():
    BASE_DIR = BASE_DIR.parent

sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings",
)

django.setup()


from apps.companies.models import Company
from crawlers.items import FloorsheetItem


class FloorsheetSpider(scrapy.Spider):
    """
    Collects floorsheet (transaction-level) data from ShareSansar for every
    active company in the database.

    Representative multi-day sample
    --------------------------------
    The spider collects floorsheet data for the most recent ``DAYS_BACK``
    calendar days per company (default 5 days ≈ one trading week).
    On every scheduled run:

    - The date range is computed dynamically as
      ``today - DAYS_BACK`` → ``today`` (rolling, no hardcoded dates).
    - Already-stored transactions are ignored via the
      ``UniqueConstraint(company, date, transaction_id)`` in the database.
    - Historical records are never deleted.

    You can override the number of days on the command line::

        scrapy crawl floorsheet -a floorsheet_days_back=10
        scrapy crawl floorsheet -a floorsheet_date=2026-09-16   (single day)
    """

    name = "floorsheet"

    allowed_domains = [
        "sharesansar.com",
        "www.sharesansar.com",
    ]

    SOURCE = "ShareSansar"

    # ShareSansar floorsheet endpoint
    URL = "https://www.sharesansar.com/company-floor-sheet"

    # Number of companies to process (None = all active companies).
    COMPANY_LIMIT = None

    # Number of calendar days to look back for floorsheet data.
    # 5 days ≈ one full trading week = a representative sample.
    # Increase to 10 for a two-week sample.
    DAYS_BACK = 5

    # Number of floorsheet records requested per page.
    PAGE_LENGTH = 200

    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "CONCURRENT_REQUESTS": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 2,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 2,
        "AUTOTHROTTLE_MAX_DELAY": 10,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 0.5,
        "COOKIES_ENABLED": True,
        "HTTPERROR_ALLOW_ALL": True,
    }

    def __init__(
        self,
        floorsheet_date=None,
        floorsheet_days_back=None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        # Single-date override: scrape only this one date.
        self.floorsheet_date = floorsheet_date

        # Number-of-days override from CLI.
        if floorsheet_days_back is not None:
            try:
                self.DAYS_BACK = int(floorsheet_days_back)
            except (TypeError, ValueError):
                pass

        self.requested_companies = 0
        self.successful_responses = 0
        self.failed_responses = 0
        self.items_found = 0

        self.floorsheet_saved = 0
        self.floorsheet_failed = 0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _target_dates(self):
        """
        Return a list of date strings (YYYY-MM-DD format) to request.

        If ``floorsheet_date`` was supplied on the CLI, return that
        single date only.  Otherwise return the last ``DAYS_BACK``
        calendar days (most-recent first).  Weekend days (Sat) are
        included; the website simply returns no data for non-trading days.
        """
        if self.floorsheet_date:
            return [str(self.floorsheet_date).strip()]

        today = date.today()
        return [
            str(today - timedelta(days=i))
            for i in range(self.DAYS_BACK)
        ]

    # ------------------------------------------------------------------
    # Request generation
    # ------------------------------------------------------------------

    async def start(self):
        """Bridge Scrapy's async start hook to the Django-backed request generator."""
        requests = await sync_to_async(list)(self.start_requests())
        for request in requests:
            yield request

    def start_requests(self):
        companies = Company.objects.filter(is_active=True).order_by("symbol")

        if self.COMPANY_LIMIT:
            companies = companies[: self.COMPANY_LIMIT]

        companies = list(companies)

        if not companies:
            self.logger.error("No active companies found in Company table.")
            return

        target_dates = self._target_dates()

        self.logger.info(
            "Found %s companies to crawl; collecting floorsheet for %s date(s): %s",
            len(companies),
            len(target_dates),
            ", ".join(target_dates),
        )

        for company in companies:
            symbol = str(company.symbol).strip().upper()
            if not symbol:
                continue

            self.requested_companies += 1
            company_url = f"https://www.sharesansar.com/company/{symbol.lower()}"

            self.logger.info("Opening company page for %s: %s", symbol, company_url)

            yield scrapy.Request(
                url=company_url,
                callback=self.parse_company,
                cb_kwargs={
                    "symbol": symbol,
                    # Pass the full list of dates we want for this company.
                    "target_dates": target_dates,
                },
                errback=self.handle_error,
                dont_filter=True,
            )

    # ------------------------------------------------------------------
    # Company page parsing
    # ------------------------------------------------------------------

    def parse_company(
        self,
        response,
        symbol,
        target_dates,
    ):
        self.logger.info(
            "%s company page HTTP status: %s",
            symbol,
            response.status,
        )

        if response.status != 200:
            self.logger.error(
                "Company page failed for %s: HTTP %s",
                symbol,
                response.status,
            )
            self.failed_responses += 1
            return

        # Extract CSRF token
        csrf_token = (
            response.css('meta[name="csrf-token"]::attr(content)').get()
            or response.css('meta[name="_token"]::attr(content)').get()
            or response.css('input[name="_token"]::attr(value)').get()
        )

        if csrf_token:
            csrf_token = csrf_token.strip()

        if not csrf_token:
            self.logger.error("CSRF token missing for %s", symbol)
            return

        self.logger.info(
            "%s: CSRF token found. Requesting %s date(s): %s",
            symbol,
            len(target_dates),
            ", ".join(target_dates),
        )

        # Yield one floorsheet request per target date
        for date_value in target_dates:
            yield from self.make_request(
                symbol=symbol,
                date=date_value,
                csrf_token=csrf_token,
                referer=response.url,
                start=0,
            )

    # ------------------------------------------------------------------
    # Floorsheet POST request builder
    # ------------------------------------------------------------------

    def make_request(
        self,
        symbol,
        date,
        csrf_token,
        referer,
        start=0,
    ):
        """Yield a POST request for one symbol+date combination at the given page offset."""
        data = {
            "draw": "1",
            "start": str(start),
            "length": str(self.PAGE_LENGTH),
            "search[value]": "",
            "search[regex]": "false",
            "company": symbol,
            "buyer": "",
            "seller": "",
        }

        columns = [
            "DT_Row_Index",
            "contract_no",
            "buyer",
            "seller",
            "quantity",
            "rate",
            "amount",
            "date_",
        ]

        for index, column in enumerate(columns):
            data[f"columns[{index}][data]"] = column
            data[f"columns[{index}][name]"] = ""
            data[f"columns[{index}][searchable]"] = (
                "false" if column == "DT_Row_Index" else "true"
            )
            data[f"columns[{index}][orderable]"] = "false"
            data[f"columns[{index}][search][value]"] = ""
            data[f"columns[{index}][search][regex]"] = "false"

        self.logger.info(
            "Floorsheet POST | symbol=%s | date=%s | start=%s",
            symbol,
            date,
            start,
        )

        yield scrapy.FormRequest(
            url=self.URL,
            method="POST",
            formdata=data,
            headers={
                "X-CSRF-TOKEN": csrf_token,
                "X-Requested-With": "XMLHttpRequest",
                "Referer": referer,
                "Origin": "https://www.sharesansar.com",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            },
            callback=self.parse_floorsheet,
            cb_kwargs={
                "symbol": symbol,
                "date": date,
                # Carry CSRF + referer so the pagination handler can re-use them
                # without hitting the company page again.
                "csrf_token": csrf_token,
                "referer": referer,
                "start": start,
            },
            errback=self.handle_error,
            dont_filter=True,
        )

    # ------------------------------------------------------------------
    # Parse floorsheet JSON response
    # ------------------------------------------------------------------

    def parse_floorsheet(
        self,
        response,
        symbol,
        date,
        csrf_token,
        referer,
        start,
    ):
        self.logger.info(
            "Floorsheet response | symbol=%s | HTTP=%s | date=%s | start=%s",
            symbol,
            response.status,
            date,
            start,
        )

        if response.status not in (200, 202):
            self.logger.error(
                "Floorsheet request failed for %s on %s: HTTP %s",
                symbol,
                date,
                response.status,
            )
            self.failed_responses += 1
            return

        if not response.text.strip():
            self.logger.error("Empty floorsheet response for %s on %s", symbol, date)
            return

        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger.error(
                "Invalid JSON for %s on %s: %s",
                symbol,
                date,
                response.text[:3000],
            )
            return

        records_total = payload.get("recordsTotal", 0)
        records_filtered = payload.get("recordsFiltered", 0)
        rows = payload.get("data", [])

        self.logger.info(
            "%s | date=%s | recordsTotal=%s | recordsFiltered=%s | rows=%s",
            symbol,
            date,
            records_total,
            records_filtered,
            len(rows),
        )

        if not rows:
            self.logger.warning(
                "No floorsheet rows for %s on %s",
                symbol,
                date,
            )
            return

        self.successful_responses += 1

        # ------------------------------------------------------------------
        # Yield one FloorsheetItem per transaction row
        # ------------------------------------------------------------------
        for row in rows:
            transaction_id = (
                row.get("contract_no")
                or row.get("transaction_id")
                or row.get("contract")
            )

            buyer_broker  = row.get("buyer")  or row.get("buyer_broker")
            seller_broker = row.get("seller") or row.get("seller_broker")
            quantity      = row.get("quantity") or row.get("qty")
            rate          = row.get("rate")   or row.get("price")
            amount        = row.get("amount") or row.get("turnover")
            transaction_date = row.get("date_") or row.get("date") or date

            if not buyer_broker:
                self.logger.warning("Skipping row for %s: buyer broker missing", symbol)
                continue
            if not seller_broker:
                self.logger.warning("Skipping row for %s: seller broker missing", symbol)
                continue
            if quantity in (None, ""):
                self.logger.warning("Skipping row for %s: quantity missing", symbol)
                continue
            if rate in (None, ""):
                self.logger.warning("Skipping row for %s: rate missing", symbol)
                continue

            self.items_found += 1

            yield FloorsheetItem(
                item_type="floorsheet",
                company=symbol,
                date=transaction_date,
                transaction_id=transaction_id,
                buyer_broker=buyer_broker,
                seller_broker=seller_broker,
                quantity=quantity,
                rate=rate,
                amount=amount,
                source=self.SOURCE,
            )

        # ------------------------------------------------------------------
        # Pagination within the same date: request the next page if more
        # records exist beyond what was returned.
        # ------------------------------------------------------------------
        try:
            total_records = int(records_filtered or records_total or 0)
        except (TypeError, ValueError):
            total_records = 0

        next_start = start + self.PAGE_LENGTH

        if total_records > next_start and len(rows) > 0:
            self.logger.info(
                "%s: requesting next page start=%s of %s (date=%s)",
                symbol,
                next_start,
                total_records,
                date,
            )
            # Re-use the CSRF token and referer already in scope — no need
            # to hit the company page again just to get a new token.
            yield from self.make_request(
                symbol=symbol,
                date=date,
                csrf_token=csrf_token,
                referer=referer,
                start=next_start,
            )

    # ------------------------------------------------------------------
    # Error handler
    # ------------------------------------------------------------------

    def handle_error(self, failure):
        self.failed_responses += 1
        self.logger.error("Floorsheet request failed: %r", failure)

        response = getattr(failure.value, "response", None)
        if response:
            self.logger.error("URL: %s", response.url)
            self.logger.error("HTTP status: %s", response.status)
            self.logger.error("Response body: %s", response.text[:3000])

    # ------------------------------------------------------------------
    # Closed
    # ------------------------------------------------------------------

    def closed(self, reason):
        self.logger.info("=" * 48)
        self.logger.info("FLOORSHEET CRAWLER FINISHED — reason: %s", reason)
        self.logger.info("Companies requested : %s", self.requested_companies)
        self.logger.info("Successful responses: %s", self.successful_responses)
        self.logger.info("Failed responses    : %s", self.failed_responses)
        self.logger.info("Items found         : %s", self.items_found)
        self.logger.info("Items saved         : %s", self.floorsheet_saved)
        self.logger.info("Items failed        : %s", self.floorsheet_failed)
        self.logger.info("=" * 48)