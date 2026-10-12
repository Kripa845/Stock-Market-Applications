from django.contrib import admin

from .models import IndexDaily, MarketIndex, MarketStockDaily, StockSector


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
