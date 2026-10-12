from django.contrib import admin
from .models import DailyPrice, DividendAnnouncement, FloorsheetTransaction, IntradayCandle, TradingHoliday
# Register your models here.
admin.site.register(DailyPrice)
admin.site.register(FloorsheetTransaction)


@admin.register(TradingHoliday)
class TradingHolidayAdmin(admin.ModelAdmin):
    list_display = ("date", "name")
    search_fields = ("name",)
    date_hierarchy = "date"


@admin.register(DividendAnnouncement)
class DividendAnnouncementAdmin(admin.ModelAdmin):
    list_display = ("company", "fiscal_year", "bonus_pct", "cash_pct", "total_pct", "book_closure_date")
    list_filter = ("fiscal_year",)
    search_fields = ("company__symbol", "company__name")
    list_select_related = ("company",)


@admin.register(IntradayCandle)
class IntradayCandleAdmin(admin.ModelAdmin):
    list_display = ("company", "interval", "bucket_start", "open", "high", "low", "close", "volume", "trade_count")
    list_filter = ("interval",)
    search_fields = ("company__symbol",)
    date_hierarchy = "bucket_start"
    list_select_related = ("company",)
