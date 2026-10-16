"""
Proposed dividends (bonus % / cash %) for the tracked companies, per fiscal year.

Source: ShareSansar "Proposed Dividend" (checked against the live page 2026-10-15).
The table is drawn by DataTables from a JSON endpoint on the same URL, so no browser is
needed.  The spider loads the page once (session cookie + the fiscal-year <select>), then
pages through
    GET /proposed-dividend?type=YEARWISE&year=<id>&sector=0&start=<n>&length=50
with ``X-Requested-With: XMLHttpRequest``.  The server answers an empty result when
length > 50, and a 500 unless every DataTables column is listed (COLUMNS).
    fiscal years   <select id="year"> options: value = ShareSansar id, text = "2082/2083"
    row keys       symbol / companyname (HTML links), bonus_share, cash_dividend, year,
                   announcement_date, bookclose_date ("2026-07-03 [Closed]"),
                   distribution_date, bonus_listing_date, id
The endpoint has no symbol filter, so every page is read, but only rows for active, tracked
companies are yielded (-a scope=all keeps every listed company, and rows without a symbol).
Then, once per kept symbol (-a fundamentals=0 skips both):
    ShareSansar /company/<symbol>        "Paid Up  Rs. 100.00"            -> CompanyFaceValueItem
    Merolagani CompanyDetail.aspx        "EPS  27.01 (FY:082-083, Q:4)"   -> CompanyEpsItem
With scope=all a row without a symbol or fiscal year is still yielded: the pipeline stores it marked.

Respects the project's ROBOTSTXT_OBEY = True.  Manual run:
    scrapy crawl dividends                  # tracked companies, the latest 2 fiscal years
    scrapy crawl dividends -a years=5
    scrapy crawl dividends -a years=all -a fundamentals=0
    scrapy crawl dividends -a scope=all     # every listed company
"""

import json
import re
from datetime import date
from urllib.parse import urlencode

import scrapy
from asgiref.sync import sync_to_async
from w3lib.html import remove_tags

from crawlers.items import CompanyEpsItem, CompanyFaceValueItem, DividendItem
from crawlers.market_wide_pipeline import _ensure_django

START_URL = "https://www.sharesansar.com/proposed-dividend"
COMPANY_URL = "https://www.sharesansar.com/company/{symbol}"
EPS_URL = "https://merolagani.com/CompanyDetail.aspx?symbol={symbol}"
PAGE_SIZE = 50
DEFAULT_YEARS = 2

YEAR_OPTIONS_SELECTOR = "select#year option"
FISCAL_YEAR_TEXT = re.compile(r"^\s*(\d{4}/\d{4})\s*$")
DATE_REGEX = re.compile(r"(\d{4}-\d{2}-\d{2})")
FACE_VALUE_XPATH = '//table[@id="myTableCInfo"]//tr[td[1][normalize-space()="Paid Up"]]/td[2]//text()'
EPS_XPATH = '//th[normalize-space()="EPS"]/following-sibling::td[1]//text()'
EPS_REGEX = re.compile(r"(-?[\d,]+(?:\.\d+)?)\s*\(\s*FY\s*:\s*(\d{3}-\d{3})\s*,\s*Q\s*:\s*(\d)\s*\)")
NUMBER_REGEX = re.compile(r"-?[\d,]+(?:\.\d+)?")

# DataTables columns in the page's order (the order[0][column] index refers to these).
COLUMNS = [
    "DT_Row_Index", "symbol", "companyname", "bonus_share", "cash_dividend", "total_dividend",
    "announcement_date", "bookclose_date", "distribution_date", "bonus_listing_date", "year",
]
AJAX_HEADERS = {"X-Requested-With": "XMLHttpRequest", "Accept": "application/json, text/javascript, */*"}


def _date(value):
    """'2026-07-03 [Closed]' -> date; '', None, garbage -> None."""
    match = DATE_REGEX.search(str(value or ""))
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def _text(html):
    return re.sub(r"\s+", " ", remove_tags(str(html or ""))).strip()


def _tracked_symbols():
    _ensure_django()
    from apps.companies.selection import tracked_active_companies

    return {symbol.upper() for symbol in tracked_active_companies().values_list("symbol", flat=True)}


