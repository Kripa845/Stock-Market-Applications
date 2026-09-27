# from django.db import models

# from apps.companies.models import Company


# class DailyAnalysis(models.Model):
#     """
#     One row per company per trading day: the stored analytical state.

#     This model holds DERIVED values only.  Raw OHLCV stays in
#     ``market_data.DailyPrice`` and is never duplicated here beyond the
#     two anchors (``close_price``, ``volume``) that the metrics are
#     expressed against, which are kept so the frontend can render a row
#     without a second join.

#     Everything here is written by ``apps.analysis.tasks``, never
#     recomputed inside a request handler.
#     """

#     company = models.ForeignKey(
#         Company,
#         on_delete=models.CASCADE,
#         related_name="daily_analysis",
#     )

#     date = models.DateField()

#     # ------------------------------------------------------------------
#     # VWAP
#     # ------------------------------------------------------------------

#     vwap = models.DecimalField(
#         max_digits=14,
#         decimal_places=4,
#         null=True,
#         blank=True,
#         help_text=(
#             "DAILY VWAP for this trading day = daily turnover / daily "
#             "volume. NULL when volume is zero or turnover is missing."
#         ),
#     )

#     vwap_30d = models.DecimalField(
#         max_digits=14,
#         decimal_places=4,
#         null=True,
#         blank=True,
#         help_text=(
#             "Separate 30-day aggregate summary metric = SUM(turnover) / "
#             "SUM(volume) across the rolling window. Not the daily VWAP."
#         ),
#     )

#     # ------------------------------------------------------------------
#     # Price anchors
#     # ------------------------------------------------------------------

#     close_price = models.DecimalField(
#         max_digits=12,
#         decimal_places=2,
#     )

#     previous_close = models.DecimalField(
#         max_digits=12,
#         decimal_places=2,
#         null=True,
#         blank=True,
#         help_text="Close of the previous TRADING SESSION. Independent of VWAP.",
#     )

#     daily_return_pct = models.DecimalField(
#         max_digits=10,
#         decimal_places=4,
#         null=True,
#         blank=True,
#         help_text="(close - previous_close) / previous_close * 100.",
#     )

#     # ------------------------------------------------------------------
#     # Volume baseline
#     # ------------------------------------------------------------------

#     volume = models.BigIntegerField()

#     volume_average = models.DecimalField(
#         max_digits=20,
#         decimal_places=2,
#         null=True,
#         blank=True,
#         help_text=(
#             "Mean volume of the PREVIOUS 20 TRADING SESSIONS (not "
#             "calendar days, and never including this day's own volume)."
#         ),
#     )

#     volume_ratio = models.DecimalField(
#         max_digits=8,
#         decimal_places=2,
#         null=True,
#         blank=True,
#         help_text="volume / volume_average. NULL when no usable baseline.",
#     )

#     volume_anomaly = models.BooleanField(
#         default=False,
#         help_text="True when volume_ratio >= 1.5 on a full 20-session baseline.",
#     )

#     volume_baseline_sessions = models.PositiveSmallIntegerField(
#         default=0,
#         help_text="How many previous sessions the baseline was actually built from.",
#     )

#     has_sufficient_history = models.BooleanField(
#         default=False,
#         help_text="True once 20 previous trading sessions are available.",
#     )

#     # ------------------------------------------------------------------
#     # Pressure proxy
#     # ------------------------------------------------------------------

#     pressure = models.CharField(
#         max_length=20,
#         choices=[
#             ("buying", "Buying"),
#             ("selling", "Selling"),
#             ("neutral", "Neutral"),
#         ],
#         default="neutral",
#     )

#     pressure_score = models.DecimalField(
#         max_digits=6,
#         decimal_places=2,
#         null=True,
#         blank=True,
#         help_text="Deterministic OHLCV score in the range -100 .. +100.",
#     )

#     pressure_method = models.CharField(
#         max_length=40,
#         default="OHLCV_PRICE_VOLUME",
#         help_text=(
#             "Methodology identifier. OHLCV_PRICE_VOLUME is a published-data "
#             "proxy and is not evidence of order-book buying or selling."
#         ),
#     )

#     # ------------------------------------------------------------------

#     news_count = models.PositiveIntegerField(
#         default=0,
#     )

#     created_at = models.DateTimeField(
#         auto_now_add=True,
#     )

#     updated_at = models.DateTimeField(
#         auto_now=True,
#         null=True,
#     )

#     class Meta:
#         constraints = [
#             models.UniqueConstraint(
#                 fields=["company", "date"],
#                 name="unique_daily_analysis",
#             )
#         ]

#         indexes = [
#             models.Index(fields=["company", "date"]),
#         ]

#         ordering = ["-date"]

#         verbose_name_plural = "Daily analyses"

