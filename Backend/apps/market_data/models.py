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

    # End-of-day fields for change calculations.  Raw numbers only.
    #   ltp         last traded price; the source is end-of-day, so it equals close.
    #   prev_close  the company's close on its previous stored trading day
    #               (not adjusted for bonus/right/dividend book closures).
    #   transactions number of floorsheet trades that day; NULL until the
    #               floorsheet for that company-day has been crawled.
    # Filled by services.price_fields.derive_price_fields.
    ltp = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    prev_close = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    transactions = models.PositiveIntegerField(null=True, blank=True)

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