class DividendsSpider(scrapy.Spider):
    name = "dividends"
    source = "ShareSansar"
    allowed_domains = ["sharesansar.com", "www.sharesansar.com", "merolagani.com"]
    custom_settings = {
        "ITEM_PIPELINES": {
            "crawlers.pipelines.CrawlRunPipeline": 100,
            "crawlers.dividend_pipeline.DividendPipeline": 450,
        },
    }

    def __init__(self, url=None, years=None, fundamentals=None, scope=None, **kwargs):
        super().__init__(**kwargs)
        self.start_url = url or START_URL
        self.max_years = None if str(years).lower() == "all" else self._positive_int(years, DEFAULT_YEARS)
        self.fetch_fundamentals = str(fundamentals if fundamentals is not None else "1").lower() not in ("0", "false", "no")
        self.tracked_only = str(scope or "tracked").lower() != "all"
        # Filled in start(); None = keep every row (scope=all, or parse_page called directly).
        self.tracked_symbols = None
        self.seen_symbols = set()

    @staticmethod
    def _positive_int(value, default):
        try:
            value = int(value)
        except (TypeError, ValueError):
            return default
        return value if value > 0 else default

    async def start(self):
        # Scrapy >= 2.13 calls start(), not start_requests().
        if self.tracked_only:
            self.tracked_symbols = await sync_to_async(_tracked_symbols)()
            if not self.tracked_symbols:
                self.logger.error("No active, tracked companies: nothing to crawl (use -a scope=all for every company).")
                return
            self.logger.info("dividends: %s tracked companies", len(self.tracked_symbols))
        for request in self.start_requests():
            yield request

    def start_requests(self):
        yield scrapy.Request(self.start_url, callback=self.parse)

    # ------------------------------------------------------------------

    def parse(self, response):
        years = self._fiscal_years(response)
        if not years:
            self.logger.error("No fiscal years in %r: page layout changed. Nothing saved.", YEAR_OPTIONS_SELECTOR)
            return
        self.logger.info("dividends: fiscal years %s", [label for _, label in years])
        for year_id, label in years:
            yield self._page_request(year_id, label, start=0)

    def _fiscal_years(self, response):
        years = []
        for option in response.css(YEAR_OPTIONS_SELECTOR):
            match = FISCAL_YEAR_TEXT.match(" ".join(option.css("::text").getall()))
            value = (option.attrib.get("value") or "").strip()
            if match and value:
                years.append((value, match.group(1)))
        years.sort(key=lambda year: year[1], reverse=True)
        return years if self.max_years is None else years[: self.max_years]

    def _page_request(self, year_id, label, start):
        params = {
            "draw": "1", "start": str(start), "length": str(PAGE_SIZE),
            "order[0][column]": "6", "order[0][dir]": "desc",
            "type": "YEARWISE", "year": year_id, "sector": "0",
        }
        # Only columns[i][data] is required; the full DataTables spec passes Scrapy's 2083-char URL limit.
        params.update({f"columns[{position}][data]": data for position, data in enumerate(COLUMNS)})
        return scrapy.Request(
            f"{self.start_url}?{urlencode(params)}",
            headers=AJAX_HEADERS,
            callback=self.parse_page,
            cb_kwargs={"year_id": year_id, "label": label, "start": start},
            dont_filter=True,
        )

    def parse_page(self, response, year_id, label, start):
        try:
            payload = json.loads(response.text)
            rows = payload["data"]
            total = int(payload.get("recordsFiltered") or payload.get("recordsTotal") or 0)
        except (ValueError, KeyError, TypeError):
            self.logger.error("%s: unexpected response at start=%s (%s): endpoint changed", label, start, response.text[:200])
            return

        for row in rows:
            symbol = _text(row.get("symbol")).upper()
            if self.tracked_symbols is not None and symbol not in self.tracked_symbols:
                continue
            yield DividendItem(
                item_type="dividend",
                source_id=str(row.get("id") or ""),
                symbol=symbol,
                company_name=_text(row.get("companyname")),
                fiscal_year=_text(row.get("year")),
                bonus_pct=row.get("bonus_share"),
                cash_pct=row.get("cash_dividend"),
                announcement_date=_date(row.get("announcement_date")),
                book_closure_date=_date(row.get("bookclose_date")),
                distribution_date=_date(row.get("distribution_date")),
                bonus_listing_date=_date(row.get("bonus_listing_date")),
                source=self.source,
            )
            if self.fetch_fundamentals and symbol and symbol not in self.seen_symbols:
                self.seen_symbols.add(symbol)
                yield scrapy.Request(COMPANY_URL.format(symbol=symbol.lower()), callback=self.parse_face_value,
                                     cb_kwargs={"symbol": symbol})
                yield scrapy.Request(EPS_URL.format(symbol=symbol), callback=self.parse_eps,
                                     cb_kwargs={"symbol": symbol})

        if start == 0:
            self.logger.info("dividends %s: %s rows", label, total)
            for next_start in range(PAGE_SIZE, total, PAGE_SIZE):
                yield self._page_request(year_id, label, next_start)

    # ------------------------------------------------------------------

    def parse_face_value(self, response, symbol):
        match = NUMBER_REGEX.search(" ".join(response.xpath(FACE_VALUE_XPATH).getall()))
        if not match:
            self.logger.warning("%s: no 'Paid Up' value on %s", symbol, response.url)
            return
        yield CompanyFaceValueItem(item_type="company_face_value", symbol=symbol,
                                   face_value=match.group(0), source="ShareSansar")

    def parse_eps(self, response, symbol):
        text = re.sub(r"\s+", " ", " ".join(response.xpath(EPS_XPATH).getall()))
        match = EPS_REGEX.search(text)
        if not match:
            self.logger.warning("%s: EPS with fiscal year / quarter not found on %s (%r)", symbol, response.url, text[:80])
            return
        eps, fiscal_year, quarter = match.groups()
        if not 1 <= int(quarter) <= 4:
            # Mutual funds show a placeholder "0.00 (FY:083-084, Q:5)": they report NAV, not EPS.
            self.logger.info("%s: no EPS (placeholder %r), payout ratio stays empty", symbol, text.strip())
            return
        yield CompanyEpsItem(item_type="company_eps", symbol=symbol, fiscal_year=fiscal_year,
                             quarter=int(quarter), eps=eps, source="Merolagani")
