"""
Crawl the latest quarterly reports of the tracked companies from nepsetrading.com's Latest
Report pages (services/nepsetrading.py).  Idempotent: re-runs update the same rows.  Also runs
daily from Celery beat (apps.reports.tasks.crawl_quarterly_reports).

    python manage.py crawl_quarterly_reports [--sector BANKING ...] [--dry-run]
"""

from django.core.management.base import BaseCommand, CommandError

from apps.reports.services import nepsetrading


class Command(BaseCommand):
    help = "Crawl the latest quarterly reports of the tracked companies from nepsetrading.com."

    def add_arguments(self, parser):
        parser.add_argument("--sector", action="append", help="Sector code, e.g. BANKING; repeatable. Default: all.")
        parser.add_argument("--dry-run", action="store_true", help="Fetch and match without saving.")

    def handle(self, *args, **options):
        sectors = [s.strip().upper() for s in options["sector"] or []]
        unknown = [s for s in sectors if s not in nepsetrading.SECTORS]
        if unknown:
            raise CommandError(f"--sector must be one of {nepsetrading.SECTORS} (got {', '.join(unknown)}).")

        results = nepsetrading.crawl(sectors or None, dry_run=options["dry_run"])
        for r in results:
            if r.error:
                self.stderr.write(self.style.WARNING(f"{r.sector}: failed ({r.error})"))
            else:
                self.stdout.write(f"{r.sector}: Q{r.quarter} {r.fiscal_year}, {r.listed} listed, "
                                  f"{len(r.symbols)} tracked ({r.created} new, {r.updated} updated)")

        prefix = "[dry run, nothing saved] " if options["dry_run"] else ""
        saved = sum(len(r.symbols) for r in results)
        failed = sum(1 for r in results if r.error)
        self.stdout.write(self.style.SUCCESS(f"{prefix}{saved} reports saved, {failed} sector page(s) failed."))
