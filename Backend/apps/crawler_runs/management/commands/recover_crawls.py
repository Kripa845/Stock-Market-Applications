"""
Management command: recover_crawls

Marks genuinely *stale* RUNNING/PENDING CrawlRuns as FAILED.

A run is considered stale when:
  - Its ``started_at`` is older than ``--max-age-minutes`` (default 90),
    OR it is PENDING and its ``created_at`` is older than that threshold
    (meaning the worker never picked it up).

Runs that are newer than the threshold are left untouched, so running
this command during a legitimate 30-minute crawl does NOT kill it.

Safe to run repeatedly — already-terminal runs (SUCCESS/FAILED/CANCELLED)
are never touched.

Recommended production schedule:
    Every 2 hours via Celery Beat or a cron job:
        python manage.py recover_crawls --max-age-minutes 90
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from apps.crawler_runs.models import CrawlRun


class Command(BaseCommand):
    help = (
        "Mark stale RUNNING or PENDING crawl runs as FAILED. "
        "Only affects runs older than --max-age-minutes (default 90)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--max-age-minutes",
            type=int,
            default=90,
            help=(
                "Runs that started (or were created, for PENDING) more than "
                "this many minutes ago are considered stale. Default: 90."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Print what would be changed without writing to the database.",
        )

    def handle(self, *args, **options):
        max_age = options["max_age_minutes"]
        dry_run = options["dry_run"]
        cutoff = timezone.now() - timedelta(minutes=max_age)

        # ------------------------------------------------------------------
        # Find stale RUNNING runs: started_at is set and is too old.
        # ------------------------------------------------------------------
        stale_running = CrawlRun.objects.filter(
            status=CrawlRun.Status.RUNNING,
            started_at__lt=cutoff,
        )

        # ------------------------------------------------------------------
        # Find stale PENDING runs: created_at is too old (worker never
        # picked them up).
        # ------------------------------------------------------------------
        stale_pending = CrawlRun.objects.filter(
            status=CrawlRun.Status.PENDING,
            created_at__lt=cutoff,
        )

        all_stale = list(stale_running) + list(stale_pending)

        if not all_stale:
            self.stdout.write(
                self.style.SUCCESS(
                    f"No stale crawl runs found (threshold: {max_age} minutes)."
                )
            )
            return

        for run in all_stale:
            age_mins = round(
                (timezone.now() - (run.started_at or run.created_at)).total_seconds() / 60,
                1,
            )
            label = f"CrawlRun #{run.pk} ({run.crawl_type}, {run.status}, age={age_mins}m)"

            if dry_run:
                self.stdout.write(f"[DRY RUN] Would recover: {label}")
                continue

            # Append a recovery note to the errors list.
            errors = list(run.errors or [])
            errors.append(
                f"Recovered by manage.py recover_crawls: "
                f"run was {run.status} for {age_mins} minutes "
                f"(threshold={max_age}m). Marked FAILED at {timezone.now().isoformat()}."
            )

            CrawlRun.objects.filter(pk=run.pk).update(
                status=CrawlRun.Status.FAILED,
                completed_at=timezone.now(),
                errors=errors,
                process_id=None,
            )

            self.stdout.write(
                self.style.WARNING(f"Recovered: {label}")
            )

        if not dry_run:
            count = len(all_stale)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Recovered {count} stale crawl run(s) "
                    f"(threshold: {max_age} minutes)."
                )
            )
