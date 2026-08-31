import os
import sys
import json

from pathlib import Path

import django
import scrapy


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

    name = "floorsheet"

    allowed_domains = [
        "sharesansar.com",
        "www.sharesansar.com",
    ]

    SOURCE = "ShareSansar"

    URL = (
        "https://www.sharesansar.com/"
        "company-floor-sheet"
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
    }

    def start_requests(self):

        companies = Company.objects.filter(
            is_active=True,
        ).order_by("symbol")[:10]

        for company in companies:

            yield scrapy.Request(
                url=(
                    f"https://www.sharesansar.com/"
                    f"company/{company.symbol.lower()}"
                ),

                callback=self.parse_company,

                cb_kwargs={
                    "symbol": company.symbol,
                },

                errback=self.handle_error,
            )

    def parse_company(
        self,
        response,
        symbol,
    ):

        csrf_token = (
            response.css(
                'meta[name="_token"]::attr(content)'
            ).get()
            or
            response.css(
                'input[name="_token"]::attr(value)'
            ).get()
        )

        if not csrf_token:

            self.logger.error(
                "CSRF token missing for %s",
                symbol,
            )

            return

        # Use the currently displayed/default
        # floorsheet date.
        date_value = (
            self.floorsheet_date 
            
            or response.css(
                "#date::attr(value)"
            ).get()
        )

        if not date_value:

            date_value = (
                response.css(
                    "#date::text"
                ).get()
            )

        if not date_value:

            self.logger.warning(
                "No floorsheet date found for %s",
                symbol,
            )

            return

        yield self.make_request(
            symbol=symbol,
            date=date_value,
            csrf_token=csrf_token,
            referer=response.url,
        )

    def make_request(
        self,
        symbol,
        date,
        csrf_token,
        referer,
    ):

        data = {

            "draw": "1",

            "start": "0",

            "length": "200",

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
                if column
                in {
                    "contract_no",
                    "buyer",
                    "seller",
                    "quantity",
                    "rate",
                    "amount",
                    "date_",
                }
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

        yield scrapy.FormRequest(
            url=self.URL,

            method="POST",

            formdata=data,

            headers={
                "X-CSRF-TOKEN": csrf_token,

                "X-Requested-With":
                    "XMLHttpRequest",

                "Referer": referer,

                "Origin":
                    "https://www.sharesansar.com",

                "Accept":
                    "application/json, "
                    "text/javascript, */*; q=0.01",
            },

            callback=self.parse_floorsheet,

            cb_kwargs={
                "symbol": symbol,
                "date": date,
            },

            errback=self.handle_error,
        )

    def parse_floorsheet(
        self,
        response,
        symbol,
        date,
    ):

        try:

            payload = json.loads(
                response.text
            )

        except json.JSONDecodeError:

            self.logger.error(
                "Invalid floorsheet JSON: %s",
                symbol,
            )

            return

        rows = payload.get(
            "data",
            [],
        )

        self.logger.info(
            "%s: %s floorsheet rows",
            symbol,
            len(rows),
        )

        for row in rows:

            yield FloorsheetItem(

                item_type="floorsheet",

                company=symbol,

                date=(
                    row.get("date_")
                    or date
                ),

                transaction_id=(
                    row.get("contract_no")
                ),

                buyer_broker=(
                    row.get("buyer")
                ),

                seller_broker=(
                    row.get("seller")
                ),

                quantity=(
                    row.get("quantity")
                ),

                rate=(
                    row.get("rate")
                ),

                amount=(
                    row.get("amount")
                ),

                source=self.SOURCE,
            )

    def handle_error(
        self,
        failure,
    ):

        self.logger.error(
            "Floorsheet request failed: %r",
            failure,
        )
        
    def __init__(
        self,
        floorsheet_date=None,
        *args,
        **kwargs,
    ):

        super().__init__(*args, **kwargs)

        self.floorsheet_date = (
            floorsheet_date
        )