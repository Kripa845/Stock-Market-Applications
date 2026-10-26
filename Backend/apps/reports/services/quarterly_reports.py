"""
Market -> Quarterly Report: the latest quarterly filings of the tracked companies in one
sector, with valuation and dividend ratios (definitions: quarterly_metrics).

Filed figures come from QuarterlyReport / YearlyDPPS (``manage.py import_quarterly_reports``).
The price is the latest crawled close, MarketStockDaily or DailyPrice, whichever is newer
(the same rule as services/dividends.py; live and unverified prices are never used).

Caching.  The filed figures of one (sector, fiscal year, quarter) are cached for
CACHE_SECONDS; the prices are read on every request (one query) and the ratios rebuilt, so
PE / PB / yields always follow the latest close.  An import bumps the cache version, so a
revised filing shows at once.
"""

import time
from collections import defaultdict

from django.core.cache import cache
from django.db.models import OuterRef, Subquery

from apps.companies.models import Company
from apps.companies.services.selection import tracked_active_companies
from apps.market_data.models import DailyPrice
from apps.reports.models import QuarterlyReport, YearlyDPPS
from apps.market_indices.models import MarketStockDaily
from apps.market_indices.sectors import SECTOR_NAMES, SUB_INDICES, normalise_sector

from apps.reports.services import quarterly_metrics as metrics

PRICE_SOURCE = "crawled"
CACHE_SECONDS = 10 * 60
VERSION_KEY = "quarterly-report:version"

# Sub-index code ("BANKING") -> normalised sector name ("Banking").
SECTORS = {code: name for code, _, name in SUB_INDICES}


def sector_name_of(raw):
    return raw if raw in SECTOR_NAMES else normalise_sector(raw)


def sector_companies(sector_code):
    """Tracked, active companies whose (normalised) sector is ``sector_code``."""
    name = SECTORS[sector_code]
    return [company for company in tracked_active_companies() if sector_name_of(company.sector) == name]


def get_latest_prices(company_ids):
    """{company_id: (close, date)} from the latest crawled close; companies with none are left out."""
    market = (MarketStockDaily.objects
              .filter(symbol=OuterRef("symbol"), source=PRICE_SOURCE, close__isnull=False)
              .order_by("-date"))
    tracked = (DailyPrice.objects
               .filter(company_id=OuterRef("pk"), source=PRICE_SOURCE)
               .order_by("-date"))
    rows = (Company.objects.filter(pk__in=company_ids)
            .annotate(market_close=Subquery(market.values("close")[:1]),
                      market_close_date=Subquery(market.values("date")[:1]),
                      tracked_close=Subquery(tracked.values("close")[:1]),
                      tracked_close_date=Subquery(tracked.values("date")[:1]))
            .values("pk", "market_close", "market_close_date", "tracked_close", "tracked_close_date"))
    prices = {}
    for row in rows:
        candidates = [(row["market_close_date"], row["market_close"]), (row["tracked_close_date"], row["tracked_close"])]
        candidates = [c for c in candidates if c[0] and c[1] is not None]
        if candidates:
            day, close = max(candidates, key=lambda c: c[0])
            prices[row["pk"]] = (close, day)
    return prices


def periods(sector_code):
    """Fiscal years with filings in the sector, newest first, each with its quarters (newest first)."""
    ids = [company.pk for company in sector_companies(sector_code)]
    found = defaultdict(set)
    pairs = (QuarterlyReport.objects.filter(company_id__in=ids).order_by()
             .values_list("fiscal_year", "quarter").distinct())
    for fiscal_year, quarter in pairs:
        found[fiscal_year].add(quarter)
    return [
        {"fiscal_year": fiscal_year, "quarters": sorted(found[fiscal_year], reverse=True)}
        for fiscal_year in sorted(found, key=metrics.fiscal_year_start, reverse=True)
    ]


