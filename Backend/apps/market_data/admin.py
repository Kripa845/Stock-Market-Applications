from django.contrib import admin

from apps.market_data.models import DailyPrice, TradingHoliday

admin.site.register(DailyPrice)


@admin.register(TradingHoliday)
class TradingHolidayAdmin(admin.ModelAdmin):
    list_display = ("date", "name")
    search_fields = ("name",)
    date_hierarchy = "date"
