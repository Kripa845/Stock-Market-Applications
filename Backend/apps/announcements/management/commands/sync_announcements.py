from django.core.management.base import BaseCommand

from apps.announcements.services import sync_announcements


class Command(BaseCommand):
    help = "Scrape ShareHub announcements. --days 90 to backfill, --debug to watch the browser."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7)
        parser.add_argument("--debug", action="store_true", help="visible browser + print XHR URLs")

    def handle(self, *args, **opts):
        n = sync_announcements(opts["days"], debug=opts["debug"])
        self.stdout.write(self.style.SUCCESS(f"saved/updated {n} announcements"))