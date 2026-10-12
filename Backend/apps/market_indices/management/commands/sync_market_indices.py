from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.market_indices.services.nepse_indices import IndexFeedError, sync_index_history


class Command(BaseCommand):
    help = "Fetch NEPSE main and sub-index history (OHLC, turnover, volume, transactions) into IndexDaily."

    def add_arguments(self, parser):
        parser.add_argument("--since", help="oldest session to fetch, YYYY-MM-DD (default: last 10 days)")

    def handle(self, *args, since=None, **options):
        try:
            since = date.fromisoformat(since) if since else None
        except ValueError:
            raise CommandError("--since must use YYYY-MM-DD")
        try:
            result = sync_index_history(since)
        except IndexFeedError as exc:
            self.stderr.write(f"{exc}. Nothing was saved.")
            return
        self.stdout.write(self.style.SUCCESS(
            f"{result['saved']} index rows saved for {result['sessions']} sessions "
            f"since {result['since']} (latest {result['latest']})."
        ))
        if result["unmatched"]:
            self.stdout.write(self.style.WARNING(f"Not in the catalogue: {', '.join(result['unmatched'])}"))
