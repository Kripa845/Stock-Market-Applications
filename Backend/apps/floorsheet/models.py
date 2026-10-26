"""
Floorsheet trades, the broker directory and the intraday candles built from the trades.

These models moved here from market_data; ``db_table`` keeps their original tables.
"""

from django.db import models

from apps.companies.models import Company


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
        db_table = "market_data_floorsheettransaction"
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
        db_table = "market_data_intradaycandle"
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
    # Directory details from ``manage.py sync_broker_directory`` (services/broker_directory.py):
    # NEPSE's member list (official) and ShareHub's broker profiles (website, offices).
    membership_type = models.CharField(max_length=100, blank=True)
    nepse_status = models.CharField(max_length=20, blank=True)
    is_dealer = models.BooleanField(default=False)
    contact_person = models.CharField(max_length=150, blank=True)
    address = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=150, blank=True)
    email = models.CharField(max_length=254, blank=True)
    # [{"name", "address", "phone", "email"}], head office first.
    branches = models.JSONField(default=list, blank=True)
    directory_synced_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "market_data_broker"
        ordering = ["broker_code"]

    def __str__(self):
        return f"{self.broker_code} - {self.name}"
