from django.core.management.base import BaseCommand, CommandError

from apps.companies.models import Company
from apps.market_intelligence.services.momentum import compute_momentum_snapshots


class Command(BaseCommand):
    help = (
        "Fill rsi_14 / macd / macd_signal / macd_hist on every CompanyTechnicalSnapshot row "
        "from crawled closes. Idempotent: only rows whose values change are written."
    )

    def add_arguments(self, parser):
        parser.add_argument("--symbols", help="Comma-separated symbols (default: every company with snapshots).")
        parser.add_argument("--dry-run", action="store_true", help="Count changes without writing.")

    def handle(self, *args, **options):
        company_ids = None
        if options["symbols"]:
            symbols = [s.strip().upper() for s in options["symbols"].split(",") if s.strip()]
            found = dict(Company.objects.filter(symbol__in=symbols).values_list("symbol", "id"))
            unknown = sorted(set(symbols) - set(found))
            if unknown:
                raise CommandError(f"Unknown symbols: {', '.join(unknown)}")
            company_ids = list(found.values())

        result = compute_momentum_snapshots(company_ids=company_ids, dry_run=options["dry_run"])
        verb = "Would update" if options["dry_run"] else "Updated"
        self.stdout.write(self.style.SUCCESS(
            f"{verb} {result['rows_updated']} rows across {result['companies']} companies "
            f"({result['rows_unchanged']} unchanged, {result['rows_without_price']} without a crawled close)."
        ))
        if result["failed"]:
            symbols = Company.objects.filter(id__in=result["failed"]).values_list("symbol", flat=True)
            self.stdout.write(self.style.ERROR(f"Failed (see log): {', '.join(symbols)}"))
