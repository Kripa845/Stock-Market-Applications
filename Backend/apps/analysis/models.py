from django.db import models
from apps.companies.models import Company
# Create your models here.
class DailyAnalysis(models.Model):
    company=models.ForeignKey(Company,
        on_delete=models.CASCADE,
        related_name="daily_analysis"
)

    date = models.DateField()

    vwap = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True
    )

    close_price = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    volume = models.BigIntegerField()

    volume_average = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True
    )
    volume_anomaly = models.BooleanField(
        default=False
    )

    pressure = models.CharField(
        max_length=20,
        choices=[
            ("buying", "Buying"),
            ("selling", "Selling"),
            ("neutral", "Neutral"),
        ],
        default="neutral"
    )

    news_count = models.PositiveIntegerField(
        default=0
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "date"],
                name="unique_daily_analysis"
            )
        ]
        
        ordering =["-date"]
        
        
        def __str__(self):
            return (
                f"{self.company.symbol} |"
                 f"{self.date}"
            )