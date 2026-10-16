from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.market_indices.services import sharesansar_indices
from apps.market_indices.services.nepse_indices import IndexFeedError, sync_index_history


class Command(BaseCommand):
    help = (
        "Fetch NEPSE main and sub-index history (OHLC, turnover, volume, transactions) into IndexDaily. "
        "--source sharesansar fills only the sessions NEPSE has not stored, from ShareSansar."
    )

    def add_arguments(self, parser):
        parser.add_argument("--since", help="oldest session to fetch, YYYY-MM-DD (default: last 10 days)")
        parser.add_argument("--source", choices=("nepse", "sharesansar"), default="nepse")

    def handle(self, *args, since=None, source="nepse", **options):
        try:
            since = date.fromisoformat(since) if since else None
        except ValueError:
            raise CommandError("--since must use YYYY-MM-DD")
        if source == "sharesansar":
            return self._sharesansar(since)
        try:
            result = sync_index_history(since)
        except IndexFeedError as exc:
            self.stderr.write(f"{exc}. Nothing was saved (try --source sharesansar).")
            return
        self.stdout.write(self.style.SUCCESS(
            f"{result['saved']} index rows saved for {result['sessions']} sessions "
            f"since {result['since']} (latest {result['latest']})."
        ))
        if result["unmatched"]:
            self.stdout.write(self.style.WARNING(f"Not in the catalogue: {', '.join(result['unmatched'])}"))
        if result["skipped_in_progress"]:
            self.stdout.write(f"Still trading, not stored until the close: {', '.join(result['skipped_in_progress'])}")

    def _sharesansar(self, since):
        try:
            result = sharesansar_indices.backfill_index_history(since)
        except sharesansar_indices.ShareSansarIndexError as exc:
            self.stderr.write(f"{exc}. Nothing was saved.")
            return
        self.stdout.write(self.style.SUCCESS(
            f"ShareSansar: {result['saved']} rows added, {result['refreshed']} refreshed, "
            f"{result['kept_nepse']} kept from NEPSE (since {result['since']})."
        ))
