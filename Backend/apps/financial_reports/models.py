from django.db import models

from apps.companies.models import Company


class FinancialReport(models.Model):
    """One financial report document scraped from nepalipaisa.com."""

    # financialReportDocumentId from the nepalipaisa API; makes re-syncing idempotent.
    document_id = models.BigIntegerField(unique=True)

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="financial_reports",
    )
    symbol = models.CharField(max_length=20, db_index=True)
    company_name = models.CharField(max_length=255, blank=True)

    duration = models.CharField(max_length=30, db_index=True)        # Monthly, 1st Quarter ... Annual
    fiscal_year_bs = models.CharField(max_length=20, db_index=True)  # e.g. 2083/2084
    fiscal_year_ad = models.CharField(max_length=20, blank=True)     # e.g. 2026/2027

    report_date_bs = models.CharField(max_length=20, blank=True)     # e.g. 2083-07-20
    report_date_ad = models.DateField(null=True, blank=True, db_index=True)

    title = models.CharField(max_length=500, blank=True)
    file_name = models.CharField(max_length=255, blank=True)         # pdf or jpg on nepalipaisa
    is_active = models.BooleanField(default=True)

    scraped_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-report_date_ad", "-document_id"]
        indexes = [
            models.Index(fields=["fiscal_year_bs", "duration"]),
        ]

    def __str__(self):
        return f"{self.symbol} {self.fiscal_year_bs} {self.duration}"
