import time
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.companies.models import Company
from apps.companies.services.selection import parse_symbols, tracked_active_companies
from apps.floorsheet.models import FloorsheetTransaction
from apps.floorsheet.services.sharehub_floorsheet import PAUSE_SECONDS, ShareHubError, sync_company_day
from apps.market_data.services.trading_calendar import trading_dates


class Command(BaseCommand):
    help = (
        "Fill floorsheet history from ShareHub for each crawled trading day in a range, newest day first. "
        "Company-days that already have trades are skipped, so the command can be stopped and re-run."
    )

    def add_arguments(self, parser):
        parser.add_argument("--from", dest="start", required=True, help="oldest date, YYYY-MM-DD")
        parser.add_argument("--to", dest="end", help="newest date, YYYY-MM-DD (default: latest trading day)")
        parser.add_argument("--symbols", help="comma-separated symbols (default: tracked companies)")
        parser.add_argument("--refetch", action="store_true", help="also re-fetch company-days that already have trades")

    def handle(self, *args, **opts):
        try:
            start = date.fromisoformat(opts["start"])
            end = date.fromisoformat(opts["end"]) if opts["end"] else None
        except ValueError as exc:
            raise CommandError(f"Dates must be YYYY-MM-DD: {exc}")

        symbols = parse_symbols(opts["symbols"])
        companies = list(Company.objects.filter(symbol__in=symbols)) if symbols else list(tracked_active_companies())
        if not companies:
            raise CommandError("No companies selected.")

        # Real sessions come from crawled prices, never a weekday rule.
        days = [day for day in trading_dates(since=start) if end is None or day <= end]
        if not days:
            self.stdout.write(self.style.WARNING("No crawled trading days in that range."))
            return
        self.stdout.write(f"{len(days)} trading days x {len(companies)} companies, newest first")

        failures = 0
        for day in days:
            have = set(
                FloorsheetTransaction.objects.filter(date=day, company__in=companies)
                .exclude(transaction_id__startswith="TX-")
                .values_list("company_id", flat=True).distinct()
            )
            todo = companies if opts["refetch"] else [c for c in companies if c.pk not in have]
            if not todo:
                self.stdout.write(f"{day}: complete, skipping")
                continue
            found = created = 0
            for index, company in enumerate(todo):
                if index:
                    time.sleep(PAUSE_SECONDS)
                try:
                    counts = sync_company_day(company, day)
                except ShareHubError as exc:
                    failures += 1
                    self.stdout.write(self.style.WARNING(f"   {company.symbol}: {exc}"))
                    continue
                found += counts["found"]
                created += counts["created"]
            self.stdout.write(f"{day}: {len(todo)} companies fetched, {found} trades ({created} new)")
            time.sleep(PAUSE_SECONDS)

        if failures:
            self.stdout.write(self.style.WARNING(f"{failures} company-day(s) failed; re-run to retry them."))
        self.stdout.write(self.style.SUCCESS("Done."))
