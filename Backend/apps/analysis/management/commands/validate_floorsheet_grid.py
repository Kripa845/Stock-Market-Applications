from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.analysis.services.floorsheet_grid import BUCKET_MINUTES, build_grid
from apps.floorsheet.models import FloorsheetTransaction


class Command(BaseCommand):
    help = "Run the Floor Sheet Summary grid checks for one session or every timestamped session in a range."

    def add_arguments(self, parser):
        parser.add_argument("--date", type=date.fromisoformat, help="One session (default: latest with trade times).")
        parser.add_argument("--since", type=date.fromisoformat, help="Check every session from this date on.")
        parser.add_argument("--minutes", type=int, default=1, choices=BUCKET_MINUTES)
        parser.add_argument("--verbose-pass", action="store_true", help="Also list sessions where every check passed.")

    def handle(self, *args, **options):
        timed = FloorsheetTransaction.objects.filter(trade_time__isnull=False)
        if options["since"]:
            days = sorted(set(timed.filter(date__gte=options["since"]).values_list("date", flat=True)))
        else:
            day = options["date"] or timed.order_by("-date").values_list("date", flat=True).first()
            days = [day] if day else []
        if not days:
            raise CommandError("No sessions with trade times.")

        failed_days = 0
        for day in days:
            failed = [c for c in build_grid(day, options["minutes"])["checks"] if c["status"] == "fail"]
            if not failed:
                if options["verbose_pass"] or len(days) == 1:
                    self.stdout.write(self.style.SUCCESS(f"{day}: all checks pass"))
                continue
            failed_days += 1
            for check in failed:
                self.stdout.write(self.style.ERROR(f"{day} FAIL {check['key']}: {check['label']} ({check['mismatch_count']})"))
                for m in check["mismatches"]:
                    where = f" {m['bucket']}" if m["bucket"] else ""
                    source = f" [{m['source']}]" if m["source"] else ""
                    self.stdout.write(f"    {m['symbol']}{where} {m['field']}: expected {m['expected']}, got {m['actual']}{source}")
        self.stdout.write(f"{len(days)} session(s) checked, {failed_days} with failures.")
