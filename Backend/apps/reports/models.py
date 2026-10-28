"""
Company fundamentals: dividends, EPS and quarterly report figures.

These models moved here from market_data; ``db_table`` keeps their original tables.
"""

from django.db import models

from apps.companies.models import Company


class DividendAnnouncement(models.Model):
    """
    Proposed bonus / cash dividend for a listed company and fiscal year.

    Crawled for every listed stock from ShareSansar's "Proposed Dividend" table
    (spider ``dividends``), so the key is ``symbol``, not the Company FK: most listed
    stocks are not in the Company table.  ``company`` is linked when the symbol is one
    of ours.  Re-crawls upsert on (symbol, fiscal_year).  A source row without a symbol
    or a fiscal year cannot use that key: it is kept with ``missing_fields`` set and
    upserted on (source, source_id) instead.  Rows can still be added in the admin.
    """

    class Status(models.TextChoices):
        PROPOSED = "proposed", "Proposed"
        AGM_APPROVED = "agm_approved", "AGM approved"
        SEBON_APPROVED = "sebon_approved", "SEBON approved"
        DISTRIBUTED = "distributed", "Distributed"

    # Stages only move forward: a re-crawl never moves a row back (services.dividends).
    STATUS_ORDER = [Status.PROPOSED, Status.AGM_APPROVED, Status.SEBON_APPROVED, Status.DISTRIBUTED]

    symbol = models.CharField(max_length=20, blank=True, db_index=True)
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dividend_announcements",
    )
    company_name = models.CharField(max_length=300, blank=True)
    fiscal_year = models.CharField(max_length=20, blank=True, help_text="Nepali fiscal year, e.g. 2081/2082.")
    bonus_pct = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    cash_pct = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    # Paid-up value per share from the ShareSansar company page; NULL until crawled.
    face_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    announcement_date = models.DateField(null=True, blank=True)
    book_closure_date = models.DateField(null=True, blank=True)
    distribution_date = models.DateField(null=True, blank=True)
    bonus_listing_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PROPOSED, db_index=True)
    # "symbol" / "fiscal_year" when the crawled row did not have it.
    missing_fields = models.JSONField(default=list, blank=True)
    source = models.CharField(max_length=32, default="manual")
    source_id = models.CharField(max_length=32, blank=True)
    scraped_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "market_data_dividendannouncement"
        ordering = ["-book_closure_date", "symbol"]
        constraints = [
            models.UniqueConstraint(
                fields=["symbol", "fiscal_year"],
                condition=~models.Q(symbol="") & ~models.Q(fiscal_year=""),
                name="unique_dividend_symbol_fiscal_year",
            )
        ]
        indexes = [models.Index(fields=["source", "source_id"])]

    @property
    def total_pct(self):
        return (self.bonus_pct or 0) + (self.cash_pct or 0)

    def __str__(self):
        return f"{self.symbol or '?'} {self.fiscal_year or '?'}: {self.total_pct}%"


class CompanyEarnings(models.Model):
    """
    EPS as published for a symbol, fiscal year and quarter (Merolagani company page).
    Nepali quarterly reports are cumulative, so quarter 4 is the full-year EPS that
    dividend payout ratios use.  Re-crawls upsert on (symbol, fiscal_year, quarter).
    """

    symbol = models.CharField(max_length=20)
    fiscal_year = models.CharField(max_length=20)
    quarter = models.PositiveSmallIntegerField()
    eps = models.DecimalField(max_digits=12, decimal_places=2)
    source = models.CharField(max_length=32, default="Merolagani")
    scraped_at = models.DateTimeField()

    class Meta:
        db_table = "market_data_companyearnings"
        verbose_name_plural = "Company earnings"
        ordering = ["symbol", "-fiscal_year", "-quarter"]
        constraints = [
            models.UniqueConstraint(fields=["symbol", "fiscal_year", "quarter"], name="unique_company_earnings"),
        ]

    def __str__(self):
        return f"{self.symbol} {self.fiscal_year} Q{self.quarter}: EPS {self.eps}"


