from django.core.management.base import BaseCommand

from apps.market_data.services.live_prices import LivePriceError, sync_live_prices


class Command(BaseCommand):
    help = "Fetch live NEPSE prices and update ltp / previous_close for the tracked companies."

    def handle(self, *args, **options):
        try:
            result = sync_live_prices()
        except LivePriceError as exc:
            self.stderr.write(f"{exc}. Keeping old prices.")
            return

        self.stdout.write(self.style.SUCCESS(
            f"Updated {result['updated']} of {result['tracked']} tracked companies "
            f"({result['feed_rows']} securities in the live feed)."
        ))
        if result["not_in_feed"]:
            self.stdout.write(self.style.WARNING(
                f"Not traded yet this session: {', '.join(result['not_in_feed'])}"
            ))
