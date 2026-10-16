from django.contrib import admin
from .models import CompanyEarnings, DailyPrice, DividendAnnouncement, FloorsheetTransaction, IntradayCandle, TradingHoliday
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
    list_display = ("symbol", "fiscal_year", "bonus_pct", "cash_pct", "total_pct", "book_closure_date", "status", "source")
    list_filter = ("status", "fiscal_year", "source")
    search_fields = ("symbol", "company_name", "company__name")
    list_select_related = ("company",)
    readonly_fields = ("missing_fields", "source_id", "scraped_at")


@admin.register(CompanyEarnings)
class CompanyEarningsAdmin(admin.ModelAdmin):
    list_display = ("symbol", "fiscal_year", "quarter", "eps", "source", "scraped_at")
    list_filter = ("fiscal_year", "quarter")
    search_fields = ("symbol",)


@admin.register(IntradayCandle)
class IntradayCandleAdmin(admin.ModelAdmin):
    list_display = ("company", "interval", "bucket_start", "open", "high", "low", "close", "volume", "trade_count")
    list_filter = ("interval",)
    search_fields = ("company__symbol",)
    date_hierarchy = "bucket_start"
    list_select_related = ("company",)