#     @property
#     def volume_avg_20d(self):
#         """Readable alias for ``volume_average``, which is the 20-session mean."""
#         return self.volume_average

#     def __str__(self):
#         return f"{self.company.symbol} | {self.date} | vwap: {self.vwap}"
from django.db import models

from apps.companies.models import Company


class DailyAnalysis(models.Model):
    """
    One row per company per trading day: the stored analytical state.

    This model holds DERIVED values only.  Raw OHLCV stays in
    ``market_data.DailyPrice`` and is never duplicated here beyond the
    two anchors (``close_price``, ``volume``) that the metrics are
    expressed against, which are kept so the frontend can render a row
    without a second join.

    Everything here is written by ``apps.analysis.tasks``, never
    recomputed inside a request handler.
    """

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="daily_analysis",
    )

    date = models.DateField()

    # ------------------------------------------------------------------
    # VWAP
    # ------------------------------------------------------------------

    vwap = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
        help_text=(
            "DAILY VWAP for this trading day = daily turnover / daily "
            "volume. NULL when volume is zero or turnover is missing."
        ),
    )

    vwap_30d = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
        help_text=(
            "Separate 30-day aggregate summary metric = SUM(turnover) / "
            "SUM(volume) across the rolling window. Not the daily VWAP."
        ),
    )

    # ------------------------------------------------------------------
    # Price anchors
    # ------------------------------------------------------------------

    close_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    previous_close = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Close of the previous TRADING SESSION. Independent of VWAP.",
    )

    daily_return_pct = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="(close - previous_close) / previous_close * 100.",
    )

    # ------------------------------------------------------------------
    # Volume baseline
    # ------------------------------------------------------------------

    volume = models.BigIntegerField()

    volume_average = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=(
            "Mean volume of the PREVIOUS 20 TRADING SESSIONS (not "
            "calendar days, and never including this day's own volume)."
        ),
    )

    volume_ratio = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="volume / volume_average. NULL when no usable baseline.",
    )

    volume_anomaly = models.BooleanField(
        default=False,
        help_text="True when volume_ratio >= 1.5 on a full 20-session baseline.",
    )

    volume_baseline_sessions = models.PositiveSmallIntegerField(
        default=0,
        help_text="How many previous sessions the baseline was actually built from.",
    )

    has_sufficient_history = models.BooleanField(
        default=False,
        help_text="True once 20 previous trading sessions are available.",
    )

    # ------------------------------------------------------------------
    # Pressure proxy
    # ------------------------------------------------------------------

    pressure = models.CharField(
        max_length=20,
        choices=[
            ("buying", "Buying"),
            ("selling", "Selling"),
            ("neutral", "Neutral"),
        ],
        default="neutral",
    )

    pressure_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Deterministic OHLCV score in the range -100 .. +100.",
    )

    pressure_method = models.CharField(
        max_length=40,
        default="OHLCV_PRICE_VOLUME",
        help_text=(
            "Methodology identifier. OHLCV_PRICE_VOLUME is a published-data "
            "proxy and is not evidence of order-book buying or selling."
        ),
    )

    # ------------------------------------------------------------------

    news_count = models.PositiveIntegerField(
        default=0,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        null=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "date"],
                name="unique_daily_analysis",
            )
        ]

        indexes = [
            models.Index(fields=["company", "date"]),
        ]

        ordering = ["-date"]

        verbose_name_plural = "Daily analyses"

    @property
    def volume_avg_20d(self):
        """Readable alias for ``volume_average``, which is the 20-session mean."""
        return self.volume_average

    def __str__(self):
        return f"{self.company.symbol} | {self.date} | vwap: {self.vwap}"


class VolumeAnomaly(models.Model):
    """Persisted rolling volume statistics for one company trading session."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="volume_anomalies")
    date = models.DateField()
    volume = models.BigIntegerField()
    rolling_mean = models.FloatField(null=True, blank=True)
    rolling_std = models.FloatField(null=True, blank=True)
    z_score = models.FloatField(null=True, blank=True)
    pct_of_avg = models.FloatField(null=True, blank=True)
    is_anomaly = models.BooleanField(default=False)
    insufficient_data = models.BooleanField(default=False)
    reason = models.CharField(max_length=16, blank=True)

    class Meta:
        ordering = ["-date"]
        constraints = [models.UniqueConstraint(fields=["company", "date"], name="unique_company_volume_anomaly")]
        indexes = [models.Index(fields=["company", "date", "is_anomaly"])]


class NewsPriceCorrelation(models.Model):
    """Latest persisted exploratory news-intensity correlation per company."""

    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name="news_price_correlation")
    computed_at = models.DateTimeField(auto_now=True)
    results = models.JSONField(default=dict)