def resolve_period(sector_code, fiscal_year=None, quarter=None):
    """Fill a missing fiscal year / quarter with the latest one filed; (None, None) when nothing is."""
    if fiscal_year and quarter:
        return fiscal_year, quarter
    for period in periods(sector_code):
        if fiscal_year and period["fiscal_year"] != fiscal_year:
            continue
        if quarter and quarter not in period["quarters"]:
            continue
        return period["fiscal_year"], quarter or period["quarters"][0]
    return fiscal_year, quarter


def invalidate_cache():
    cache.set(VERSION_KEY, time.time_ns(), None)


def _filed_figures(sector_code, fiscal_year, quarter):
    """The price-independent part: reports, last year's reports and yearly DPPS, in 3 queries."""
    version = cache.get_or_set(VERSION_KEY, 1, None)
    key = f"quarterly-report:{version}:{sector_code}:{fiscal_year}:{quarter}"
    filed = cache.get(key)
    if filed is not None:
        return filed

    companies = sector_companies(sector_code)
    reports = list(QuarterlyReport.objects
                   .filter(company_id__in=[c.pk for c in companies], fiscal_year=fiscal_year, quarter=quarter)
                   .select_related("company"))
    reported_ids = [report.company_id for report in reports]
    previous = {
        report.company_id: report
        for report in QuarterlyReport.objects.filter(
            company_id__in=reported_ids, fiscal_year=metrics.previous_fiscal_year(fiscal_year), quarter=quarter,
        )
    }
    dpps = defaultdict(dict)
    for company_id, year, value in YearlyDPPS.objects.filter(company_id__in=reported_ids).values_list(
            "company_id", "fiscal_year", "dpps"):
        dpps[company_id][year] = value

    filed = {
        "total_companies": len(companies),
        "entries": [(report, previous.get(report.company_id), dict(dpps[report.company_id])) for report in reports],
    }
    cache.set(key, filed, CACHE_SECONDS)
    return filed


def quarterly_report(sector_code, fiscal_year=None, quarter=None):
    fiscal_year, quarter = resolve_period(sector_code, fiscal_year, quarter)
    meta = {
        "sector": sector_code,
        "sector_name": SECTORS[sector_code],
        "fiscal_year": fiscal_year,
        "quarter": quarter,
        "reported_count": 0,
        "total_companies": len(sector_companies(sector_code)),
        "avg_window": metrics.AVG_WINDOW_YEARS,
        "avg_min_years": metrics.AVG_MIN_YEARS,
    }
    if not fiscal_year or not quarter:
        return {"meta": meta, "results": []}

    filed = _filed_figures(sector_code, fiscal_year, quarter)
    prices = get_latest_prices([report.company_id for report, _, _ in filed["entries"]])
    results = []
    for report, previous, dpps_by_year in filed["entries"]:
        price, price_date = prices.get(report.company_id, (None, None))
        row = metrics.build_report_row(report, price, dpps_by_year, previous)
        results.append({**row, "logo_url": report.company.logo_url, "price_date": price_date})
    results.sort(key=lambda row: row["symbol"])

    meta.update(reported_count=len(results), total_companies=filed["total_companies"])
    return {"meta": meta, "results": results}


def fill_yearly_dpps(fiscal_year=None, company_ids=None):
    """
    Upsert YearlyDPPS from the quarter 4 (full-year) reports; returns (created, updated).
    Q4 reports without a DPPS (filed or derivable) leave the yearly value untouched.
    """
    reports = QuarterlyReport.objects.filter(quarter=4)
    if fiscal_year:
        reports = reports.filter(fiscal_year=fiscal_year)
    if company_ids is not None:
        reports = reports.filter(company_id__in=company_ids)
    created = updated = 0
    for report in reports:
        dpps = metrics.report_dpps(report)
        if dpps is None:
            continue
        _, was_created = YearlyDPPS.objects.update_or_create(
            company_id=report.company_id, fiscal_year=report.fiscal_year, defaults={"dpps": dpps},
        )
        created += int(was_created)
        updated += int(not was_created)
    if created or updated:
        invalidate_cache()
    return created, updated
