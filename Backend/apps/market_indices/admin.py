from django.contrib import admin

from .models import CompanyDaily, IndexCalibration, IndexCheck, IndexDaily, MarketIndex, MarketStockDaily, StockSector


@admin.register(MarketIndex)
class MarketIndexAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "kind", "sector_name", "sort_order")
    list_filter = ("kind",)


@admin.register(IndexDaily)
class IndexDailyAdmin(admin.ModelAdmin):
    list_display = ("index", "date", "open", "high", "low", "close", "source")
    list_filter = ("index", "source")
    date_hierarchy = "date"


@admin.register(StockSector)
class StockSectorAdmin(admin.ModelAdmin):
    list_display = ("symbol", "sector")
    list_filter = ("sector",)
    search_fields = ("symbol",)


@admin.register(MarketStockDaily)
class MarketStockDailyAdmin(admin.ModelAdmin):
    list_display = ("symbol", "sector", "date", "close", "volume", "turnover", "transactions")
    list_filter = ("sector", "date")
    search_fields = ("symbol",)


@admin.register(CompanyDaily)
class CompanyDailyAdmin(admin.ModelAdmin):
    list_display = ("symbol", "date", "sector", "share_class", "close", "traded", "listed_shares",
                    "listed_shares_source", "public_shares")
    list_filter = ("sector", "share_class", "traded", "listed_shares_source")
    search_fields = ("symbol",)
    date_hierarchy = "date"


@admin.register(IndexCalibration)
class IndexCalibrationAdmin(admin.ModelAdmin):
    list_display = ("index", "effective_date", "k", "published_close", "market_cap", "constituents")
    list_filter = ("index",)


@admin.register(IndexCheck)
class IndexCheckAdmin(admin.ModelAdmin):
    list_display = ("index", "date", "computed", "published", "diff", "flagged", "needs_recalibration")
    list_filter = ("index", "flagged", "needs_recalibration")
    date_hierarchy = "date"
