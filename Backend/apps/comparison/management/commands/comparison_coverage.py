import json

from django.core.management.base import BaseCommand
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection, transaction

from apps.comparison.services.compare import compare_companies
from apps.comparison.services.coverage import coverage_report
from apps.market_data.services.market_stats import tracked_companies


class Command(BaseCommand):
    help = "Print the comparison data-coverage table for every tracked company (read-only)."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", help="Print the full report as JSON.")
        parser.add_argument("--sample", help="Also print comparison JSON for these comma-separated symbols.")
        parser.add_argument("--output", help="Write the JSON to this file (UTF-8) instead of stdout.")

    def handle(self, *args, **options):
        with transaction.atomic():
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SET TRANSACTION READ ONLY")
            report = coverage_report()
            samples = None
            if options["sample"]:
                symbols = [s.strip().upper() for s in options["sample"].split(",")]
                by_symbol = {c.symbol: c for c in tracked_companies().filter(symbol__in=symbols)}
                samples = compare_companies([by_symbol[s] for s in symbols if s in by_symbol])

        if options["json"] or samples:
            payload = {"coverage": report} if options["json"] else {}
            if samples:
                payload["samples"] = samples
            text = json.dumps(payload, cls=DjangoJSONEncoder, indent=2)
            if options["output"]:
                with open(options["output"], "w", encoding="utf-8") as handle:
                    handle.write(text)
            else:
                self.stdout.write(text)
            return

        self.stdout.write(f"Expected latest session: {report['expected_latest_session']}  "
                          f"tracked companies: {report['tracked_count']}")
        header = ("Symbol", "Sector", "Price", "Snap", "QR qtrs", "EPS", "BV", "Shares", "Divs", "Problems", "Null fields")
        self.stdout.write(" | ".join(header))
        for row in report["companies"]:
            if "error" in row:
                self.stdout.write(f"{row['symbol']} | {row['sector']} | ERROR {row['error']}")
                continue
            self.stdout.write(" | ".join(str(v) for v in (
                row["symbol"], row["sector"], row["price_sessions"], row["snapshot_sessions"],
                row["quarters_in_quarterly_report"], row["eps_present"], row["book_value_present"],
                row["listed_shares_present"], row["dividend_rows"],
                ",".join(row["problems"] + [f"sanity:{n}" for n in row["sanity_checks_failed"]]) or "-",
                ",".join(row["null_fields"]),
            )))
