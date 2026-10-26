from django.db import models
from apps.companies.models import Company
# Create your models here.
class DailyPrice(models.Model):
    SOURCE_CHOICES = [("crawled", "Crawled"), ("seeded", "Seeded"), ("manual", "Manual"), ("unverified", "Unverified")]
    company=models.ForeignKey(Company,on_delete=models.CASCADE)
    source = models.CharField(max_length=16, choices=SOURCE_CHOICES, default="unverified", db_index=True)
    date=models.DateField()
    open=models.DecimalField(max_digits=15,decimal_places=2)
    high=models.DecimalField(max_digits=15,decimal_places=2)
    low=models.DecimalField(max_digits=15,decimal_places=2)
    close=models.DecimalField(max_digits=15,decimal_places=2)
    volume=models.BigIntegerField()
    
    turnover=models.DecimalField(max_digits=18,decimal_places=2)

    # Number of floorsheet trades that day; NULL until the floorsheet for that
    # company-day has been crawled.  Filled by services.price_fields.
    # (Previous close is never stored: services.movers derives it from the
    # trading calendar, so there is one definition everywhere.)
    transactions = models.PositiveIntegerField(null=True, blank=True)
    # ShareSansar's own "% change" (``per_change``) for the session, as published.
    # It is measured against the exchange's previous close, which is ADJUSTED for
    # bonus / right shares, so it can differ from close(t) vs close(t-1) of our
    # rows on a book-closure day.  NULL for rows crawled before this field existed.
    source_change_pct = models.DecimalField(max_digits=9, decimal_places=4, null=True, blank=True)

    class Meta:
     ordering = ['-date']

     constraints = [
        models.UniqueConstraint(
            fields=['company', 'date'],
            name='unique_company_daily_trading_data'
        )
    ]

     indexes = [
        models.Index(fields=['company', 'date']),
    ]

    def __str__(self):
        return f"{self.company.symbol} | {self.date} | close: {self.close}"


class TradingHoliday(models.Model):
    """A weekday NEPSE is closed (public holiday, special closure). Admin-editable."""

    date = models.DateField(unique=True)
    name = models.CharField(max_length=200)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.date} - {self.name}"


class LiveFeedStatus(models.Model):
    """
    Single row: when the NEPSE live feed was last fetched AND saved successfully.

    Kept in the DB (not the cache) because the Celery worker and the web server
    are separate processes and the project uses Django's per-process cache.
    """

    last_successful_fetch = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "Live feed status"

    def __str__(self):
        return f"Live feed last fetched {self.last_successful_fetch}"


