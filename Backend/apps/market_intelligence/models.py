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
    """"Tracked Basket" index over the tracked companies (not the NEPSE index).

    ``level`` / ``daily_return_pct`` are the original turnover-weighted
    variant (weights = previous session's turnover).  ``equal_weight_*`` is the
    same basket with every eligible company weighted equally.  Both start at
    1000 on the first valid session and skip the same corporate-action days.
    """

    date = models.DateField(unique=True)
    level = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    daily_return_pct = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    equal_weight_level = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    equal_weight_return_pct = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
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


class SupportResistanceSet(models.Model):
    """Latest support / resistance computation for one company (replaced on every run)."""

    STATUS_OK = "ok"
    STATUS_INSUFFICIENT = "insufficient_history"
    STATUS_NO_LEVELS = "no_levels"
    STATUS_CHOICES = [
        (STATUS_OK, "OK"),
        (STATUS_INSUFFICIENT, "Insufficient history"),
        (STATUS_NO_LEVELS, "No levels found"),
    ]

    company = models.OneToOneField("companies.Company", on_delete=models.CASCADE, related_name="support_resistance")
    as_of = models.DateField()                                     # latest session used
    status = models.CharField(max_length=24, choices=STATUS_CHOICES)
    latest_close = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    sessions_used = models.PositiveIntegerField(default=0)
    window_start = models.DateField(null=True, blank=True)
    # History before this date was dropped: a price adjustment with no usable factor.
    adjustment_cut = models.DateField(null=True, blank=True)
    # Sessions whose earlier bars were back-adjusted (bonus / right shares), oldest first.
    adjustments = models.JSONField(default=list, blank=True)
    params = models.JSONField(default=dict, blank=True)
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company_id"]

    def __str__(self):
        return f"S&R {self.company_id} as of {self.as_of} ({self.status})"


class SupportResistanceLevel(models.Model):
    """One clustered price level: swing highs / lows within the tolerance of each other."""

    KIND_SUPPORT = "support"
    KIND_RESISTANCE = "resistance"
    KIND_CHOICES = [(KIND_SUPPORT, "Support"), (KIND_RESISTANCE, "Resistance")]

    set = models.ForeignKey(SupportResistanceSet, on_delete=models.CASCADE, related_name="levels")
    price = models.DecimalField(max_digits=15, decimal_places=4)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    touches = models.PositiveSmallIntegerField()
    strength = models.DecimalField(max_digits=10, decimal_places=4)
    first_touch = models.DateField()
    last_touch = models.DateField()
    at_price = models.BooleanField(default=False)                  # within a hair of the latest close

    class Meta:
        ordering = ["-price"]
        indexes = [models.Index(fields=["set", "kind"])]

    def __str__(self):
        return f"{self.kind} {self.price} ({self.touches} touches)"
