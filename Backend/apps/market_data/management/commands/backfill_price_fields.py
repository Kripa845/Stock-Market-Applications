"""
Fill DailyPrice.transactions (floorsheet trade count) for rows already stored.
Usage:
    python manage.py backfill_price_fields
    python manage.py backfill_price_fields --source unverified
"""

from django.core.management.base import BaseCommand

from apps.market_data.services.price_fields import derive_price_fields


class Command(BaseCommand):
    help = "Backfill DailyPrice.transactions from the stored floorsheet"

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default="crawled",
            help="DailyPrice.source to process (default: crawled)",
        )

    def handle(self, *args, **options):
        result = derive_price_fields(source=options["source"])
        self.stdout.write(
            self.style.SUCCESS("transactions filled: {transactions_filled}".format(**result))
        )
