from django.core.management.base import BaseCommand

from apps.market_intelligence.services.snapshots import compute_market_snapshots


class Command(BaseCommand):
    help = "Idempotently compute market intelligence snapshots for all DailyPrice dates."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report valid sessions and exclusions without writing snapshots.",
        )

    def handle(self, *args, **options):
        result = compute_market_snapshots(dry_run=options["dry_run"])
        excluded = result["excluded_dates"]
        mode = "Would compute" if options["dry_run"] else "Computed"
        if not options["dry_run"]:
            from apps.market_intelligence.services.sector_rotation import compute_sector_rotation_snapshots
            from apps.market_intelligence.services.technicals import compute_company_technical_snapshots

            result["technicals"] = compute_company_technical_snapshots()
            result["sectors"] = compute_sector_rotation_snapshots()
        self.stdout.write(self.style.SUCCESS(
            "{mode} {sessions} market sessions ({breadth} breadth, {proxy} proxy index rows)."
            .format(mode=mode, **result)
        ))
        if not options["dry_run"]:
            self.stdout.write(
                f"Technical snapshots: {result['technicals']['snapshots']}; "
                f"sector snapshots: {result['sectors']['snapshots']}."
            )
        if excluded:
            self.stdout.write("Excluded dates:")
            for day, reasons in sorted(excluded.items()):
                self.stdout.write(f"  {day}: {'; '.join(reasons)}")
        else:
            self.stdout.write("Excluded dates: none")
