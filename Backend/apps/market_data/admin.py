from django.contrib import admin
from .models import DailyPrice, DividendAnnouncement, FloorsheetTransaction, TradingHoliday
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
