"""
Load the symbol -> sector mapping for EVERY listed stock from a CSV.

CSV format (header required):  symbol,sector
    NABIL,Commercial Banks
    NHPC,Hydro Power

Raw sector labels are normalised with sectors.normalise_sector(); rows with an
unknown label are skipped and reported so the SECTOR_MAP can be extended.

    python manage.py import_stock_sectors data/stock_sectors.csv
"""

import csv

from django.core.management.base import BaseCommand, CommandError

from apps.market_indices.models import StockSector
from apps.market_indices.sectors import SECTOR_NAMES, normalise_sector


class Command(BaseCommand):
    help = "Import symbol -> sector mapping from a CSV file."

    def add_arguments(self, parser):
        parser.add_argument("csv_path")

    def handle(self, *args, csv_path, **options):
        try:
            handle = open(csv_path, newline="", encoding="utf-8-sig")
        except OSError as exc:
            raise CommandError(f"Cannot open {csv_path}: {exc}")

        saved, unknown = 0, {}
        with handle:
            reader = csv.DictReader(handle)
            if not {"symbol", "sector"} <= set(reader.fieldnames or []):
                raise CommandError("CSV needs a header row: symbol,sector")
            for row in reader:
                symbol = (row["symbol"] or "").strip().upper()
                raw = (row["sector"] or "").strip()
                if not symbol:
                    continue
                sector = raw if raw in SECTOR_NAMES else normalise_sector(raw)
                if sector is None:
                    unknown.setdefault(raw, []).append(symbol)
                    continue
                StockSector.objects.update_or_create(symbol=symbol, defaults={"sector": sector})
                saved += 1

        self.stdout.write(self.style.SUCCESS(f"{saved} symbols saved."))
        for raw, symbols in sorted(unknown.items()):
            self.stdout.write(self.style.WARNING(
                f"Unknown sector label {raw!r} ({len(symbols)} symbols, e.g. {', '.join(symbols[:5])}) "
                "-> add it to SECTOR_MAP in apps/market_indices/sectors.py"
            ))
