"""
Manual / cron entry point for crawling.

Celery beat (see CELERY_BEAT_SCHEDULE in config/settings.py) is the
primary scheduler for this project, but the assignment explicitly asks
for the crawler to be "runnable on a schedule (e.g. Celery beat,
APScheduler, or cron), not only as a manual one-off script" — this
command is what a plain crontab entry (or a developer's terminal)
would call.

Examples
--------
    # everything, one after another (what beat's daily job runs)
    python manage.py run_crawl --type all

    # just the news portals
    python manage.py run_crawl --type news

    # just OHLCV prices
    python manage.py run_crawl --type prices

    # just floorsheet
    python manage.py run_crawl --type floorsheet

    # a single named spider (useful for debugging one portal)
    python manage.py run_crawl --spider sharesansar

Example crontab entry (runs the full pipeline every evening):
    0 18 * * * cd /path/to/Backend && /path/to/venv/bin/python \
        manage.py run_crawl --type all >> /var/log/nepse_crawl.log 2>&1
"""

from django.core.management.base import BaseCommand, CommandError

from crawlers.runner import (
    ALL_SPIDERS,
    FLOORSHEET_SPIDERS,
    MARKET_DATA_SPIDERS,
    NEWS_SPIDERS,
    run_spiders,
)


class Command(BaseCommand):
    help = "Run one or more crawl spiders (manual / cron alternative to Celery beat)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--type",
            choices=["news", "prices", "floorsheet", "all"],
            help="Run every spider in this group.",
        )
        parser.add_argument(
            "--spider",
            choices=ALL_SPIDERS,
            help="Run exactly one named spider.",
        )

    def handle(self, *args, **options):
        crawl_type = options.get("type")
        spider_name = options.get("spider")

        if not crawl_type and not spider_name:
            raise CommandError("Pass either --type or --spider.")

        if crawl_type and spider_name:
            raise CommandError("Pass only one of --type / --spider.")

        if spider_name:
            spiders_to_run = [spider_name]
        else:
            spiders_to_run = {
                "news": NEWS_SPIDERS,
                "prices": MARKET_DATA_SPIDERS,
                "floorsheet": FLOORSHEET_SPIDERS,
                "all": NEWS_SPIDERS + MARKET_DATA_SPIDERS + FLOORSHEET_SPIDERS,
            }[crawl_type]

        self.stdout.write(f"Running: {', '.join(spiders_to_run)}")

        results = run_spiders(spiders_to_run)

        any_failed = False

        for result in results:
            if result.ok:
                self.stdout.write(
                    self.style.SUCCESS(f"  [OK]     {result.spider_name}")
                )
            else:
                any_failed = True
                self.stdout.write(
                    self.style.ERROR(
                        f"  [FAILED] {result.spider_name} "
                        f"(exit={result.returncode})"
                    )
                )
                if result.stderr:
                    self.stdout.write(result.stderr[-2000:])

        if any_failed:
            raise CommandError("One or more spiders failed. See output above.")

        self.stdout.write(self.style.SUCCESS("Crawl run completed."))
