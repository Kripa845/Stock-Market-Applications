"""
NEPSE indices, sub-indices and whole-market daily data.

Scope: these tables describe the WHOLE NEPSE market (every listed stock), unlike
``market_data.DailyPrice`` which only holds the tracked companies.  They are kept
in separate tables on purpose so tracked-only analysis is never polluted.

Only crawled data is stored.  Nothing here is simulated or back-filled.
"""

from django.db import models


class MarketIndex(models.Model):
    """Catalogue of NEPSE indices: 4 main indices + 13 sub-indices."""

    KIND_MAIN = "main"
    KIND_SUB = "sub"
    KIND_CHOICES = [(KIND_MAIN, "Main index"), (KIND_SUB, "Sub index")]

    code = models.CharField(max_length=40, unique=True)          # "NEPSE", "BANKING"
    name = models.CharField(max_length=80)                        # "Banking Sub-Index"
    kind = models.CharField(max_length=4, choices=KIND_CHOICES, db_index=True)
    # Normalised sector label used in StockSector / MarketStockDaily for this
    # sub-index (blank for main indices).
    sector_name = models.CharField(max_length=100, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["kind", "sort_order", "code"]

    def __str__(self):
        return self.name


class IndexDaily(models.Model):
    """
    One scraped OHLC row per index per session.

    The previous close is NOT stored: it is the close of the previous row of the
    same index (same convention as DailyPrice / services.movers).
    """

    index = models.ForeignKey(MarketIndex, on_delete=models.CASCADE, related_name="daily")
    date = models.DateField(db_index=True)
    open = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    high = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    low = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    close = models.DecimalField(max_digits=14, decimal_places=2)
    # Session totals of the index's constituents, as published by NEPSE (NULL = not published).
    turnover = models.DecimalField(max_digits=22, decimal_places=2, null=True, blank=True)
    volume = models.BigIntegerField(null=True, blank=True)
    transactions = models.PositiveIntegerField(null=True, blank=True)
    # NEPSE's own % change vs the previous session, computed from unrounded values
    # (matters for small indices such as Mutual Fund at ~19.5 points).
    source_change_pct = models.DecimalField(max_digits=9, decimal_places=4, null=True, blank=True)
    source = models.CharField(max_length=16, default="crawled", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(fields=["index", "date"], name="unique_index_daily"),
        ]
        indexes = [models.Index(fields=["index", "date"])]

    def __str__(self):
        return f"{self.index.code} | {self.date} | close: {self.close}"


class IndexIntradayPoint(models.Model):
    """
    NEPSE's live index value during a session, saved every couple of minutes by
    ``snapshot_live_index`` (NEPSE serves no intraday history once the session is
    over).  ``recorded_at`` is NEPSE's own ``generatedTime``, not our fetch time.
    """

    index = models.ForeignKey(MarketIndex, on_delete=models.CASCADE, related_name="intraday")
    recorded_at = models.DateTimeField(db_index=True)
    value = models.DecimalField(max_digits=14, decimal_places=2)
    previous_close = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    change = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    change_pct = models.DecimalField(max_digits=9, decimal_places=4, null=True, blank=True)

    class Meta:
        ordering = ["index", "recorded_at"]
        constraints = [
            models.UniqueConstraint(fields=["index", "recorded_at"], name="unique_index_intraday_point"),
        ]

    def __str__(self):
        return f"{self.index.code} | {self.recorded_at} | {self.value}"


class StockSector(models.Model):
    """symbol -> normalised sub-index sector, for every listed stock (not only tracked)."""

    symbol = models.CharField(max_length=20, unique=True)
    sector = models.CharField(max_length=100, db_index=True)

    class Meta:
        ordering = ["symbol"]

    def __str__(self):
        return f"{self.symbol} -> {self.sector}"


class MarketStockDaily(models.Model):
    """Whole-market daily row per listed stock."""

    UNCLASSIFIED = "Unclassified"

    symbol = models.CharField(max_length=20)
    sector = models.CharField(max_length=100, db_index=True, default=UNCLASSIFIED)
    date = models.DateField(db_index=True)
    close = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    # Previous close exactly as published by the source (used for LTP / CH% in Top lists).
    prev_close = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    volume = models.BigIntegerField(default=0)
    turnover = models.DecimalField(max_digits=22, decimal_places=2, default=0)
    # NULL when the source does not publish a transaction count for the row.
    transactions = models.PositiveIntegerField(null=True, blank=True)
    source = models.CharField(max_length=16, default="crawled", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "symbol"]
        constraints = [
            models.UniqueConstraint(fields=["symbol", "date"], name="unique_market_stock_daily"),
        ]
        indexes = [models.Index(fields=["date", "sector"])]

    def __str__(self):
        return f"{self.symbol} | {self.date} | turnover: {self.turnover}"
