# apps/crawler_runs/models.py

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.companies.models import Company


class CrawlRun(models.Model):

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    class CrawlType(models.TextChoices):
        NEWS = "news", "News"
        TRADING = "trading", "Trading Data"
        FLOORSHEET = "floorsheet", "Floorsheet"
        ALL = "all", "All"

    crawl_type = models.CharField(
        max_length=20,
        choices=CrawlType.choices,
        default=CrawlType.NEWS,
    )

    source = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    target = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    sources = models.JSONField(
        default=list,
        blank=True,
    )
    company = models.ForeignKey(
    Company,
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name="crawl_runs",
)

    # -------------------------
    # NEWS
    # -------------------------

    articles_found = models.PositiveIntegerField(
        default=0
    )

    articles_created = models.PositiveIntegerField(
        default=0
    )

    articles_updated = models.PositiveIntegerField(
        default=0
    )

    # -------------------------
    # TRADING DATA
    # -------------------------

    prices_found = models.PositiveIntegerField(
        default=0
    )

    prices_created = models.PositiveIntegerField(
        default=0
    )

    prices_updated = models.PositiveIntegerField(
        default=0
    )

    # -------------------------
    # FLOORSHEET
    # -------------------------

    floorsheet_found = models.PositiveIntegerField(
        default=0
    )

    floorsheet_created = models.PositiveIntegerField(
        default=0
    )

    floorsheet_updated = models.PositiveIntegerField(
        default=0
    )

    # -------------------------
    # TASK / LOGGING
    # -------------------------

    task_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    errors = models.JSONField(
        default=list,
        blank=True,
    )

    logs = models.TextField(
        blank=True,
        default="",
    )

    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="crawl_runs",
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )
    process_id = models.PositiveIntegerField(
    null=True,
    blank=True,
)
    @property
    def duration_seconds(self):
        if not self.started_at:
            return None

        end = self.completed_at or timezone.now()

        return round(
            (end - self.started_at).total_seconds(),
            1,
        )

    def start(self):
        self.status = self.Status.RUNNING
        self.started_at = timezone.now()

        self.save(
            update_fields=[
                "status",
                "started_at",
            ]
        )

    def complete(self):
        self.status = self.Status.SUCCESS
        self.completed_at = timezone.now()

        self.save(
            update_fields=[
                "status",
                "completed_at",
            ]
        )

    def fail(self, error=None):
        self.status = self.Status.FAILED
        self.completed_at = timezone.now()

        if error:
            self.errors = [
                *self.errors,
                str(error),
            ]

        self.save(
            update_fields=[
                "status",
                "completed_at",
                "errors",
            ]
        )
    def cancel(self):
        self.status = self.Status.CANCELLED
        self.completed_at = timezone.now()

        self.save(
            update_fields=[
                "status",
                "completed_at",
            ]
        )
        
        