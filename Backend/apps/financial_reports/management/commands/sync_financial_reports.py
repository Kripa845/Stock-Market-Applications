"""
Sync financial reports from nepalipaisa.com for the tracked companies.

    python manage.py sync_financial_reports                # incremental, all tracked companies
    python manage.py sync_financial_reports --full         # crawl every page (use for the first run)
    python manage.py sync_financial_reports --symbol NABIL # one company only

Requires:  pip install requests
"""
import time
from datetime import datetime

import requests
from django.core.management.base import BaseCommand

from apps.companies.models import TrackedCompany
from apps.financial_reports.models import FinancialReport

API = "https://nepalipaisa.com/api/GetFinancialReportDocuments"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ReportsSync/1.0)",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://nepalipaisa.com/financial-report",
}
PER_PAGE = 10
MAX_PAGES = 300


def parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


class Command(BaseCommand):
    help = "Fetch financial reports for tracked companies from nepalipaisa.com (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--full", action="store_true",
                            help="Crawl all pages instead of stopping once nothing new is found.")
        parser.add_argument("--symbol", help="Only sync this symbol.")
        parser.add_argument("--delay", type=float, default=1.0,
                            help="Seconds to wait between requests (default 1).")

    def handle(self, *args, **opts):
        tracked = TrackedCompany.objects.filter(is_tracked=True).select_related("company")
        if opts["symbol"]:
            tracked = tracked.filter(company__symbol=opts["symbol"].upper())

        companies = [t.company for t in tracked]
        if not companies:
            self.stdout.write(self.style.WARNING("No tracked companies to sync."))
            return

        session = requests.Session()
        total_new = 0
        for i, company in enumerate(companies, 1):
            try:
                new = self.sync_company(session, company, opts["full"], opts["delay"])
            except RuntimeError as exc:
                self.stdout.write(self.style.ERROR(f"[{i}/{len(companies)}] {company.symbol}: {exc}"))
                continue
            total_new += new
            self.stdout.write(f"[{i}/{len(companies)}] {company.symbol}: {new} new")
            time.sleep(opts["delay"])

        self.stdout.write(self.style.SUCCESS(f"Done. {total_new} new reports."))

    def fetch_page(self, session, symbol, page):
        params = {
            "stockSymbol": symbol,
            "sectorCode": "",
            "fiscalYearId": 0,
            "reportCategoryId": 0,
            "pageNo": page,
            "itemsPerPage": PER_PAGE,
            "pagePerDisplay": 5,
        }
        last_error = None
        for attempt in range(3):
            try:
                resp = session.get(API, params=params, headers=HEADERS, timeout=30)
                resp.raise_for_status()
                return (resp.json().get("result") or {}).get("data") or []
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                time.sleep(2 * (attempt + 1))
        raise RuntimeError(f"page {page} failed: {last_error}")

    def sync_company(self, session, company, full, delay):
        new_count = 0
        for page in range(1, MAX_PAGES + 1):
            rows = self.fetch_page(session, company.symbol, page)
            if not rows:
                break

            page_new = 0
            for row in rows:
                # Safety: the API search is a text match, so keep exact symbol matches only.
                if (row.get("stockSymbol") or "").strip().upper() != company.symbol.upper():
                    continue
                _, created = FinancialReport.objects.update_or_create(
                    document_id=row["financialReportDocumentId"],
                    defaults={
                        "company": company,
                        "symbol": company.symbol,
                        "company_name": (row.get("companyName") or "").strip(),
                        "duration": row.get("categoryName") or "",
                        "fiscal_year_bs": row.get("fiscalYearBS") or "",
                        "fiscal_year_ad": row.get("fiscalYearAD") or "",
                        "report_date_bs": row.get("reportDateBS") or "",
                        "report_date_ad": parse_date(row.get("reportDateAD")),
                        "title": (row.get("reportName") or "").strip(),
                        "file_name": row.get("fileName") or "",
                        "is_active": bool(row.get("isActive", True)),
                    },
                )
                if created:
                    page_new += 1

            new_count += page_new
            # Newest-first results: a page with nothing new means we're caught up.
            if not full and page_new == 0:
                break
            if len(rows) < PER_PAGE:
                break
            time.sleep(delay)
        return new_count
