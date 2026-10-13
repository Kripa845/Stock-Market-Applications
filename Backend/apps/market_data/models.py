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
    
# class FloorsheetTransaction(models.Model):
#     company=models.ForeignKey(Company,on_delete=models.CASCADE)
#     date=models.DateField()
#     buyer_broker=models.IntegerField(unique=True)
#     seller_broker=models.IntegerField(unique=True)
#     quantity=models.IntegerField()
#     rate=models.IntegerField()
    
    
#     class Meta:
#         ordering = ['-date']

#     def __str__(self):
#         return f"Tx {self.id} | {self.company.symbol} | B#{self.buyer_broker} -> S#{self.seller_broker}"
    
    
class FloorsheetTransaction(models.Model):
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="floorsheet_transactions",
    )

    date = models.DateField()
    trade_time = models.DateTimeField(null=True, blank=True, db_index=True)

    transaction_id = models.CharField(
        max_length=100,
        blank=True,
    )

    buyer_broker = models.CharField(
        max_length=100,
    )

    seller_broker = models.CharField(
        max_length=100,
    )

    quantity = models.BigIntegerField()

    rate = models.DecimalField(
        max_digits=14,
        decimal_places=4,
    )

    amount = models.DecimalField(
        max_digits=20,
        decimal_places=4,
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        indexes = [
            models.Index(
                fields=["company", "date"],
            ),
            models.Index(
                fields=["buyer_broker"],
            ),
            models.Index(
                fields=["seller_broker"],
            ),
            # Intraday candles read one company's trades in time order.
            models.Index(
                fields=["company", "trade_time"],
                name="floorsheet_company_time_idx",
            ),
            # Market-wide one-day reads (top brokers) filter on date alone.
            models.Index(
                fields=["date"],
                name="floorsheet_date_idx",
            ),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "company",
                    "date",
                    "transaction_id",
                ],
                name="unique_floorsheet_transaction",
            )
        ]

    def __str__(self):
        return (
            f"{self.company.symbol} - "
            f"{self.date} - "
            f"{self.quantity}"
        )


class IntradayCandle(models.Model):
    """
    OHLCV candle for one company, interval and time bucket, built from the
    timestamped floorsheet trades by services.intraday_candles.  Only buckets
    with at least one trade exist; nothing is stored outside the session.
    """

    INTERVAL_CHOICES = [
        ("1m", "1 minute"),
        ("5m", "5 minutes"),
        ("15m", "15 minutes"),
        ("30m", "30 minutes"),
        ("1h", "1 hour"),
    ]

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="intraday_candles",
    )
    interval = models.CharField(max_length=4, choices=INTERVAL_CHOICES)
    # Start of the bucket (aware; buckets are aligned to Asia/Kathmandu session open).
    bucket_start = models.DateTimeField()

    open = models.DecimalField(max_digits=14, decimal_places=4)
    high = models.DecimalField(max_digits=14, decimal_places=4)
    low = models.DecimalField(max_digits=14, decimal_places=4)
    close = models.DecimalField(max_digits=14, decimal_places=4)
    volume = models.BigIntegerField()
    turnover = models.DecimalField(max_digits=20, decimal_places=4)
    trade_count = models.PositiveIntegerField()

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company", "interval", "bucket_start"]
        # The unique constraint is also the (company, interval, bucket_start)
        # index, so no separate Index is declared.
        constraints = [
            models.UniqueConstraint(
                fields=["company", "interval", "bucket_start"],
                name="unique_intraday_candle",
            )
        ]

    def __str__(self):
        return f"{self.company.symbol} | {self.interval} | {self.bucket_start} | close: {self.close}"


class Broker(models.Model):
    broker_no = models.PositiveIntegerField(
        unique=True,
        null=True,
        blank=True,
    )
    broker_code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    short_name = models.CharField(max_length=100, blank=True)
    # Logo filename maps to frontend/public/broker-logos/.
    logo = models.CharField(max_length=255, blank=True)
    website = models.URLField(blank=True)
    tms_link = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["broker_code"]

    def __str__(self):
        return f"{self.broker_code} - {self.name}"


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


class DividendAnnouncement(models.Model):
    """Proposed bonus / cash dividend for a company and fiscal year. Admin-editable."""

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="dividend_announcements",
    )
    fiscal_year = models.CharField(max_length=20, help_text="Nepali fiscal year, e.g. 2081/82.")
    bonus_pct = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    cash_pct = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    book_closure_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-book_closure_date", "company__symbol"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "fiscal_year"],
                name="unique_company_dividend_fiscal_year",
            )
        ]

    @property
    def total_pct(self):
        return (self.bonus_pct or 0) + (self.cash_pct or 0)

    def __str__(self):
        return f"{self.company.symbol} {self.fiscal_year}: {self.total_pct}%"
