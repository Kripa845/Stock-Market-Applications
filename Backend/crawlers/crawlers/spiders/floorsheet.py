import json
import os
import sys
from pathlib import Path

import django
import scrapy


# ============================================================
# DJANGO SETUP
# ============================================================

BASE_DIR = Path(__file__).resolve()

while not (BASE_DIR / "manage.py").exists():
    BASE_DIR = BASE_DIR.parent

sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings",
)

django.setup()


# ============================================================
# IMPORTS
# ============================================================

from apps.companies.models import Company
from crawlers.items import FloorsheetItem


# ============================================================
# SPIDER
# ============================================================

class FloorsheetSpider(scrapy.Spider):

    name = "floorsheet"

    allowed_domains = [
        "sharesansar.com",
        "www.sharesansar.com",
    ]

    SOURCE = "ShareSansar"

    # ShareSansar floorsheet endpoint
    URL = (
        "https://www.sharesansar.com/"
        "company-floor-sheet"
    )

    # Number of companies to test.
    # Remove the limit after confirming the crawler works.
    COMPANY_LIMIT = 10

    # Number of floorsheet records requested per page.
    PAGE_LENGTH = 200

    custom_settings = {

        # Respect robots.txt
        "ROBOTSTXT_OBEY": True,

        # Be conservative with requests
        "CONCURRENT_REQUESTS": 1,

        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,

        "DOWNLOAD_DELAY": 2,

        # Auto throttling
        "AUTOTHROTTLE_ENABLED": True,

        "AUTOTHROTTLE_START_DELAY": 2,

        "AUTOTHROTTLE_MAX_DELAY": 10,

        "AUTOTHROTTLE_TARGET_CONCURRENCY": 0.5,

        # Keep cookies because CSRF/session may depend on them.
        "COOKIES_ENABLED": True,

        # Useful debugging
        "HTTPERROR_ALLOW_ALL": True,
    }

    # ========================================================
    # INITIALIZATION
    # ========================================================

    def __init__(
        self,
        floorsheet_date=None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        # Optional date supplied from command line:
        #
        # scrapy crawl floorsheet -a floorsheet_date=2026-08-26
        #
        self.floorsheet_date = floorsheet_date

        self.requested_companies = 0
        self.successful_responses = 0
        self.failed_responses = 0
        self.items_found = 0

        self.floorsheet_saved = 0
        self.floorsheet_failed = 0

    # ========================================================
    # START REQUESTS
    # ========================================================

    def start_requests(self):

        companies = (
            Company.objects
            .filter(is_active=True)
            .order_by("symbol")
        )

        if self.COMPANY_LIMIT:
            companies = companies[:self.COMPANY_LIMIT]

        companies = list(companies)

        if not companies:
            self.logger.error(
                "No active companies found in Company table."
            )
            return

        self.logger.info(
            "Found %s companies to crawl.",
            len(companies),
        )

        for company in companies:

            symbol = (
                str(company.symbol)
                .strip()
                .upper()
            )

            if not symbol:
                self.logger.warning(
                    "Skipping company with empty symbol."
                )
                continue

            self.requested_companies += 1

            company_url = (
                "https://www.sharesansar.com/"
                f"company/{symbol.lower()}"
            )

            self.logger.info(
                "Opening company page for %s: %s",
                symbol,
                company_url,
            )

            yield scrapy.Request(

                url=company_url,

                callback=self.parse_company,

                cb_kwargs={
                    "symbol": symbol,
                },

                errback=self.handle_error,

                # Allow repeated company requests.
                dont_filter=True,
            )

    # ========================================================
    # PARSE COMPANY PAGE
    # ========================================================

    def parse_company(
        self,
        response,
        symbol,
    ):

        self.logger.info(
            "%s company page HTTP status: %s",
            symbol,
            response.status,
        )

        # ----------------------------------------------------
        # CHECK RESPONSE
        # ----------------------------------------------------

        if response.status != 200:

            self.logger.error(
                "Company page failed for %s: HTTP %s",
                symbol,
                response.status,
            )

            self.failed_responses += 1

            return

        # ----------------------------------------------------
        # CSRF TOKEN
        # ----------------------------------------------------

        csrf_token = (
            response.css(
                'meta[name="csrf-token"]::attr(content)'
            ).get()
        )

        if not csrf_token:

            csrf_token = (
                response.css(
                    'meta[name="_token"]::attr(content)'
                ).get()
            )

        if not csrf_token:

            csrf_token = (
                response.css(
                    'input[name="_token"]::attr(value)'
                ).get()
            )

        if csrf_token:

            csrf_token = csrf_token.strip()

        self.logger.info(
            "%s: CSRF token found = %s",
            symbol,
            bool(csrf_token),
        )

        if not csrf_token:

            self.logger.error(
                "CSRF token missing for %s",
                symbol,
            )

            return

        # ----------------------------------------------------
        # DETERMINE DATE
        # ----------------------------------------------------

        date_value = self.get_floorsheet_date(
            response
        )

        if not date_value:

            self.logger.warning(
                "No floorsheet date found for %s",
            )

            return

        self.logger.info(
            "%s: floorsheet date = %s",
            symbol,
            date_value,
        )

        # ----------------------------------------------------
        # SEND FIRST PAGE
        # ----------------------------------------------------

        yield from self.make_request(
            symbol=symbol,
            date=date_value,
            csrf_token=csrf_token,
            referer=response.url,
            start=0,
        )

    # ========================================================
    # GET FLOOR SHEET DATE
    # ========================================================

    def get_floorsheet_date(
        self,
        response,
    ):

        # ----------------------------------------------------
        # 1. Explicit date passed from command line
        # ----------------------------------------------------

        if self.floorsheet_date:

            return str(
                self.floorsheet_date
            ).strip()

        # ----------------------------------------------------
        # 2. Common date input selectors
        # ----------------------------------------------------

        selectors = [

            "#date::attr(value)",

            "#date::text",

            'input[name="date"]::attr(value)',

            'input[name="date_"]::attr(value)',

            'input[name="as_on"]::attr(value)',

            'input[name="as_on_date"]::attr(value)',

            '#datepicker::attr(value)',

            '.datepicker::attr(value)',
        ]

        for selector in selectors:

            value = response.css(
                selector
            ).get()

            if value:

                value = value.strip()

                if value:

                    return value

        # ----------------------------------------------------
        # 3. Try data attributes
        # ----------------------------------------------------

        data_selectors = [

            '[data-date]::attr(data-date)',

            '[data-value]::attr(data-value)',
        ]

        for selector in data_selectors:

            value = response.css(
                selector
            ).get()

            if value:

                value = value.strip()

                if value:

                    return value

        # ----------------------------------------------------
        # 4. Log useful HTML around date controls
        # ----------------------------------------------------

        date_html = response.css(
            "#date"
        ).get()

        if date_html:

            self.logger.warning(
                "Date element found but value "
                "could not be extracted: %s",
                date_html[:1000],
            )

        else:

            self.logger.warning(
                "No #date element found on %s",
                response.url,
            )

        return None

    # ========================================================
    # BUILD DATATABLES REQUEST
    # ========================================================

    def make_request(
        self,
        symbol,
        date,
        csrf_token,
        referer,
        start=0,
    ):

        data = {

            # DataTables
            "draw": "1",

            "start": str(start),

            "length": str(
                self.PAGE_LENGTH
            ),

            # Global search
            "search[value]": "",

            "search[regex]": "false",

            # Filters
            "company": symbol,

            "buyer": "",

            "seller": "",

        }

        # ----------------------------------------------------
        # DataTables columns
        # ----------------------------------------------------

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

        for index, column in enumerate(
            columns
        ):

            data[
                f"columns[{index}][data]"
            ] = column

            data[
                f"columns[{index}][name]"
            ] = ""

            data[
                f"columns[{index}][searchable]"
            ] = (
                "true"
                if column != "DT_Row_Index"
                else "false"
            )

            data[
                f"columns[{index}][orderable]"
            ] = "false"

            data[
                f"columns[{index}][search][value]"
            ] = ""

            data[
                f"columns[{index}][search][regex]"
            ] = "false"

        self.logger.info(
            (
                "Sending floorsheet POST | "
                "symbol=%s | date=%s | start=%s"
            ),
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

                "X-Requested-With":
                    "XMLHttpRequest",

                "Referer":
                    referer,

                "Origin":
                    "https://www.sharesansar.com",

                "Accept":
                    (
                        "application/json, "
                        "text/javascript, "
                        "*/*; q=0.01"
                    ),

                "Content-Type":
                    (
                        "application/x-www-form-urlencoded; "
                        "charset=UTF-8"
                    ),
            },

            callback=self.parse_floorsheet,

            cb_kwargs={
                "symbol": symbol,
                "date": date,
                "start": start,
            },

            errback=self.handle_error,

            dont_filter=True,
        )

    # ========================================================
    # PARSE FLOOR SHEET RESPONSE
    # ========================================================

    def parse_floorsheet(
        self,
        response,
        symbol,
        date,
        start,
    ):

        self.logger.info(
            (
                "Floorsheet response | "
                "symbol=%s | HTTP=%s | URL=%s"
            ),
            symbol,
            response.status,
            response.url,
        )

        # ----------------------------------------------------
        # HTTP STATUS
        # ----------------------------------------------------

        if response.status not in (
            200,
            202,
        ):

            self.logger.error(
                (
                    "Floorsheet request failed "
                    "for %s: HTTP %s"
                ),
                symbol,
                response.status,
            )

            self.failed_responses += 1

            self.logger.error(
                "Response body: %s",
                response.text[:3000],
            )

            return

        # ----------------------------------------------------
        # EMPTY RESPONSE
        # ----------------------------------------------------

        if not response.text.strip():

            self.logger.error(
                "Empty floorsheet response for %s",
                symbol,
            )

            return

        # ----------------------------------------------------
        # JSON
        # ----------------------------------------------------

        try:

            payload = json.loads(
                response.text
            )

        except json.JSONDecodeError:

            self.logger.error(
                "Invalid JSON response for %s",
                symbol,
            )

            self.logger.error(
                "Response body: %s",
                response.text[:3000],
            )

            return

        # ----------------------------------------------------
        # LOG RESPONSE STRUCTURE
        # ----------------------------------------------------

        self.logger.info(
            "%s response keys: %s",
            symbol,
            list(payload.keys()),
        )

        # ----------------------------------------------------
        # DATATABLE METADATA
        # ----------------------------------------------------

        records_total = payload.get(
            "recordsTotal",
            0,
        )

        records_filtered = payload.get(
            "recordsFiltered",
            0,
        )

        rows = payload.get(
            "data",
            [],
        )

        self.logger.info(
            (
                "%s | recordsTotal=%s | "
                "recordsFiltered=%s | rows=%s"
            ),
            symbol,
            records_total,
            records_filtered,
            len(rows),
        )

        # ----------------------------------------------------
        # DEBUG EMPTY DATA
        # ----------------------------------------------------

        if not rows:

            self.logger.warning(
                (
                    "No floorsheet rows returned "
                    "for %s on %s"
                ),
                symbol,
                date,
            )

            self.logger.debug(
                "Full response: %s",
                response.text[:5000],
            )

            return

        self.successful_responses += 1

        # ----------------------------------------------------
        # PROCESS ROWS
        # ----------------------------------------------------

        for row in rows:

            self.logger.debug(
                "Raw floorsheet row: %s",
                row,
            )

            # -----------------------------------------------
            # EXTRACT VALUES
            # -----------------------------------------------

            transaction_id = (
                row.get("contract_no")
                or row.get("transaction_id")
                or row.get("contract")
            )

            buyer_broker = (
                row.get("buyer")
                or row.get("buyer_broker")
            )

            seller_broker = (
                row.get("seller")
                or row.get("seller_broker")
            )

            quantity = (
                row.get("quantity")
                or row.get("qty")
            )

            rate = (
                row.get("rate")
                or row.get("price")
            )

            amount = (
                row.get("amount")
                or row.get("turnover")
            )

            transaction_date = (
                row.get("date_")
                or row.get("date")
                or date
            )

            # -----------------------------------------------
            # BASIC VALIDATION
            # -----------------------------------------------

            if not buyer_broker:

                self.logger.warning(
                    (
                        "Skipping row for %s: "
                        "buyer broker missing"
                    ),
                    symbol,
                )

                continue

            if not seller_broker:

                self.logger.warning(
                    (
                        "Skipping row for %s: "
                        "seller broker missing"
                    ),
                    symbol,
                )

                continue

            if quantity in (
                None,
                "",
            ):

                self.logger.warning(
                    (
                        "Skipping row for %s: "
                        "quantity missing"
                    ),
                    symbol,
                )

                continue

            if rate in (
                None,
                "",
            ):

                self.logger.warning(
                    (
                        "Skipping row for %s: "
                        "rate missing"
                    ),
                    symbol,
                )

                continue

            # -----------------------------------------------
            # YIELD ITEM
            # -----------------------------------------------

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

        # ----------------------------------------------------
        # PAGINATION
        # ----------------------------------------------------
        #
        # If the endpoint reports more records than the
        # current page, request the next page.
        #
        # Example:
        #
        # recordsTotal = 500
        # current page = 200
        #
        # next start = 200
        # ----------------------------------------------------

        try:

            total_records = int(
                records_filtered
                or records_total
                or 0
            )

        except (
            TypeError,
            ValueError,
        ):

            total_records = 0

        next_start = (
            start + self.PAGE_LENGTH
        )

        if (
            total_records > next_start
            and len(rows) > 0
        ):

            self.logger.info(
                (
                    "%s: requesting next page "
                    "start=%s of %s"
                ),
                symbol,
                next_start,
                total_records,
            )

            # We need the CSRF token again.
            #
            # Scrapy keeps the same cookie jar for the
            # request chain, so request the company page
            # again to obtain the token cleanly.

            company_url = (
                "https://www.sharesansar.com/"
                f"company/{symbol.lower()}"
            )

            yield scrapy.Request(

                url=company_url,

                callback=self.parse_company_next_page,

                cb_kwargs={
                    "symbol": symbol,
                    "date": date,
                    "start": next_start,
                },

                errback=self.handle_error,

                dont_filter=True,
            )

    # ========================================================
    # PREPARE NEXT PAGE
    # ========================================================

    def parse_company_next_page(
        self,
        response,
        symbol,
        date,
        start,
    ):

        csrf_token = (
            response.css(
                'meta[name="csrf-token"]::attr(content)'
            ).get()
        )

        if not csrf_token:

            csrf_token = (
                response.css(
                    'meta[name="_token"]::attr(content)'
                ).get()
            )

        if not csrf_token:

            csrf_token = (
                response.css(
                    'input[name="_token"]::attr(value)'
                ).get()
            )

        if csrf_token:

            csrf_token = csrf_token.strip()

        if not csrf_token:

            self.logger.error(
                (
                    "Could not obtain CSRF token "
                    "for next page: %s"
                ),
                symbol,
            )

            return

        yield from self.make_request(
            symbol=symbol,
            date=date,
            csrf_token=csrf_token,
            referer=response.url,
            start=start,
        )

    # ========================================================
    # ERROR HANDLER
    # ========================================================

    def handle_error(
        self,
        failure,
    ):

        self.failed_responses += 1

        self.logger.error(
            "Floorsheet request failed."
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
                "HTTP status: %s",
                response.status,
            )

            self.logger.error(
                "Response body: %s",
                response.text[:3000],
            )

    # ========================================================
    # CLOSE SPIDER
    # ========================================================

    def closed(
        self,
        reason,
    ):

        self.logger.info(
            "================================================"
        )

        self.logger.info(
            "FLOORSHEET CRAWLER FINISHED"
        )

        self.logger.info(
            "Reason: %s",
            reason,
        )

        self.logger.info(
            "Companies requested: %s",
            self.requested_companies,
        )

        self.logger.info(
            "Successful responses: %s",
            self.successful_responses,
        )

        self.logger.info(
            "Failed responses: %s",
            self.failed_responses,
        )

        self.logger.info(
            "Items found: %s",
            self.items_found,
        )

        self.logger.info(
            "Items saved by pipeline: %s",
            self.floorsheet_saved,
        )

        self.logger.info(
            "Items failed in pipeline: %s",
            self.floorsheet_failed,
        )

        self.logger.info(
            "================================================"
        )