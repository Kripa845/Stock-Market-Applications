import json
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.companies.models import Company
from apps.companies.utils import normalize_symbol


class Command(BaseCommand):
    help = "Import company logo URLs from company_logos.json"

    def handle(self, *args, **options):
        # company_logos.json is located beside manage.py
        json_path = Path("company_logos.json")

        if not json_path.exists():
            self.stdout.write(
                self.style.ERROR(
                    f"File not found: {json_path.resolve()}"
                )
            )
            return

        with open(json_path, "r", encoding="utf-8") as file:
            logos = json.load(file)

        updated = 0
        not_found = 0
        skipped = 0

        for item in logos:
            raw_symbol = item.get("symbol", "").strip()
            logo_url = item.get("logo_url", "").strip()

            if not raw_symbol or not logo_url:
                skipped += 1
                continue

            symbol = normalize_symbol(raw_symbol)

            try:
                company = Company.objects.get(
                    symbol__iexact=symbol
                )
            except Company.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(
                        f"Company not found: {symbol}"
                    )
                )
                not_found += 1
                continue

            company.logo_url = logo_url
            company.save(update_fields=["logo_url"])

            updated += 1

            self.stdout.write(
                f"Updated {company.symbol}"
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully updated: {updated}"
            )
        )

        self.stdout.write(
            self.style.WARNING(
                f"Companies not found: {not_found}"
            )
        )

        self.stdout.write(
            f"Skipped records: {skipped}"
        )