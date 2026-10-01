import csv

from django.core.management.base import BaseCommand, CommandError

from apps.market_data.models import Broker


class Command(BaseCommand):
    help = "Import broker directory rows from a CSV file."

    def add_arguments(self, parser):
        parser.add_argument("csv_path")

    def handle(self, *args, **options):
        path = options["csv_path"]
        try:
            source = open(path, "r", encoding="utf-8-sig", newline="")
        except OSError as exc:
            raise CommandError(f"Could not open {path}: {exc}") from exc

        created = updated = 0
        with source:
            reader = csv.DictReader(source)
            required = {"broker_code", "name", "short_name", "logo_filename"}
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise CommandError("CSV must contain broker_code,name,short_name,logo_filename headers.")
            for line, row in enumerate(reader, start=2):
                code = (row.get("broker_code") or "").strip()
                name = (row.get("name") or "").strip()
                if not code or not name:
                    raise CommandError(f"CSV row {line} must include broker_code and name.")
                _, was_created = Broker.objects.update_or_create(
                    broker_code=code,
                    defaults={
                        "name": name,
                        "short_name": (row.get("short_name") or "").strip(),
                        "logo": (row.get("logo_filename") or "").strip(),
                    },
                )
                created += int(was_created)
                updated += int(not was_created)
        self.stdout.write(self.style.SUCCESS(f"Imported {created} brokers; updated {updated}."))
