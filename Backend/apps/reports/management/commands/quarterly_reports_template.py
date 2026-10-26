"""
Write a blank CSV for import_quarterly_reports with one row per tracked company, grouped
by sector, so a newly tracked company shows up in the template.  Fiscal year and quarter
are left blank: an unfilled row is skipped by the import instead of saving an empty report.
The trailing sector / name columns are for reference; the import ignores them.

Tracked companies whose sector label is not recognised are listed: they would appear in no
sector tab until their sector is fixed (Admin -> Companies) or SECTOR_MAP is extended.

    python manage.py quarterly_reports_template [--sector HYDROPOWER] [--output path.csv] [--force]
"""

import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.companies.services.selection import tracked_active_companies
from apps.reports.services import quarterly_reports

COLUMNS = ["symbol", "fiscal_year", "quarter", "reported_on", "net_profit", "net_worth", "distributable_profit",
           "share_count", "eps", "book_value", "dpps", "price_on_report_date", "sector", "name"]


class Command(BaseCommand):
    help = "Write a blank quarterly report CSV listing every tracked company, grouped by sector."

    def add_arguments(self, parser):
        parser.add_argument("--output", default=str(Path(settings.BASE_DIR) / "data" / "quarterly_reports_template.csv"))
        parser.add_argument("--sector", help="Only this sector code, e.g. HYDROPOWER.")
        parser.add_argument("--force", action="store_true", help="Overwrite the output file if it exists.")

    def handle(self, *args, **options):
        sector = (options["sector"] or "").strip().upper() or None
        if sector and sector not in quarterly_reports.SECTORS:
            raise CommandError(f"--sector must be one of {sorted(quarterly_reports.SECTORS)}.")
        output = Path(options["output"])
        if output.exists() and not options["force"]:
            raise CommandError(f"{output} exists (it may hold figures you typed); pass --force or another --output.")

        order = list(quarterly_reports.SECTORS.values())
        rows, unknown = [], []
        for company in tracked_active_companies():
            name = quarterly_reports.sector_name_of(company.sector)
            if name is None:
                unknown.append(f"{company.symbol} ({company.sector!r})")
                continue
            if sector and name != quarterly_reports.SECTORS[sector]:
                continue
            rows.append((order.index(name), company.symbol, name, company.name))
        rows.sort()

        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS)
            writer.writeheader()
            for _, symbol, name, company_name in rows:
                writer.writerow({"symbol": symbol, "sector": name, "name": company_name})

        per_sector = {}
        for _, _, name, _ in rows:
            per_sector[name] = per_sector.get(name, 0) + 1
        summary = ", ".join(f"{name} {count}" for name, count in per_sector.items())
        self.stdout.write(self.style.SUCCESS(f"Wrote {len(rows)} companies to {output} ({summary})."))
        if unknown:
            self.stderr.write(self.style.WARNING(
                "Not in any sector tab (unrecognised sector label): " + ", ".join(unknown)))
