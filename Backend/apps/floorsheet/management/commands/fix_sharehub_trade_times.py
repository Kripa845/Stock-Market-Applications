import json
from collections import Counter
from datetime import datetime, time, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.floorsheet.models import FloorsheetTransaction
from apps.floorsheet.services.sharehub_time import NPT

# Trusting ShareHub's wrong "Z" moves a trade 5:45 later (14:59:59 -> 20:44:59 NPT).
SHIFT = timedelta(hours=5, minutes=45)
# A real trade time falls inside this window (pre-open through a little after the close).
VALID_FROM = time(10, 0)
VALID_TO = time(15, 30)


def is_shifted(trade_time, trade_date):
    """True when the stored time is outside the session but moving it back 5:45 puts it inside, same day."""
    local = trade_time.astimezone(NPT)
    if VALID_FROM <= local.time() <= VALID_TO:
        return False
    fixed = local - SHIFT
    return fixed.date() == trade_date and VALID_FROM <= fixed.time() <= VALID_TO


class Command(BaseCommand):
    help = (
        "Correct floorsheet trade_time values stored 5h45m late (ShareHub's 'Z' read as UTC). "
        "Writes a JSON backup of every changed row first; --undo restores from it."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="report what would change, write nothing")
        parser.add_argument("--undo", metavar="BACKUP_JSON", help="restore trade_time values from a backup file")

    def handle(self, *args, **opts):
        if opts["undo"]:
            return self.undo(Path(opts["undo"]), opts["dry_run"])

        # Coarse DB filter (hour in Asia/Kathmandu, the project time zone), exact check in Python.
        candidates = (
            FloorsheetTransaction.objects
            .filter(trade_time__isnull=False, trade_time__hour__gte=VALID_TO.hour)
            .values_list("pk", "trade_time", "date")
        )
        changes = [(pk, trade_time, day) for pk, trade_time, day in candidates.iterator() if is_shifted(trade_time, day)]

        self.stdout.write(f"Rows that would change: {len(changes)}")
        for day, count in sorted(Counter(day for _, _, day in changes).items()):
            self.stdout.write(f"   {day}: {count}")
        for pk, trade_time, _ in changes[:5]:
            self.stdout.write(
                f"   e.g. id={pk}: {trade_time.astimezone(NPT).isoformat()} -> "
                f"{(trade_time - SHIFT).astimezone(NPT).isoformat()}"
            )
        if opts["dry_run"] or not changes:
            return

        backup = Path(settings.BASE_DIR) / f"trade_time_fix_backup_{datetime.now(NPT):%Y%m%d_%H%M%S}.json"
        backup.write_text(json.dumps([[pk, trade_time.isoformat()] for pk, trade_time, _ in changes]))
        self.stdout.write(f"Backup written: {backup}")

        objs = [FloorsheetTransaction(pk=pk, trade_time=trade_time - SHIFT) for pk, trade_time, _ in changes]
        with transaction.atomic():
            FloorsheetTransaction.objects.bulk_update(objs, ["trade_time"], batch_size=2000)
        self.stdout.write(self.style.SUCCESS(
            f"Corrected {len(objs)} rows. Undo with: manage.py fix_sharehub_trade_times --undo {backup}\n"
            "Then rebuild candles for the affected dates with rebuild_intraday_candles."
        ))

    def undo(self, backup, dry_run):
        if not backup.exists():
            raise CommandError(f"Backup file not found: {backup}")
        rows = json.loads(backup.read_text())
        self.stdout.write(f"Rows to restore: {len(rows)}")
        if dry_run:
            return
        objs = [FloorsheetTransaction(pk=pk, trade_time=datetime.fromisoformat(value)) for pk, value in rows]
        with transaction.atomic():
            FloorsheetTransaction.objects.bulk_update(objs, ["trade_time"], batch_size=2000)
        self.stdout.write(self.style.SUCCESS(f"Restored {len(objs)} rows from {backup}."))
