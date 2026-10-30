from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.companies.models import Company
from apps.companies.services.selection import parse_symbols
from apps.floorsheet.services import floorsheet_quality
from apps.floorsheet.services.trade_filters import ODD_LOT_THRESHOLD, untimed_company_days


class Command(BaseCommand):
    help = (
        "Read-only floorsheet check against DailyPrice: volume, high / low with and without odd lots, "
        "untimed and pre-open trades, missing days; --candles adds the impact of the filters on stored candles."
    )

    def add_arguments(self, parser):
        parser.add_argument("--from", dest="start", help="oldest date, YYYY-MM-DD")
        parser.add_argument("--to", dest="end", help="newest date, YYYY-MM-DD")
        parser.add_argument("--symbols", help="comma-separated symbols (default: all)")
        parser.add_argument("--candles", action="store_true", help="also report the filters' impact on IntradayCandle")
        parser.add_argument("--list", type=int, default=10, help="mismatches to list (default 10)")

    def handle(self, *args, **opts):
        try:
            start = date.fromisoformat(opts["start"]) if opts["start"] else None
            end = date.fromisoformat(opts["end"]) if opts["end"] else None
        except ValueError as exc:
            raise CommandError(f"Dates must be YYYY-MM-DD: {exc}")
        symbols = parse_symbols(opts["symbols"])
        company_ids = list(Company.objects.filter(symbol__in=symbols).values_list("pk", flat=True)) if symbols else None
        names = dict(Company.objects.values_list("pk", "symbol"))
        out = self.stdout.write

        counts = floorsheet_quality.trade_counts(start, end)
        out(f"Trades: {counts['trades']}")
        out(f"  untimed (trade_time NULL): {counts['untimed']}")
        untimed = untimed_company_days(start, end, company_ids)
        if untimed:
            out(f"    on {len(untimed)} company-day(s): "
                + ", ".join(f"{names[c]} {d}" for c, d in untimed[:opts["list"]]) + (" ..." if len(untimed) > opts["list"] else ""))
        out(f"  odd lots (< {ODD_LOT_THRESHOLD} shares, left out of high/low and footprints): {counts['odd_lots']}")
        out(f"  pre-open auction fills (before 11:00, a separate footprint group, never classified): "
            f"{counts['pre_open']} on {counts['pre_open_company_days']} company-days")
        out(f"  continuous session: {counts['continuous']}")

        for label, odd in (("board lots", False), ("all trades", True)):
            r = floorsheet_quality.compare_with_daily_prices(start, end, company_ids, odd_lots=odd)
            n = r["company_days"] or 1
            if not odd:
                out(f"\nCompany-days in both floorsheet and DailyPrice: {r['company_days']}")
                out(f"  volume equal: {r['volume_matched']} ({r['volume_matched'] / n * 100:.2f}%)")
                for (c, d), fs, dp in r["volume_mismatches"][:opts["list"]]:
                    out(f"    {names[c]} {d}: floorsheet {fs} vs DailyPrice {dp}")
                out(f"  in DailyPrice, no floorsheet: {len(r['missing_floorsheet'])}"
                    + "".join(f"  {names[c]} {d}" for c, d in r["missing_floorsheet"][:opts["list"]]))
                out(f"  in floorsheet, no DailyPrice: {len(r['missing_daily_price'])}")
            out(f"  high/low equal ({label}): {r['high_low_matched']} ({r['high_low_matched'] / n * 100:.2f}%)")
            if not odd:
                for (c, d), fh, dh, fl, dl in r["high_low_mismatches"][:opts["list"]]:
                    out(f"    {names[c]} {d}: high {fh} vs {dh}, low {fl} vs {dl}")

        if opts["candles"]:
            out("\nStored IntradayCandle rows the filters would change (builder NOT changed):")
            for interval, r in floorsheet_quality.candle_filter_impact(start, end).items():
                out(f"  {interval:4} stored={r['stored']:7}  high/low change without odd lots={r['odd_lot_high_low_changes']:6}  "
                    f"11:00 candles holding pre-open fills={r['contain_pre_open']}")
