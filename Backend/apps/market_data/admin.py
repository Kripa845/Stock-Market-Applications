from django.contrib import admin
from .models import (
    Broker, CompanyEarnings, DailyPrice, DividendAnnouncement, FloorsheetTransaction, IntradayCandle, QuarterlyReport,
    TradingHoliday, YearlyDPPS,
)
# Register your models here.
admin.site.register(DailyPrice)
admin.site.register(FloorsheetTransaction)


@admin.register(Broker)
class BrokerAdmin(admin.ModelAdmin):
    list_display = ("broker_no", "name", "website", "tms_link", "membership_type", "is_active", "directory_synced_at")
    list_filter = ("is_active", "membership_type", "is_dealer")
    search_fields = ("broker_code", "name", "short_name", "website")
    readonly_fields = ("directory_synced_at", "updated_at")


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


@admin.register(QuarterlyReport)
class QuarterlyReportAdmin(admin.ModelAdmin):
    list_display = ("company", "fiscal_year", "quarter", "reported_on", "eps", "book_value", "dpps", "updated_at")
    list_filter = ("fiscal_year", "quarter", "company__sector")
    search_fields = ("company__symbol", "company__name")
    list_select_related = ("company",)


@admin.register(YearlyDPPS)
class YearlyDPPSAdmin(admin.ModelAdmin):
    list_display = ("company", "fiscal_year", "dpps")
    list_filter = ("fiscal_year",)
    search_fields = ("company__symbol",)
    list_select_related = ("company",)


@admin.register(IntradayCandle)
class IntradayCandleAdmin(admin.ModelAdmin):
    list_display = ("company", "interval", "bucket_start", "open", "high", "low", "close", "volume", "trade_count")
    list_filter = ("interval",)
    search_fields = ("company__symbol",)
    date_hierarchy = "bucket_start"
    list_select_related = ("company",)
