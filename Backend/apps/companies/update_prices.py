from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand
from django.utils import timezone
# pip install nepse-data-api  (or similar package name)
from nepse_data_api import Nepse  # type: ignore[import-not-found]

from .models import Company


def to_decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return None


class Command(BaseCommand):
    help = "Fetch live NEPSE prices and update ltp / previous_close for our companies."

    def handle(self, *args, **options):
        nepse = Nepse()
        rows = nepse.get_stocks()  # list of dicts, one per listed stock

        if not rows:
            self.stderr.write("No data returned from NEPSE (market closed or source down). Keeping old prices.")
            return

        # symbol -> row, for fast lookup
        by_symbol = {r.get("symbol"): r for r in rows if r.get("symbol")}

        updated, missing = 0, []
        now = timezone.now()

        for company in Company.objects.all():
            row = by_symbol.get(company.symbol)
            if not row:
                missing.append(company.symbol)
                continue

            # Field names can differ between library versions, so try a few.
            ltp = to_decimal(row.get("lastTradedPrice") or row.get("ltp") or row.get("closePrice"))
            prev = to_decimal(row.get("previousClose") or row.get("previousDayClosePrice"))

            if ltp is None or prev is None:
                missing.append(company.symbol)
                continue

            company.ltp = ltp
            company.previous_close = prev
            company.prices_updated_at = now
            company.save(update_fields=["ltp", "previous_close", "prices_updated_at"])
            updated += 1

        self.stdout.write(self.style.SUCCESS(f"Updated {updated} companies."))
        if missing:
            self.stdout.write(self.style.WARNING(f"No price found for: {', '.join(missing)}"))