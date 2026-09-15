from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.crawler_runs.models import CrawlRun


class Command(BaseCommand):
    help = "Mark stale running crawls as failed"

    def handle(self, *args, **options):

        runs = CrawlRun.objects.filter(
            status=CrawlRun.Status.RUNNING
        )

        count = runs.count()

        runs.update(
            status=CrawlRun.Status.FAILED,
            completed_at=timezone.now(),
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Recovered {count} stale crawl runs."
            )
        )