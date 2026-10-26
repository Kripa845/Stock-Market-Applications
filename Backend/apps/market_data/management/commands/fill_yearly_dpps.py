from django.core.management.base import BaseCommand, CommandError

from apps.market_data.services import quarterly_reports
from apps.market_data.services.dividends import normalise_fiscal_year


class Command(BaseCommand):
    help = "Fill YearlyDPPS from the quarter 4 (full-year) quarterly reports. import_quarterly_reports does this too."

    def add_arguments(self, parser):
        parser.add_argument("--fiscal-year", help="Only this fiscal year, e.g. 2082/83.")

    def handle(self, *args, **options):
        fiscal_year = None
        if options["fiscal_year"]:
            fiscal_year = normalise_fiscal_year(options["fiscal_year"])
            if not fiscal_year:
                raise CommandError("--fiscal-year must look like 2082/83.")
        created, updated = quarterly_reports.fill_yearly_dpps(fiscal_year=fiscal_year)
        self.stdout.write(self.style.SUCCESS(f"Yearly DPPS: {created} created, {updated} updated."))
