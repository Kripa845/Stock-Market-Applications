from django.core.management.base import BaseCommand

from apps.market_data.services.live_prices import LivePriceError, sync_live_prices


class Command(BaseCommand):
    help = "Fetch NEPSE's live market feed once and update LTP / previous close for the tracked companies."

    def handle(self, *args, **options):
        try:
            result = sync_live_prices()
        except LivePriceError as exc:
            self.stderr.write(f"{exc}. Old prices kept.")
            return
        self.stdout.write(self.style.SUCCESS(
            f"{result['updated']} of {result['tracked']} tracked companies updated "
            f"({result['feed_rows']} securities in the feed)."
        ))
        if result["not_in_feed"]:
            self.stdout.write(f"Not traded yet today: {', '.join(result['not_in_feed'])}")
