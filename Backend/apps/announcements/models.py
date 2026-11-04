from django.db import models

# Create your models here.
from django.db import models


class Announcement(models.Model):
    external_id = models.CharField(max_length=100, unique=True)
    symbol = models.CharField(max_length=20, blank=True, db_index=True)  # blank = market-wide NEPSE item
    company_name = models.CharField(max_length=255, blank=True)
    logo_url = models.URLField(max_length=500, blank=True)
    title = models.TextField()
    is_event = models.BooleanField(default=False, db_index=True)
    type = models.CharField(max_length=30, blank=True, db_index=True)
    category = models.CharField(max_length=60, blank=True, db_index=True)
    source = models.CharField(max_length=30, blank=True, db_index=True)
    details_url = models.URLField(max_length=500, blank=True)
    published_at = models.DateTimeField(db_index=True)
    raw = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-published_at"]
        indexes = [models.Index(fields=["symbol", "-published_at"])]

    def __str__(self):
        return f"{self.symbol or 'NEPSE'}: {self.title[:60]}"