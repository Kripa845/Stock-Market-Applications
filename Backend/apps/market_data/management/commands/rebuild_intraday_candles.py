from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.companies.models import Company
from apps.companies.selection import parse_symbols, tracked_active_companies
from apps.market_data.services import intraday_candles
from apps.market_data.services.sharehub_floorsheet import sync_day
from apps.market_data.services.trading_calendar import trading_dates


class Command(BaseCommand):
    help = (
        "Rebuild IntradayCandle rows from timestamped floorsheet trades for a date range. "
        "With --sync, first fetch the trade times from ShareHub (tracked companies, or --symbols)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--from", dest="start", required=True, help="oldest date, YYYY-MM-DD")
        parser.add_argument("--to", dest="end", help="newest date, YYYY-MM-DD (default: --from)")
        parser.add_argument("--symbols", help="comma-separated symbols (default: all companies)")
        parser.add_argument(
            "--intervals",
            help=f"comma-separated subset of {','.join(intraday_candles.INTERVALS)} (default: all)",
        )
        parser.add_argument(
            "--sync", action="store_true",
            help="fetch ShareHub trade times for each crawled trading day first (1 request/second)",
        )

    def handle(self, *args, **opts):
        try:
            start = date.fromisoformat(opts["start"])
            end = date.fromisoformat(opts["end"]) if opts["end"] else start
        except ValueError as exc:
            raise CommandError(f"Dates must be YYYY-MM-DD: {exc}")
        if start > end:
            raise CommandError("--from must be on or before --to")

        intervals = intraday_candles.INTERVALS
        if opts["intervals"]:
            intervals = tuple(part.strip() for part in opts["intervals"].split(",") if part.strip())
            unknown = [iv for iv in intervals if iv not in intraday_candles.INTERVAL_MINUTES]
            if unknown:
                raise CommandError(f"Unknown interval(s) {unknown}; choose from {intraday_candles.INTERVALS}")

        symbols = parse_symbols(opts["symbols"])
        company_ids = None
        if symbols:
            companies = Company.objects.filter(symbol__in=symbols)
            missing = sorted(set(symbols) - set(companies.values_list("symbol", flat=True)))
            if missing:
                raise CommandError(f"Unknown symbol(s): {', '.join(missing)}")
            company_ids = list(companies.values_list("pk", flat=True))

        if opts["sync"]:
            sync_companies = list(Company.objects.filter(pk__in=company_ids)) if symbols \
                else list(tracked_active_companies())
            days = [day for day in sorted(trading_dates(since=start)) if day <= end]
            if not days:
                self.stdout.write(self.style.WARNING("No crawled trading days in that range to sync."))
            for day in days:
                summary = sync_day(day, sync_companies)
                self.stdout.write(
                    f"{day}: ShareHub {summary['found']} trades for {summary['companies']} companies "
                    f"({summary['created']} new, {summary['updated']} timed)"
                )
                for error in summary["errors"]:
                    self.stdout.write(self.style.WARNING(f"   {error}"))

        written = intraday_candles.rebuild_range(start, end, company_ids, intervals)
        if not written:
            self.stdout.write(self.style.WARNING(
                "No timestamped trades in that range. Run again with --sync to fetch ShareHub trade times."
            ))
        for day, count in written.items():
            self.stdout.write(f"{day}: {count} candles written")
        self.stdout.write(self.style.SUCCESS(f"Done: {sum(written.values())} candles over {len(written)} day(s)."))
