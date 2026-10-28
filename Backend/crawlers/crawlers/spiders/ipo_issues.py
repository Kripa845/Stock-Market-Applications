"""
Public issues (IPO, FPO, right share, mutual fund, debenture ...) from ShareSansar's
"Existing Issues" page, for every company.  Each tab is a DataTables table served as JSON
from the same URL with ``?type=<n>`` (types: apps.reports.services.ipo_issues.SHARESANSAR_TYPES).

    scrapy crawl ipo_issues                  latest 2 pages (100 issues) per type
    scrapy crawl ipo_issues -a pages=all     full history (backfill)
"""

import json
import re
from datetime import date
from urllib.parse import urlencode

import scrapy
from w3lib.html import remove_tags

from crawlers.items import IpoIssueItem
from crawlers.market_wide_pipeline import _ensure_django, parse_decimal

START_URL = "https://www.sharesansar.com/existing-issues"
PAGE_SIZE = 50
DEFAULT_PAGES = 2
DATE_REGEX = re.compile(r"(\d{4}-\d{2}-\d{2})")
AJAX_HEADERS = {"X-Requested-With": "XMLHttpRequest", "Accept": "application/json, text/javascript, */*"}


def _date(value):
    match = DATE_REGEX.search(str(value or ""))
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def _text(html):
    return re.sub(r"\s+", " ", remove_tags(str(html or ""))).strip()


def _int(value):
    number = parse_decimal(value)
    return None if number is None else int(number)


def _source_types():
    _ensure_django()
    from apps.reports.services.ipo_issues import SHARESANSAR_TYPES, issue_source_id

    return SHARESANSAR_TYPES, issue_source_id


class IpoIssuesSpider(scrapy.Spider):
    name = "ipo_issues"
    source = "ShareSansar"
    allowed_domains = ["sharesansar.com", "www.sharesansar.com"]
    custom_settings = {
        "ITEM_PIPELINES": {
            "crawlers.pipelines.CrawlRunPipeline": 100,
            "crawlers.ipo_pipeline.IpoIssuePipeline": 450,
        },
    }

    def __init__(self, url=None, pages=None, **kwargs):
        super().__init__(**kwargs)
        self.start_url = url or START_URL
        if str(pages).lower() == "all":
            self.max_pages = None
        else:
            try:
                self.max_pages = max(int(pages), 1)
            except (TypeError, ValueError):
                self.max_pages = DEFAULT_PAGES
        self.types, self.source_id = _source_types()

    async def start(self):
        # Scrapy >= 2.13 calls start(), not start_requests() (as in spiders/dividends.py).
        for request in self.start_requests():
            yield request

    def start_requests(self):
        for type_id in self.types:
            yield self._page_request(type_id, start=0)

    def _page_request(self, type_id, start):
        params = {"type": type_id, "draw": "1", "start": str(start), "length": str(PAGE_SIZE)}
        return scrapy.Request(
            f"{self.start_url}?{urlencode(params)}",
            headers=AJAX_HEADERS,
            callback=self.parse_page,
            cb_kwargs={"type_id": type_id, "start": start},
            dont_filter=True,
        )

    def parse_page(self, response, type_id, start):
        issue_type = self.types[type_id]
        try:
            payload = json.loads(response.text)
            rows = payload["data"]
            total = int(payload.get("recordsFiltered") or payload.get("recordsTotal") or 0)
        except (ValueError, KeyError, TypeError):
            self.logger.error("%s: unexpected response at start=%s (%s): endpoint changed",
                              issue_type, start, response.text[:200])
            return

        for row in rows:
            company = row.get("company") or {}
            units = _int(row.get("total_units"))
            yield IpoIssueItem(
                issue_type=str(issue_type),
                source_id=self.source_id(issue_type, row.get("companyid") or company.get("id"), units),
                symbol=_text(company.get("symbol")).upper(),
                company_name=_text(company.get("companyname")),
                units=units,
                price=row.get("issue_price"),
                ratio=row.get("ratio_value") or "",
                issue_manager=row.get("issue_manager") or "",
                open_date=_date(row.get("opening_date")),
                close_date=_date(row.get("closing_date")),
                final_date=_date(row.get("final_date")),
                listing_date=_date(row.get("listing_date")),
                source_status=_int(row.get("status")),
                announcement_url=row.get("announcement_link") or "",
                source=self.source,
            )

        if start == 0:
            self.logger.info("ipo_issues %s: %s rows", issue_type, total)
            last = total if self.max_pages is None else min(total, self.max_pages * PAGE_SIZE)
            for next_start in range(PAGE_SIZE, last, PAGE_SIZE):
                yield self._page_request(type_id, next_start)