class QuarterlyReport(models.Model):
    """
    Figures as filed in a tracked company's quarterly report, crawled from nepsetrading's
    Latest Report pages (``manage.py crawl_quarterly_reports``) or hand-imported from a CSV
    (``manage.py import_quarterly_reports``).
    Only raw filed numbers are stored; PE, PB, yields and YoY are calculated per request
    (services/quarterly_reports.py) so they follow the latest price.  Filings are often
    unaudited and later revised: a re-import overwrites the row (unique company, FY, quarter).

    Figures are cumulative for the fiscal year.  ``eps`` is the annualized EPS as filed; when
    it is blank it is derived from net profit / share count, annualized by 4 / quarter.

    ``dpps_avg`` / ``dpps_avg_years`` / ``previous_dpps`` come from the crawled source, which
    has years of history we do not; when blank they are derived from YearlyDPPS and last
    year's report.
    """

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="quarterly_reports")
    fiscal_year = models.CharField(max_length=20, help_text="Nepali fiscal year, e.g. 2082/2083.")
    quarter = models.PositiveSmallIntegerField()
    reported_on = models.DateField(null=True, blank=True)

    net_profit = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    net_worth = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    distributable_profit = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    share_count = models.BigIntegerField(null=True, blank=True)

    eps = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    book_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    dpps = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    # Kept for reference only: ratios always use the latest crawled price.
    price_on_report_date = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    dpps_avg = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                   help_text="Average yearly DPPS as given by the source.")
    dpps_avg_years = models.PositiveSmallIntegerField(null=True, blank=True)
    previous_dpps = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                        help_text="DPPS of the same quarter last year, as given by the source.")

    source = models.CharField(max_length=32, default="manual")
    scraped_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "market_data_quarterlyreport"
        ordering = ["company__symbol", "-fiscal_year", "-quarter"]
        constraints = [
            models.UniqueConstraint(fields=["company", "fiscal_year", "quarter"], name="unique_quarterly_report"),
        ]
        indexes = [models.Index(fields=["fiscal_year", "quarter"])]

    def __str__(self):
        return f"{self.company.symbol} {self.fiscal_year} Q{self.quarter}"


class YearlyDPPS(models.Model):
    """Distributable profit per share for a full fiscal year; feeds the N-year average."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="yearly_dpps")
    fiscal_year = models.CharField(max_length=20)
    dpps = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "market_data_yearlydpps"
        verbose_name = "Yearly DPPS"
        verbose_name_plural = "Yearly DPPS"
        ordering = ["company__symbol", "-fiscal_year"]
        constraints = [
            models.UniqueConstraint(fields=["company", "fiscal_year"], name="unique_yearly_dpps"),
        ]

    def __str__(self):
        return f"{self.company.symbol} {self.fiscal_year}: DPPS {self.dpps}"


class IpoIssue(models.Model):
    """
    A public issue (IPO, FPO, right share, mutual fund, debenture) of any company, crawled
    from ShareSansar's "Existing Issues" tables (spider ``ipo_issues``).  Whole market: most
    issuers are not in the Company table, so ``company`` is linked only when the symbol is ours.

    ShareSansar has no issue id, so ``source_id`` is "<issue type>-<ShareSansar company id>-<units>",
    which stays the same while the dates of an upcoming issue are filled in.
    """

    class IssueType(models.TextChoices):
        IPO = "ipo", "IPO"
        IPO_LOCAL = "ipo_local", "IPO (project-affected locals)"
        IPO_MIGRANT = "ipo_migrant", "IPO (migrant workers)"
        IPO_QII = "ipo_qii", "IPO (qualified institutional investors)"
        FPO = "fpo", "FPO"
        RIGHT = "right", "Right share"
        MUTUAL_FUND = "mutual_fund", "Mutual fund"
        DEBENTURE = "debenture", "Bond / debenture"

    issue_type = models.CharField(max_length=20, choices=IssueType.choices, db_index=True)
    symbol = models.CharField(max_length=20, blank=True, db_index=True)
    company = models.ForeignKey(
        "companies.Company", on_delete=models.SET_NULL, null=True, blank=True, related_name="ipo_issues",
    )
    company_name = models.CharField(max_length=300, blank=True)
    units = models.BigIntegerField(null=True, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    # Right shares only, e.g. "1:1".
    ratio = models.CharField(max_length=20, blank=True)
    issue_manager = models.CharField(max_length=200, blank=True)
    open_date = models.DateField(null=True, blank=True, db_index=True)
    # Earliest closing date; the issue can stay open until ``final_date`` if undersubscribed.
    close_date = models.DateField(null=True, blank=True, db_index=True)
    final_date = models.DateField(null=True, blank=True)
    listing_date = models.DateField(null=True, blank=True)
    # ShareSansar's own status code as published (-2, -1, 0, 1); kept for auditing only.
    source_status = models.SmallIntegerField(null=True, blank=True)
    announcement_url = models.CharField(max_length=1000, blank=True)
    source = models.CharField(max_length=32, default="ShareSansar")
    source_id = models.CharField(max_length=64)
    scraped_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-open_date", "symbol"]
        constraints = [
            models.UniqueConstraint(fields=["source", "source_id"], name="unique_ipo_issue_source_id"),
        ]

    def __str__(self):
        return f"{self.get_issue_type_display()} {self.symbol or self.company_name} ({self.open_date or 'no dates'})"
