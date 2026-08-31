
import json
import os
import re
import sys
from pathlib import Path

import django
import scrapy


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

    custom_settings = {
        "ROBOTSTXT_OBEY": True,

        "CONCURRENT_REQUESTS": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,

        "DOWNLOAD_DELAY": 2,

        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 2,
        "AUTOTHROTTLE_MAX_DELAY": 10,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 0.5,

        # Important for the POST request
        "COOKIES_ENABLED": True,
    }


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

       

        company_id = response.css(
            "#companyid::text"
        ).get()

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

        self.logger.info(
            "%s company ID: %s",
            symbol,
            company_id,
        )



        csrf_token = response.css(
            'meta[name="csrf-token"]::attr(content)'
        ).get()

        if not csrf_token:

            csrf_token = response.css(
                'meta[name="_token"]::attr(content)'
            ).get()

        if not csrf_token:

            csrf_token = response.css(
                'input[name="_token"]::attr(value)'
            ).get()

        if csrf_token:
            csrf_token = csrf_token.strip()

        self.logger.info(
            "%s CSRF token found: %s",
            symbol,
            bool(csrf_token),
        )

        if not csrf_token:

            self.logger.error(
                "CSRF token not found for %s",
                symbol,
            )

            return



        form_data = self.build_form_data(
            company_id=company_id,
        )

        self.logger.info(
            "Sending price-history POST for %s",
            symbol,
        )

        # ----------------------------------------------------
        # POST
        # ----------------------------------------------------

        yield scrapy.FormRequest(
            url=self.PRICE_HISTORY_URL,

            method="POST",

            formdata=form_data,

            headers={
                "X-CSRF-TOKEN": csrf_token,

                "X-Requested-With": "XMLHttpRequest",

                "Referer": response.url,

                "Origin": "https://www.sharesansar.com",

                "Accept": (
                    "application/json, "
                    "text/javascript, "
                    "*/*; q=0.01"
                ),

                "Content-Type": (
                    "application/x-www-form-urlencoded; "
                    "charset=UTF-8"
                ),
            },

            callback=self.parse_history,

            cb_kwargs={
                "symbol": symbol,
            },

            errback=self.handle_error,

            dont_filter=True,
        )

    

    def build_form_data(
        self,
        company_id,
    ):

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

            "start": "0",

            # Browser showed length = 20
            "length": "20",

            "search[value]": "",

            "search[regex]": "false",

            "company": str(company_id),
        }

        for index, column in enumerate(columns):

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
                if column == "published_date"
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

        return data

   

    def parse_history(
        self,
        response,
        symbol,
    ):

        self.logger.info(
            "Price history response for %s: HTTP %s",
            symbol,
            response.status,
        )

        self.logger.info(
            "Price history URL: %s",
            response.url,
        )

        self.logger.info(
            "Response body: %s",
            response.text[:3000],
        )


        if response.status not in (200, 202):

            self.logger.error(
                "Price history failed for %s",
                symbol,
            )

            return



        try:

            payload = json.loads(
                response.text
            )

        except json.JSONDecodeError:

            self.logger.error(
                "Invalid JSON for %s",
                symbol,
            )

            self.logger.error(
                response.text[:3000]
            )

            return




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
            "%s recordsTotal=%s",
            symbol,
            records_total,
        )

        self.logger.info(
            "%s recordsFiltered=%s",
            symbol,
            records_filtered,
        )

        self.logger.info(
            "%s received %s rows",
            symbol,
            len(rows),
        )



        if not rows:

            self.logger.warning(
                "No trading data returned for %s",
                symbol,
            )

            return

    

        for row in rows:

            self.logger.info(
                "Trading row: %s",
                row,
            )

            yield DailyTradingDataItem(

                item_type="daily_price",

                company=symbol,

                date=row.get(
                    "published_date"
                ),

                open=row.get(
                    "open"
                ),

                high=row.get(
                    "high"
                ),

                low=row.get(
                    "low"
                ),

                close=row.get(
                    "close"
                ),

                volume=row.get(
                    "traded_quantity"
                ),

                turnover=row.get(
                    "traded_amount"
                ),

                source=self.SOURCE,
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

