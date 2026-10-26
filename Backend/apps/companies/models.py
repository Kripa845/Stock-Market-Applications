from django.db import models
# from apps.crawler_runs.models import CrawlRun
from django.conf import settings


# Create your models here.
class Company(models.Model):
    symbol = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=300)
    logo_url = models.URLField(
        blank=True,
        null=True,
    )
    sector = models.CharField(max_length=100)
    aliases = models.JSONField(
        default=list,
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_companies",
    )
    ltp = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    previous_close = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    prices_updated_at = models.DateTimeField(null=True, blank=True)
    # Shares traded / turnover (NPR) so far in the session of prices_updated_at, from the same live feed.
    session_volume = models.BigIntegerField(null=True, blank=True)
    session_turnover = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    # Market cap = ltp x listed_shares.  Edited in the admin or filled by `manage.py sync_listed_shares`.
    listed_shares = models.BigIntegerField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "Companies"
        ordering = ["symbol"]

    def __str__(self):
        return f"{self.symbol} - {self.name}"


class TrackedCompany(models.Model):
    company = models.OneToOneField(
        Company,
        on_delete=models.CASCADE,
        related_name="tracking",
    )

    is_tracked = models.BooleanField(
        default=True,
    )