from django.db import models
from apps.crawler_runs.models import CrawlRun
from django.conf import settings
# Create your models here.
class Company(models.Model):
    symbol=models.CharField(max_length=20,unique=True)
    name=models.CharField(max_length=300)
    sector=models.CharField(max_length=100)
    aliases = models.JSONField(
        default=list,
        blank=True,
    )
    is_active=models.BooleanField(default=True)
    created_by=models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_companies",)
    
    class Meta:
        verbose_name_plural = "Companies"
        ordering = ['symbol']
        
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


