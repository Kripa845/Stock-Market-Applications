from django.db import models
from apps.companies.models import Company
# Create your models here.
class DailyPrice(models.Model):
    company=models.ForeignKey(Company,on_delete=models.CASCADE)
    date=models.DateField()
    open=models.DecimalField(max_digits=15,decimal_places=2)
    high=models.DecimalField(max_digits=15,decimal_places=2)
    low=models.DecimalField(max_digits=15,decimal_places=2)
    close=models.DecimalField(max_digits=15,decimal_places=2)
    volume=models.BigIntegerField()
    
    turnover=models.DecimalField(max_digits=18,decimal_places=2)
    
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