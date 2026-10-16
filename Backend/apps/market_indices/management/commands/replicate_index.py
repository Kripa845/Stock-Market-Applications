from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.market_indices.services import index_replication as rep


def _day(value):
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise CommandError(f"{value!r}: dates must use YYYY-MM-DD")


class Command(BaseCommand):
    help = (
        "Reproduce NEPSE index values from company data (Index = market cap x K).\n"
        "  snapshot  --date D [--sector Banking ...]  store company prices + shares for D\n"
        "  calibrate INDEX --date D                     K from NEPSE's published close on D\n"
        "  verify    --date D [--index INDEX ...]       compare computed vs published, store IndexCheck\n"
        "  compute   INDEX --date D                     print the reproduced value"
    )

    def add_arguments(self, parser):
        parser.add_argument("action", choices=["snapshot", "calibrate", "verify", "compute"])
        parser.add_argument("index", nargs="?", help="MarketIndex code, e.g. BANKING")
        parser.add_argument("--date", required=True, type=_day)
        parser.add_argument("--sector", action="append", help="normalised sector to snapshot (repeatable)")
        parser.add_argument("--index", dest="indices", action="append", help="index to verify (repeatable)")

    def handle(self, *args, action, index=None, date=None, sector=None, indices=None, **options):
        if action in ("calibrate", "compute") and not index:
            raise CommandError(f"{action} needs an index code, e.g. BANKING")
        try:
            if action == "snapshot":
                result = rep.snapshot_company_daily(date, sectors=sector)
                self.stdout.write(self.style.SUCCESS(
                    f"{result['saved']} securities saved for {result['date']}; "
                    f"{len(result['carried_forward'])} untraded (last close kept)."
                ))
                if result["shares_from_same_day_mcap"]:
                    self.stdout.write(self.style.WARNING(
                        "Listed shares taken from NEPSE's same-day market cap: "
                        + ", ".join(result["shares_from_same_day_mcap"])
                    ))
            elif action == "calibrate":
                cal = rep.calibrate(index, date)
                self.stdout.write(self.style.SUCCESS(
                    f"{index} K={cal.k} from {cal.effective_date}: close {cal.published_close} / "
                    f"market cap Rs {cal.market_cap:,} ({cal.constituents} constituents)"
                ))
            elif action == "compute":
                self.stdout.write(f"{index} {date}: {rep.compute_index(date, index)}")
            else:
                for check in rep.verify_day(date, indices):
                    if isinstance(check, dict):
                        self.stderr.write(f"{check['index']}: {check['error']}")
                        continue
                    style = self.style.WARNING if check.flagged or check.needs_recalibration else self.style.SUCCESS
                    self.stdout.write(style(
                        f"{check.index.code} {check.date}: computed {check.computed} vs published "
                        f"{check.published} (diff {check.diff:+}){'  FLAGGED' if check.flagged else ''}"
                    ))
                    if check.needs_recalibration:
                        self.stdout.write(self.style.WARNING(f"  recalibrate: {check.recalibration_reason}"))
        except rep.ReplicationError as exc:
            raise CommandError(str(exc))
