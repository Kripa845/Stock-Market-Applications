from django.db import models
from django.conf import settings
from django.utils import timezone
class CrawlRun(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )
    sources = models.JSONField(default=list)
    articles_found = models.PositiveIntegerField(default=0)
    articles_created = models.PositiveIntegerField(default=0)
    articles_updated = models.PositiveIntegerField(default=0)
    errors = models.JSONField(default=list, blank=True)

    def start(self):
        self.status = "running"
        self.started_at = timezone.now()
        self.save(update_fields=["status", "started_at"])

    def complete(self):
        self.status = "completed"
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "completed_at"])

    def fail(self, error):
        self.status = "failed"
        self.completed_at = timezone.now()
        self.errors = [*self.errors, str(error)]
        self.save(update_fields=["status", "completed_at", "errors"])
