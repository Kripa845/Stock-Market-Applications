import json
import time
from datetime import date, datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.companies.models import Company
from apps.companies.services.selection import parse_symbols
from apps.floorsheet.services.sharehub_floorsheet import PAUSE_SECONDS, ShareHubError
from apps.floorsheet.services.sharehub_time import NPT
from apps.floorsheet.services.trade_filters import untimed_company_days
from apps.floorsheet.services.trade_time_backfill import apply_changes, plan_company_day, undo_changes


class Command(BaseCommand):
    help = (
        "Fill NULL floorsheet trade_time values from ShareHub, matching (company, date, contract number) "
        "with the same quantity and rate. Dry run unless --apply; --apply writes a JSON backup first, "
        "and --undo restores from it."
    )

    def add_arguments(self, parser):
        parser.add_argument("--from", dest="start", help="oldest date, YYYY-MM-DD (default: every untimed day)")
        parser.add_argument("--to", dest="end", help="newest date, YYYY-MM-DD (default: --from)")
        parser.add_argument("--symbols", help="comma-separated symbols (default: every company with untimed trades)")
        parser.add_argument("--apply", action="store_true", help="write the changes (default: dry run)")
        parser.add_argument("--undo", metavar="BACKUP_JSON", help="set trade_time back to NULL for the rows in a backup")

    def handle(self, *args, **opts):
        if opts["undo"]:
            return self.undo(Path(opts["undo"]), opts["apply"])
        try:
            start = date.fromisoformat(opts["start"]) if opts["start"] else None
            end = date.fromisoformat(opts["end"]) if opts["end"] else start
        except ValueError as exc:
            raise CommandError(f"Dates must be YYYY-MM-DD: {exc}")

        symbols = parse_symbols(opts["symbols"])
        company_ids = list(Company.objects.filter(symbol__in=symbols).values_list("pk", flat=True)) if symbols else None
        pairs = untimed_company_days(start, end, company_ids)
        if not pairs:
            self.stdout.write(self.style.SUCCESS("No untimed trades in that range; nothing to do."))
            return
        companies = Company.objects.in_bulk({company_id for company_id, _ in pairs})
        mode = "APPLY" if opts["apply"] else "DRY RUN (nothing is written; add --apply)"
        self.stdout.write(f"{mode}: {len(pairs)} company-day(s) with untimed trades")

        changes, totals, failures = [], {"untimed": 0, "missing": 0, "mismatched": 0}, []
        for index, (company_id, day) in enumerate(pairs):
            company = companies[company_id]
            if index:
                time.sleep(PAUSE_SECONDS)
            try:
                plan = plan_company_day(company, day)
            except ShareHubError as exc:
                failures.append(f"{company.symbol} {day}: {exc}")
                self.stdout.write(self.style.WARNING(f"   {day} {company.symbol}: {exc}"))
                continue
            for key in totals:
                totals[key] += plan[key] if key == "untimed" else len(plan[key])
            changes += [(pk, txn_id, when, company.symbol, day) for pk, txn_id, when in plan["changes"]]
            self.stdout.write(
                f"   {day} {company.symbol:8} untimed={plan['untimed']:5} fill={len(plan['changes']):5} "
                f"not at ShareHub={len(plan['missing'])} quantity/rate differ={len(plan['mismatched'])}"
            )
            for label in ("missing", "mismatched"):
                if plan[label]:
                    self.stdout.write(f"      {label}: {', '.join(plan[label][:10])}{' ...' if len(plan[label]) > 10 else ''}")

        self.stdout.write(
            f"Total: untimed={totals['untimed']} would fill={len(changes)} "
            f"not at ShareHub={totals['missing']} quantity/rate differ={totals['mismatched']} failed={len(failures)}"
        )
        for pk, txn_id, when, symbol, day in changes[:3]:
            self.stdout.write(f"   e.g. id={pk} {symbol} {day} {txn_id}: NULL -> {when.isoformat()}")
        if not opts["apply"] or not changes:
            return

        backup_dir = Path(settings.BASE_DIR) / "backups"
        backup_dir.mkdir(exist_ok=True)
        backup = backup_dir / f"floorsheet_trade_times_{datetime.now(NPT):%Y%m%d_%H%M%S}.json"
        backup.write_text(json.dumps([
            {"id": pk, "symbol": symbol, "date": day.isoformat(), "transaction_id": txn_id,
             "trade_time_before": None, "trade_time_after": when.isoformat()}
            for pk, txn_id, when, symbol, day in changes
        ], indent=1))
        self.stdout.write(f"Backup written: {backup}")

        written = apply_changes([(pk, txn_id, when) for pk, txn_id, when, _, _ in changes])
        days = sorted({day for *_, day in changes})
        self.stdout.write(self.style.SUCCESS(
            f"Filled {written} trade times ({len(changes) - written} already had one). "
            f"Undo with: manage.py fill_floorsheet_trade_times --undo {backup} --apply\n"
            f"Then rebuild candles: manage.py rebuild_intraday_candles --from {days[0]} --to {days[-1]}"
        ))
        if failures:
            self.stdout.write(self.style.WARNING(f"{len(failures)} company-day(s) failed; re-run to retry them."))

    def undo(self, backup, apply):
        if not backup.exists():
            raise CommandError(f"Backup file not found: {backup}")
        rows = json.loads(backup.read_text())
        self.stdout.write(f"Rows to set back to NULL: {len(rows)}")
        if not apply:
            self.stdout.write("Dry run; add --apply to restore.")
            return
        restored = undo_changes([row["id"] for row in rows])
        self.stdout.write(self.style.SUCCESS(f"Restored {restored} rows from {backup}."))
