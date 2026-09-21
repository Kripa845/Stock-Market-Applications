
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

import django
import scrapy
from asgiref.sync import sync_to_async


# ============================================================
# DJANGO SETUP
# ============================================================

# Django project root (contains manage.py).
BASE_DIR = Path(__file__).resolve().parents[3]

# Scrapy project root (contains scrapy.cfg). ``scrapy crawl`` puts this on
# sys.path itself, but adding it explicitly means this module can also be
# imported directly -- by the test suite, or by a management command --
# rather than only from inside a Scrapy process.
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
# Under ``scrapy crawl`` the Scrapy project root is on sys.path, so
# ``crawlers`` means Backend/crawlers/crawlers. Imported from Django
# (tests, management commands) ``crawlers`` means Backend/crawlers
# instead. Support both rather than only working inside Scrapy.
try:
    from crawlers.items import DailyTradingDataItem
except ModuleNotFoundError:  # pragma: no cover - import-path shim
    from crawlers.crawlers.items import DailyTradingDataItem


# ============================================================
# DATE / NUMBER PARSING
# ============================================================

#: The price-history endpoint returns ``published_date`` as an ISO date
#: string.  The extra formats below are tolerated so a formatting change
#: on the site degrades into a skipped row rather than a crashed crawl.
_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
)

_TAG_RE = re.compile(r"<[^>]+>")


