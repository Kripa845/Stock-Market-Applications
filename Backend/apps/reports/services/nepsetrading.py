"""
Latest quarterly reports from nepsetrading.com (Stock Analysis -> Latest Report), one page
per sector: https://nepsetrading.com/stockanalysis/latest-report/<sector>.

The pages are Next.js server components: the table rows ship as JSON inside the
``self.__next_f.push([1, "..."])`` script chunks, so no HTML table parsing is needed.  Each row
has eps, book_value, dpps, dpps_avg5 (+ years used) and dpps_prev; the page heading gives the
period ("Q4 2082/83").  nepsetrading's own LTP / PE / PB / yields are not stored: ours follow
our latest crawled close (services/quarterly_reports.py).

Only tracked, active companies are saved, matched on symbol whatever page they are on.  Rows
upsert on (company, fiscal year, quarter) and only the crawled columns are written, so the
CSV-only figures (net profit, share count, ...) of a hand-imported row are kept.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

import requests
from django.db import transaction
from django.utils import timezone

from apps.companies.services.selection import tracked_active_companies
from apps.reports.models import QuarterlyReport
from apps.reports.services import quarterly_reports
from apps.reports.services.dividends import normalise_fiscal_year

logger = logging.getLogger(__name__)

SOURCE = "nepsetrading"
BASE_URL = "https://nepsetrading.com/stockanalysis/latest-report/{slug}"
TIMEOUT = 30
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"}

# nepsetrading has a page for every sub-index except mutual funds; the slug is the code lower-cased.
SECTORS = [code for code in quarterly_reports.SECTORS if code != "MUTUAL"]

FLIGHT_CHUNK = re.compile(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)')
PERIOD = re.compile(r'"children":"Q([1-4]) (\d{4}/\d{2,4})"')


class PageError(ValueError):
    """The page did not have the period or the rows where expected (layout changed?)."""


@dataclass
class SectorResult:
    sector: str
    fiscal_year: str | None = None
    quarter: int | None = None
    listed: int = 0
    created: int = 0
    updated: int = 0
    error: str | None = None
    symbols: list = field(default_factory=list)


def _decimal(value):
    if value is None or value == "":
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return None
    return number.quantize(Decimal("0.01")) if number.is_finite() else None


def parse_page(html):
    """Page HTML -> (fiscal_year "2082/2083", quarter, rows); raises PageError."""
    payload = "".join(json.loads(f'"{chunk}"') for chunk in FLIGHT_CHUNK.findall(html))
    period = PERIOD.search(payload)
    fiscal_year = normalise_fiscal_year(period.group(2)) if period else ""
    if not fiscal_year:
        raise PageError("no 'Q<n> <fiscal year>' heading")

    start = payload.find('"rows":[')
    if start < 0:
        raise PageError("no rows in the page data")
    try:
        rows, _ = json.JSONDecoder().raw_decode(payload, start + len('"rows":'))
    except ValueError as exc:
        raise PageError(f"rows are not valid JSON ({exc})") from None
    return fiscal_year, int(period.group(1)), [row for row in rows if isinstance(row, dict) and row.get("symbol")]


def fetch_page(sector, session=None):
    response = (session or requests).get(BASE_URL.format(slug=sector.lower()), headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    return response.text


def row_defaults(row, scraped_at):
    years = row.get("dpps_avg5_years")
    return {
        "eps": _decimal(row.get("eps")),
        "book_value": _decimal(row.get("book_value")),
        "dpps": _decimal(row.get("dpps")),
        "dpps_avg": _decimal(row.get("dpps_avg5")),
        "dpps_avg_years": years if isinstance(years, int) and years > 0 else None,
        "previous_dpps": _decimal(row.get("dpps_prev")),
        "source": SOURCE,
        "scraped_at": scraped_at,
    }


def save_rows(sector, fiscal_year, quarter, rows, companies, scraped_at=None):
    """Upsert the tracked companies among ``rows``; returns a SectorResult."""
    scraped_at = scraped_at or timezone.now()
    result = SectorResult(sector, fiscal_year, quarter, listed=len(rows))
    for row in rows:
        company = companies.get(str(row["symbol"]).strip().upper())
        if company is None:
            continue
        _, created = QuarterlyReport.objects.update_or_create(
            company=company, fiscal_year=fiscal_year, quarter=quarter, defaults=row_defaults(row, scraped_at),
        )
        result.created += int(created)
        result.updated += int(not created)
        result.symbols.append(company.symbol)
    return result


def crawl(sectors=None, dry_run=False, fetch=fetch_page):
    """
    Fetch and save the given sector codes (default: all).  A failing page is logged and
    reported in its SectorResult; the other sectors still run.
    """
    companies = {company.symbol: company for company in tracked_active_companies()}
    results = []
    q4_company_ids = set()
    session = requests.Session()
    with transaction.atomic():
        for sector in sectors or SECTORS:
            try:
                fiscal_year, quarter, rows = parse_page(fetch(sector, session))
            except (requests.RequestException, PageError) as exc:
                logger.warning("nepsetrading latest report %s failed: %s", sector, exc)
                results.append(SectorResult(sector, error=str(exc)))
                continue
            result = save_rows(sector, fiscal_year, quarter, rows, companies)
            results.append(result)
            if quarter == 4:
                q4_company_ids.update(companies[symbol].pk for symbol in result.symbols)

        if q4_company_ids:
            quarterly_reports.fill_yearly_dpps(company_ids=q4_company_ids)
        if dry_run:
            transaction.set_rollback(True)
    if not dry_run:
        quarterly_reports.invalidate_cache()
    return results
