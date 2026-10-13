"""
Fill DailyPrice.transactions (trade count) for rows already stored.
Usage:
    python manage.py backfill_price_fields                 # from complete floorsheets only
    python manage.py backfill_price_fields --nepse         # + NEPSE day summary for every missing date
    python manage.py backfill_price_fields --nepse --limit 30
    python manage.py backfill_price_fields --source unverified
"""

import time

from django.core.management.base import BaseCommand

from apps.market_data.services.live_prices import LivePriceError, day_summary_fetcher
from apps.market_data.services.price_fields import (
    derive_price_fields,
    fill_transactions_from_nepse,
    missing_transaction_dates,
)


class Command(BaseCommand):
    help = "Backfill DailyPrice.transactions from the stored floorsheet and, with --nepse, from NEPSE"

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default="crawled",
            help="DailyPrice.source to process (default: crawled)",
        )
        parser.add_argument("--nepse", action="store_true", help="Also fetch missing dates from NEPSE")
        parser.add_argument("--limit", type=int, default=None, help="With --nepse: newest N missing dates only")
        parser.add_argument("--delay", type=float, default=1.0, help="With --nepse: seconds between NEPSE requests")

    def handle(self, *args, **options):
        result = derive_price_fields(source=options["source"])
        self.stdout.write(self.style.SUCCESS(
            "floorsheet: transactions filled {transactions_filled}, "
            "incomplete floorsheets skipped {incomplete_floorsheets}".format(**result)
        ))
        if not options["nepse"]:
            return

        dates = missing_transaction_dates(source=options["source"], limit=options["limit"])
        self.stdout.write(f"NEPSE: {len(dates)} date(s) with missing trade counts")
        fetch = day_summary_fetcher()

        def polite_fetch(day):
            rows = fetch(day)
            time.sleep(options["delay"])
            return rows

        try:
            nepse = fill_transactions_from_nepse(dates, source=options["source"], fetch_day=polite_fetch)
        except LivePriceError as exc:
            self.stderr.write(self.style.ERROR(str(exc)))
            return
        self.stdout.write(self.style.SUCCESS(
            f"NEPSE: filled {nepse['filled']}, already correct {nepse['unchanged']}, "
            f"not in feed {nepse['not_in_feed']}, volume mismatch {len(nepse['volume_mismatch'])}, "
            f"days with no NEPSE data {len(nepse['empty_days'])}"
        ))
        for item in nepse["volume_mismatch"][:20]:
            self.stdout.write(f"  volume mismatch: {item}")
