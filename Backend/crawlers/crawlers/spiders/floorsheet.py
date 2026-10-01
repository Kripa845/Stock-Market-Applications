
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

import django
import scrapy
from asgiref.sync import sync_to_async


BASE_DIR = Path(__file__).resolve()

while not (BASE_DIR / "manage.py").exists():
    BASE_DIR = BASE_DIR.parent

SCRAPY_PROJECT_DIR = BASE_DIR / "crawlers"

for path in (BASE_DIR, SCRAPY_PROJECT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings",
)

django.setup()


from apps.companies.models import Company
from apps.market_data.services.trading_calendar import (
    DEFAULT_SAMPLE_OFFSETS,
    latest_trading_date,
    select_sample_dates,
)
# Under ``scrapy crawl`` the Scrapy project root is on sys.path, so
# ``crawlers`` means Backend/crawlers/crawlers. Imported from Django
# (tests, management commands) ``crawlers`` means Backend/crawlers
# instead. Support both rather than only working inside Scrapy.
try:
    from crawlers.items import FloorsheetItem
except ModuleNotFoundError:  # pragma: no cover - import-path shim
    from crawlers.crawlers.items import FloorsheetItem


class FloorsheetSpider(scrapy.Spider):
    """
    Collects transaction-level floorsheet data from ShareSansar.

    Two deliberately separate collection strategies
    -----------------------------------------------
    ``DailyPrice`` needs a CONTINUOUS rolling month, because every
    metric built on it (20-session volume baseline, daily returns) breaks
    if a session is missing from the middle.

    Floorsheet is different.  A single company-day can run to thousands
    of transactions, so collecting a continuous month for every tracked
    company is neither polite to the source nor necessary: broker net
    positions are read as a SAMPLE of behaviour over time, not as a
    continuous series.  So this spider has two modes:

    ``mode=sample`` (historical)
        A deterministic sample of ~6 sessions, chosen by TRADING-SESSION
        offset from the latest available session: offsets
        ``(0, 5, 10, 15, 20, 25)``.  Session offsets, not calendar
        offsets — ``latest - 5 sessions`` skips weekends and holidays
        automatically because the session list is derived from dates the
        market actually traded (see ``apps.market_data.services``).
        The SAME sampled dates are used for every tracked company, so
        cross-company comparison on a sampled date is valid.

    ``mode=latest`` (daily, scheduled)
        Only the latest available trading session.  This is the nightly
        top-up and is what the beat schedule runs.

    Neither mode ever deletes existing rows.  Persistence goes through
    ``update_or_create`` on ``(company, date, transaction_id)``, so
    re-running a sample is idempotent and historical data accumulates.

    CLI::

        scrapy crawl floorsheet -a mode=latest
        scrapy crawl floorsheet -a mode=sample
        scrapy crawl floorsheet -a mode=sample -a sample_offsets=0,3,6,9
        scrapy crawl floorsheet -a floorsheet_date=2026-09-16
    """

    name = "floorsheet"

    allowed_domains = [
        "sharesansar.com",
        "www.sharesansar.com",
    ]

    SOURCE = "ShareSansar"

    URL = "https://www.sharesansar.com/company-floor-sheet"

    # Number of companies to process (None = all active companies).
    COMPANY_LIMIT = None

    # Trading-SESSION offsets back from the latest available session.
    SAMPLE_OFFSETS = DEFAULT_SAMPLE_OFFSETS

    # Number of floorsheet records requested per page.
    PAGE_LENGTH = 200

    # Safety limit on pages per company+date.
    MAX_PAGES_PER_DATE = 25

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
        mode="latest",
        floorsheet_date=None,
        sample_offsets=None,
        company_symbol=None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.mode = str(mode or "latest").strip().lower()

        # Single-date override: scrape only this one date.
        self.floorsheet_date = floorsheet_date
        self.company_symbol = str(company_symbol or "").strip().upper()

        if sample_offsets:
            try:
                self.SAMPLE_OFFSETS = tuple(
                    int(part.strip())
                    for part in str(sample_offsets).split(",")
                    if part.strip()
                )
            except (TypeError, ValueError):
                self.logger.warning(
                    "Could not parse sample_offsets=%r; using defaults %s",
                    sample_offsets,
                    DEFAULT_SAMPLE_OFFSETS,
                )

        self.requested_companies = 0
        self.successful_responses = 0
        self.failed_responses = 0
        self.items_found = 0

        self.floorsheet_saved = 0
        self.floorsheet_failed = 0

        # Dates this run targeted, recorded onto the CrawlRun.
        self.sampled_dates = []

        # (symbol, date) pairs that returned no transactions at all.
        self.missing_company_dates = []

        # Pages fetched per (symbol, date).
        self.page_counts = {}

    # ------------------------------------------------------------------
    # Date selection
    # ------------------------------------------------------------------

    def _target_dates(self):
        """
        Resolve which trading dates this run should collect.

        Every branch returns real trading sessions taken from stored
        ``DailyPrice`` data, so a weekend or holiday can never end up in
        the list.  Returns an empty list when no price history exists
        yet — the crawler then has nothing meaningful to anchor to, and
        says so rather than guessing at ``date.today()``.
        """
        if self.floorsheet_date:
            parsed = self._parse_date(self.floorsheet_date)
            return [parsed] if parsed else []

        if self.mode == "sample":
            return select_sample_dates(offsets=self.SAMPLE_OFFSETS)

        latest = latest_trading_date()
        return [latest] if latest else []

    @staticmethod
    def _parse_date(value):
        if isinstance(value, date):
            return value
        try:
            return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return None

    def _record_sampled_dates(self):
        """
        Persist the sampled dates onto the CrawlRun metadata.

        Without this you cannot later tell whether a broker's absence on
        a date means "did not trade" or "we never asked for that date".
        """
        crawl_run_id = getattr(self, "crawl_run_id", None)

        if not crawl_run_id:
            return

        try:
            from apps.crawler_runs.models import CrawlRun

            crawl_run = CrawlRun.objects.get(pk=crawl_run_id)
            metadata = dict(crawl_run.metadata or {})
            metadata["mode"] = self.mode
            metadata["sample_offsets"] = list(self.SAMPLE_OFFSETS)
            metadata["sampled_dates"] = [
                target.isoformat() for target in self.sampled_dates
            ]
            crawl_run.metadata = metadata
            crawl_run.save(update_fields=["metadata"])
        except Exception as exc:  # noqa: BLE001 - metadata must never break a crawl
            self.logger.warning("Could not record sampled_dates: %s", exc)

    # ------------------------------------------------------------------
    # Request generation
    # ------------------------------------------------------------------

    async def start(self):
        """Bridge Scrapy's async start hook to the Django-backed generator."""
        requests = await sync_to_async(list)(self.start_requests())
        for request in requests:
            yield request

    def start_requests(self):
        companies = Company.objects.filter(is_active=True).order_by("symbol")
        if self.company_symbol:
            companies = companies.filter(symbol__iexact=self.company_symbol)

        if self.COMPANY_LIMIT:
            companies = companies[: self.COMPANY_LIMIT]

        companies = list(companies)

        if not companies:
            self.logger.error("No active companies found in Company table.")
            return

        target_dates = self._target_dates()

        if not target_dates:
            self.logger.error(
                "No trading dates available for mode=%s. DailyPrice has no "
                "history to anchor the floorsheet sample to — run the "
                "trading_data crawler first.",
                self.mode,
            )
            return

        self.sampled_dates = list(target_dates)
        self._record_sampled_dates()

        self.logger.info(
            "FLOORSHEET PLAN | mode=%s | companies=%s | sampled_dates=%s",
            self.mode,
            len(companies),
            ", ".join(target.isoformat() for target in target_dates),
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
            "%s: CSRF token found. Requesting %s sampled date(s): %s",
            symbol,
            len(target_dates),
            ", ".join(target.isoformat() for target in target_dates),
        )

        for date_value in target_dates:
            yield from self.make_request(
                symbol=symbol,
                date=date_value,
                csrf_token=csrf_token,
                referer=response.url,
                start=0,
            )

    def make_request(
        self,
        symbol,
        date,
        csrf_token,
        referer,
        start=0,
    ):
        """
        Yield a POST for one symbol+date combination at the given offset.

        NOTE: the previous implementation iterated over dates but never
        put the date in the request body, so every "different date"
        request was byte-identical and the site returned the same rows
        each time.  The date is now sent both as a top-level ``date``
        parameter and as the DataTables column search on ``date_``;
        whichever the endpoint honours, the filter now actually applies.
        """
        date_text = date.isoformat() if hasattr(date, "isoformat") else str(date)

        data = {
            "draw": "1",
            "start": str(start),
            "length": str(self.PAGE_LENGTH),
            "search[value]": "",
            "search[regex]": "false",
            "company": symbol,
            "buyer": "",
            "seller": "",
            "date": date_text,
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
            data[f"columns[{index}][search][value]"] = (
                date_text if column == "date_" else ""
            )
            data[f"columns[{index}][search][regex]"] = "false"

        self.logger.info(
            "Floorsheet POST | symbol=%s | date=%s | start=%s",
            symbol,
            date_text,
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
        date_text = date.isoformat() if hasattr(date, "isoformat") else str(date)
        key = (symbol, date_text)
        self.page_counts[key] = self.page_counts.get(key, 0) + 1

        self.logger.info(
            "Floorsheet response | symbol=%s | HTTP=%s | date=%s | start=%s",
            symbol,
            response.status,
            date_text,
            start,
        )

        if response.status not in (200, 202):
            self.logger.error(
                "Floorsheet request failed for %s on %s: HTTP %s",
                symbol,
                date_text,
                response.status,
            )
            self.failed_responses += 1
            return

        if not response.text.strip():
            self.logger.error(
                "Empty floorsheet response for %s on %s", symbol, date_text
            )
            return

        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger.error(
                "Invalid JSON for %s on %s: %s",
                symbol,
                date_text,
                response.text[:3000],
            )
            return

        records_total = payload.get("recordsTotal", 0)
        records_filtered = payload.get("recordsFiltered", 0)
        rows = payload.get("data", []) or []

        self.logger.info(
            "%s | date=%s | recordsTotal=%s | recordsFiltered=%s | rows=%s",
            symbol,
            date_text,
            records_total,
            records_filtered,
            len(rows),
        )

        if not rows:
            # A company genuinely may not trade on a sampled date. Record
            # that explicitly instead of inventing a zero-volume row.
            if start == 0:
                self.missing_company_dates.append(key)
                self.logger.warning(
                    "NO FLOORSHEET DATA | company=%s | sampled_date=%s | "
                    "recorded as missing, no data invented",
                    symbol,
                    date_text,
                )
            return

        if start == 0 and isinstance(rows[0], dict):
            self.logger.info(
                "Floorsheet raw timestamp probe | symbol=%s | keys=%s | trade_time=%r | date_=%r",
                symbol,
                sorted(rows[0].keys()),
                rows[0].get("trade_time") or rows[0].get("tradeTime"),
                rows[0].get("date_"),
            )

        self.successful_responses += 1

        for row in rows:
            transaction_id = (
                row.get("contract_no")
                or row.get("transaction_id")
                or row.get("contract")
            )

            buyer_broker = row.get("buyer") or row.get("buyer_broker")
            seller_broker = row.get("seller") or row.get("seller_broker")
            quantity = row.get("quantity") or row.get("qty")
            rate = row.get("rate") or row.get("price")
            amount = row.get("amount") or row.get("turnover")
            transaction_date = row.get("date_") or row.get("date") or date_text
            transaction_trade_time = (
                row.get("trade_time")
                or row.get("tradeTime")
                or row.get("date_")
            )

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
                trade_time=transaction_trade_time,
                transaction_id=transaction_id,
                buyer_broker=buyer_broker,
                seller_broker=seller_broker,
                quantity=quantity,
                rate=rate,
                amount=amount,
                source=self.SOURCE,
            )

        # ------------------------------------------------------------------
        # Pagination within the same date.
        # ------------------------------------------------------------------
        try:
            total_records = int(records_filtered or records_total or 0)
        except (TypeError, ValueError):
            total_records = 0

        next_start = start + self.PAGE_LENGTH

        if self.page_counts[key] >= self.MAX_PAGES_PER_DATE:
            self.logger.warning(
                "%s on %s: MAX_PAGES_PER_DATE (%s) reached; stopping pagination.",
                symbol,
                date_text,
                self.MAX_PAGES_PER_DATE,
            )
            return

        if total_records > next_start and rows:
            self.logger.info(
                "%s: requesting next page start=%s of %s (date=%s)",
                symbol,
                next_start,
                total_records,
                date_text,
            )
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
        self.logger.info("=" * 60)
        self.logger.info("FLOORSHEET CRAWLER FINISHED - reason: %s", reason)
        self.logger.info("Mode                : %s", self.mode)
        self.logger.info(
            "Sampled dates       : %s",
            ", ".join(d.isoformat() for d in self.sampled_dates) or "(none)",
        )
        self.logger.info("Companies requested : %s", self.requested_companies)
        self.logger.info("Successful responses: %s", self.successful_responses)
        self.logger.info("Failed responses    : %s", self.failed_responses)
        self.logger.info("Items found         : %s", self.items_found)
        self.logger.info("Items saved         : %s", self.floorsheet_saved)
        self.logger.info("Items failed        : %s", self.floorsheet_failed)
        self.logger.info(
            "Company/date pairs with no data: %s",
            len(self.missing_company_dates),
        )
        for symbol, date_text in self.missing_company_dates:
            self.logger.info("  MISSING | %s | %s", symbol, date_text)
        self.logger.info("=" * 60)
