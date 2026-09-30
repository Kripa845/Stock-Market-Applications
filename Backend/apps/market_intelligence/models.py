from django.db import models


class MarketBreadthSnapshot(models.Model):
    """Market-wide breadth for one date in the global DailyPrice calendar."""

    date = models.DateField(unique=True)
    market_session_count = models.PositiveIntegerField(default=0)
    advances = models.PositiveIntegerField(default=0)
    declines = models.PositiveIntegerField(default=0)
    unchanged = models.PositiveIntegerField(default=0)
    return_eligible_count = models.PositiveIntegerField(default=0)
    above_50_dma_count = models.PositiveIntegerField(default=0)
    valid_50_dma_count = models.PositiveIntegerField(default=0)
    above_50_dma_pct = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True)
    above_200_dma_count = models.PositiveIntegerField(default=0)
    valid_200_dma_count = models.PositiveIntegerField(default=0)
    above_200_dma_pct = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True)
    corporate_action_excluded_count = models.PositiveIntegerField(default=0)
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date"]


class ProxyIndexSnapshot(models.Model):
    """Turnover-weighted market proxy, versioned for future methodology changes."""

    date = models.DateField(unique=True)
    level = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    daily_return_pct = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    eligible_company_count = models.PositiveIntegerField(default=0)
    corporate_action_excluded_count = models.PositiveIntegerField(default=0)
    methodology_version = models.CharField(max_length=32, default="turnover-weighted-v1")
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date"]


class CompanyTechnicalSnapshot(models.Model):
    """Daily, published-price technical levels and signals for one company."""

    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="technical_snapshots")
    date = models.DateField()
    support_20 = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    resistance_20 = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    support_60 = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    resistance_60 = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    breakout_20_up = models.BooleanField(null=True, blank=True)
    breakout_20_down = models.BooleanField(null=True, blank=True)
    breakout_55_up = models.BooleanField(null=True, blank=True)
    breakout_55_down = models.BooleanField(null=True, blank=True)
    patterns = models.JSONField(default=list, blank=True)
    dma_50 = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    dma_200 = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    signal = models.CharField(max_length=32, default="insufficient_history")
    signal_score = models.SmallIntegerField(null=True, blank=True)
    history_sessions = models.PositiveIntegerField(default=0)
    sufficient_history = models.BooleanField(default=False)
    possible_corporate_action = models.BooleanField(default=False)
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "company_id"]
        constraints = [
            models.UniqueConstraint(fields=["company", "date"], name="unique_company_technical_snapshot"),
        ]
        indexes = [models.Index(fields=["date", "signal"])]


class SectorRotationSnapshot(models.Model):
    """Turnover-weighted sector returns and ranks for rolling session windows."""

    sector = models.CharField(max_length=100)
    date = models.DateField()
    return_1w = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    return_1m = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    return_3m = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    rank_1w = models.PositiveIntegerField(null=True, blank=True)
    rank_1m = models.PositiveIntegerField(null=True, blank=True)
    rank_3m = models.PositiveIntegerField(null=True, blank=True)
    previous_rank_1w = models.PositiveIntegerField(null=True, blank=True)
    previous_rank_1m = models.PositiveIntegerField(null=True, blank=True)
    previous_rank_3m = models.PositiveIntegerField(null=True, blank=True)
    turnover = models.DecimalField(max_digits=22, decimal_places=4, default=0)
    company_count = models.PositiveIntegerField(default=0)
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date", "sector"]
        constraints = [
            models.UniqueConstraint(fields=["sector", "date"], name="unique_sector_rotation_snapshot"),
        ]
        indexes = [models.Index(fields=["date", "rank_1w"])]
