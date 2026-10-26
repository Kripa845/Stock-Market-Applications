from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError

from crawlers.runner import run_spider


class Command(BaseCommand):
    help = "Re-crawl ShareSansar floorsheet data for each date in an inclusive range."

    def add_arguments(self, parser):
        parser.add_argument("start_date", help="Start date in YYYY-MM-DD format")
        parser.add_argument("end_date", help="End date in YYYY-MM-DD format")

    def handle(self, *args, **options):
        try:
            start = date.fromisoformat(options["start_date"])
            end = date.fromisoformat(options["end_date"])
        except ValueError as exc:
            raise CommandError("Dates must use YYYY-MM-DD format.") from exc
        if start > end:
            raise CommandError("start_date must be on or before end_date.")

        cursor = start
        failures = []
        while cursor <= end:
            self.stdout.write(f"Crawling floorsheet for {cursor}...")
            result = run_spider(
                "floorsheet",
                {"floorsheet_date": cursor.isoformat()},
            )
            if result.ok:
                self.stdout.write(self.style.SUCCESS(f"Completed {cursor}."))
            else:
                failures.append(cursor.isoformat())
                self.stderr.write(self.style.ERROR(f"Failed {cursor}."))
            cursor += timedelta(days=1)

        if failures:
            raise CommandError("Failed dates: " + ", ".join(failures))