def parse_trading_date(value):
    """
    Normalise one ``published_date`` cell into a ``datetime.date``.

    DataTables cells sometimes arrive wrapped in markup, so tags are
    stripped first.  Returns ``None`` for anything unparseable; callers
    skip the row rather than aborting the company.
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    text = _TAG_RE.sub(" ", str(value))
    text = " ".join(text.split()).strip()

    if not text:
        return None

    # Tolerate a trailing time component: "2026-09-18 00:00:00".
    candidate = text.split(" ")[0].split("T")[0]

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(candidate, fmt).date()
        except ValueError:
            continue

    return None


def parse_number(value):
    """Decimal from a possibly comma-formatted cell, or ``None``."""
    if value is None:
        return None

    text = _TAG_RE.sub(" ", str(value))
    text = text.replace(",", "").strip()

    if not text or text in {"-", "--", "N/A", "n/a"}:
        return None

    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


# ============================================================
# SPIDER
# ============================================================

class TradingDataSpider(scrapy.Spider):
    """
    Collects a genuine rolling one-month window of daily OHLCV +
    turnover history from ShareSansar, for every active company.

    Why this is date-driven, not row-count driven
    ---------------------------------------------
    The previous implementation asked for a fixed number of rows and
    treated that count as "one month".  It is not.  NEPSE trades a
    variable number of sessions per month — holidays, closures and
    suspensions all move the number, and a suspended company can have
    far fewer sessions than the market as a whole.  Any fixed row count
    is therefore either short of a month or wastefully long, and you
    cannot tell which without looking at the dates.

    So the window is defined by DATES and the row count falls out of it:

        target_end_date   = latest AVAILABLE trading date for the company
        target_start_date = target_end_date - WINDOW_DAYS calendar days

    ``target_end_date`` is read from the first page of the API response,
    NOT from ``date.today()``.  If the market last traded three days ago,
    today's date is not a trading date and anchoring to it would silently
    shorten the window by three days.

    Pagination
    ----------
    Pages of ``PAGE_SIZE`` rows are requested until the oldest row
    received reaches back past ``retrieval_start_date``, or until
    ``MAX_PAGES`` is hit.  ``MAX_PAGES`` is the safety limit that stops
    this from walking the entire historical database of a company.

    Retrieval buffer
    ----------------
    ``RETRIEVAL_BUFFER_DAYS`` extends how far back we FETCH, so that the
    window boundary is never decided by a page edge.  It does not extend
    the analysis window: rows are filtered back down to
    ``[target_start_date, target_end_date]`` before being emitted.  Rows
    that fall only in the buffer are discarded, never persisted.  Fetch
    range and final dataset range are deliberately separate.

    Completeness
    ------------
    Completeness is judged on UNIQUE TRADING DATES covered, never on a
    row count.  A company with 21 sessions in the window is complete; so
    is one with 22.  Neither 20 nor 30 rows means anything on its own.
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

    # Length of the rolling analysis window, in CALENDAR days.
    WINDOW_DAYS = 31

    # Rows requested per page.  50 is comfortably above one month of
    # sessions, so most companies finish in a single page, while still
    # being a polite request size.
    PAGE_SIZE = 50

    # Hard safety limit on pages per company.  At PAGE_SIZE=50 this caps
    # a single company at 300 rows (~14 months) even if the date logic
    # somehow never terminates.  It is a backstop, not the strategy.
    MAX_PAGES = 6

    # Fetch this many days past target_start_date so the window edge is
    # never truncated by a page boundary.  Retrieval only — see above.
    RETRIEVAL_BUFFER_DAYS = 5

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

    def __init__(self, window_days=None, max_pages=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if window_days is not None:
            try:
                self.WINDOW_DAYS = int(window_days)
            except (TypeError, ValueError):
                pass

        if max_pages is not None:
            try:
                self.MAX_PAGES = int(max_pages)
            except (TypeError, ValueError):
                pass

        # Counters consumed by the pipeline / CrawlRun.
        self.prices_found = 0
        self.prices_created = 0
        self.prices_updated = 0

        # Per-company pagination state, keyed by symbol.
        self.company_state = {}

    # ----------------------------------------------------------
    # REQUEST GENERATION
    # ----------------------------------------------------------

    async def start(self):
        """Bridge Scrapy's async start hook to the Django-backed generator."""
        requests = await sync_to_async(list)(self.start_requests())
        for request in requests:
            yield request

    def start_requests(self):
        companies = Company.objects.filter(
            is_active=True
        ).order_by("symbol")

        if not companies.exists():
            self.logger.error(
                "No active companies found in Company table."
            )
            return

        self.logger.info(
            "Found %s active companies to crawl "
            "(window=%s days, page_size=%s, max_pages=%s).",
            companies.count(),
            self.WINDOW_DAYS,
            self.PAGE_SIZE,
            self.MAX_PAGES,
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
        # Fresh pagination state for this company.
        # ------------------------------------------------------------------
        self.company_state[symbol] = {
            "company_id": company_id,
            "csrf_token": csrf_token,
            "referer": response.url,
            "rows_by_date": {},
            "rows_fetched": 0,
            "rows_invalid": 0,
            "pages_fetched": 0,
            "target_end_date": None,
            "target_start_date": None,
            "retrieval_start_date": None,
            "oldest_date_seen": None,
            "records_total": 0,
            "stop_reason": None,
        }

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
        """Build and yield a DataTables POST for price history at an offset."""
        form_data = self.build_form_data(
            company_id=company_id,
            start=start,
        )

        self.logger.info(
            "Sending price-history POST for %s (start=%s, length=%s)",
            symbol,
            start,
            self.PAGE_SIZE,
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

        The column list is unchanged from the working implementation —
        it mirrors what the site's own DataTables instance sends.  Only
        ``length`` changed, from a fixed 20 to ``PAGE_SIZE``, and it is
        now a PAGE size rather than the definition of the window.
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
            "length": str(self.PAGE_SIZE),
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

    # ----------------------------------------------------------
    # ROW EXTRACTION
    # ----------------------------------------------------------

    def extract_row(self, row, symbol):
        """
        Validate one API row into a normalised dict, or ``None``.

        Validates date, open, high, low, close, volume and turnover.  A
        row missing any of them is skipped and logged; it never raises,
        because one malformed row must not abort the company's crawl.
        """
        if not isinstance(row, dict):
            self.logger.warning("%s: non-dict row skipped: %r", symbol, row)
            return None

        trading_date = parse_trading_date(row.get("published_date"))

        if trading_date is None:
            self.logger.warning(
                "%s: unparseable published_date %r — row skipped",
                symbol,
                row.get("published_date"),
            )
            return None

        values = {
            "open": parse_number(row.get("open")),
            "high": parse_number(row.get("high")),
            "low": parse_number(row.get("low")),
            "close": parse_number(row.get("close")),
            "volume": parse_number(row.get("traded_quantity")),
            "turnover": parse_number(row.get("traded_amount")),
        }

        missing = [key for key, value in values.items() if value is None]

        if missing:
            self.logger.warning(
                "%s %s: missing/invalid field(s) %s — row skipped",
                symbol,
                trading_date,
                ", ".join(missing),
            )
            return None

        return {
            "date": trading_date,
            **values,
        }

    # ----------------------------------------------------------
    # RESPONSE HANDLING
    # ----------------------------------------------------------

    def parse_history(
        self,
        response,
        symbol,
        start,
    ):
        state = self.company_state.get(symbol)

        if state is None:
            self.logger.error("%s: no pagination state — aborting.", symbol)
            return

        self.logger.info(
            "Price history response for %s: HTTP %s (start=%s)",
            symbol,
            response.status,
            start,
        )

        if response.status not in (200, 202):
            self.logger.error("Price history failed for %s", symbol)
            state["stop_reason"] = f"http_{response.status}"
            yield from self._finalise(symbol)
            return

        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON for %s", symbol)
            self.logger.error(response.text[:3000])
            state["stop_reason"] = "invalid_json"
            yield from self._finalise(symbol)
            return

        records_total = payload.get("recordsTotal", 0)
        records_filtered = payload.get("recordsFiltered", 0)
        rows = payload.get("data", []) or []

        try:
            state["records_total"] = int(records_filtered or records_total or 0)
        except (TypeError, ValueError):
            state["records_total"] = 0

        state["pages_fetched"] += 1
        state["rows_fetched"] += len(rows)

        self.logger.info(
            "%s page %s | recordsTotal=%s recordsFiltered=%s rows_received=%s",
            symbol,
            state["pages_fetched"],
            records_total,
            records_filtered,
            len(rows),
        )

        if not rows:
            self.logger.warning(
                "No trading data returned for %s (start=%s)",
                symbol,
                start,
            )
            state["stop_reason"] = state["stop_reason"] or "no_more_rows"
            yield from self._finalise(symbol)
            return

        # ------------------------------------------------------------------
        # Normalise this page's rows.
        # ------------------------------------------------------------------
        parsed = []

        for row in rows:
            extracted = self.extract_row(row, symbol)

            if extracted is None:
                state["rows_invalid"] += 1
                continue

            parsed.append(extracted)

        if parsed:
            page_max = max(item["date"] for item in parsed)
            page_min = min(item["date"] for item in parsed)
        else:
            page_max = page_min = None

        # ------------------------------------------------------------------
        # Anchor the window on the FIRST page, using the latest date the
        # source actually has — never date.today().
        # ------------------------------------------------------------------
        if state["target_end_date"] is None and page_max is not None:
            state["target_end_date"] = page_max
            state["target_start_date"] = page_max - timedelta(
                days=self.WINDOW_DAYS
            )
            state["retrieval_start_date"] = (
                state["target_start_date"]
                - timedelta(days=self.RETRIEVAL_BUFFER_DAYS)
            )

            self.logger.info(
                "%s | latest available trading date=%s | "
                "target window %s .. %s | retrieval floor=%s",
                symbol,
                state["target_end_date"],
                state["target_start_date"],
                state["target_end_date"],
                state["retrieval_start_date"],
            )

        # ------------------------------------------------------------------
        # Accumulate, de-duplicating by trading date.  The API can repeat
        # a row across page boundaries; first occurrence wins.
        # ------------------------------------------------------------------
        for item in parsed:
            state["rows_by_date"].setdefault(item["date"], item)

        if page_min is not None:
            if state["oldest_date_seen"] is None:
                state["oldest_date_seen"] = page_min
            else:
                state["oldest_date_seen"] = min(
                    state["oldest_date_seen"],
                    page_min,
                )

        # ------------------------------------------------------------------
        # Should we ask for another page?
        # ------------------------------------------------------------------
        next_start = start + self.PAGE_SIZE

        reached_window = (
            state["retrieval_start_date"] is not None
            and state["oldest_date_seen"] is not None
            and state["oldest_date_seen"] <= state["retrieval_start_date"]
        )

        exhausted = (
            state["records_total"] > 0
            and next_start >= state["records_total"]
        )

        hit_page_cap = state["pages_fetched"] >= self.MAX_PAGES

        if reached_window:
            state["stop_reason"] = "window_covered"
        elif exhausted:
            state["stop_reason"] = "source_exhausted"
        elif hit_page_cap:
            state["stop_reason"] = "max_pages_reached"
            self.logger.warning(
                "%s: MAX_PAGES (%s) reached before covering the window; "
                "dataset may be incomplete.",
                symbol,
                self.MAX_PAGES,
            )

        if state["stop_reason"]:
            yield from self._finalise(symbol)
            return

        self.logger.info(
            "%s: window not yet covered (oldest=%s > floor=%s) — "
            "fetching page %s (start=%s of %s)",
            symbol,
            state["oldest_date_seen"],
            state["retrieval_start_date"],
            state["pages_fetched"] + 1,
            next_start,
            state["records_total"],
        )

        yield from self._make_price_request(
            symbol=symbol,
            company_id=state["company_id"],
            csrf_token=state["csrf_token"],
            referer=state["referer"],
            start=next_start,
        )

    # ----------------------------------------------------------
    # FINALISATION
    # ----------------------------------------------------------

    def _finalise(self, symbol):
        """
        Filter the retrieved buffer down to the real target window and
        emit items, then log the per-company audit line.
        """
        state = self.company_state.get(symbol)

        if state is None:
            return

        target_start = state["target_start_date"]
        target_end = state["target_end_date"]

        all_rows = state["rows_by_date"]

        if target_start is None or target_end is None:
            in_range = []
        else:
            in_range = [
                row
                for row_date, row in all_rows.items()
                if target_start <= row_date <= target_end
            ]

        in_range.sort(key=lambda item: item["date"], reverse=True)

        # Unique trading dates is the only meaningful measure of coverage.
        unique_dates = sorted({row["date"] for row in in_range})

        covered = (
            state["stop_reason"] in {"window_covered", "source_exhausted"}
            and bool(unique_dates)
        )

        if not unique_dates:
            completeness = "EMPTY"
        elif covered:
            completeness = "COMPLETE"
        else:
            completeness = "PARTIAL"

        self.logger.info(
            "TRADING WINDOW SUMMARY | company=%s | "
            "target_start_date=%s | target_end_date=%s | "
            "pages_fetched=%s | rows_fetched=%s | rows_in_range=%s | "
            "unique_trading_dates=%s | rows_skipped=%s | "
            "buffered_rows_discarded=%s | stop_reason=%s | completeness=%s",
            symbol,
            target_start,
            target_end,
            state["pages_fetched"],
            state["rows_fetched"],
            len(in_range),
            len(unique_dates),
            state["rows_invalid"],
            len(all_rows) - len(in_range),
            state["stop_reason"],
            completeness,
        )

        for row in in_range:
            yield DailyTradingDataItem(
                item_type="daily_price",
                company=symbol,
                date=row["date"].isoformat(),
                open=str(row["open"]),
                high=str(row["high"]),
                low=str(row["low"]),
                close=str(row["close"]),
                volume=str(row["volume"]),
                turnover=str(row["turnover"]),
                source=self.SOURCE,
            )

        # Release the buffer; the company is done.
        self.company_state.pop(symbol, None)

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
