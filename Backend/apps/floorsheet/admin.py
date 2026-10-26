from django.contrib import admin

from apps.floorsheet.models import Broker, FloorsheetTransaction, IntradayCandle

admin.site.register(FloorsheetTransaction)


@admin.register(Broker)
class BrokerAdmin(admin.ModelAdmin):
    list_display = ("broker_no", "name", "website", "tms_link", "membership_type", "is_active", "directory_synced_at")
    list_filter = ("is_active", "membership_type", "is_dealer")
    search_fields = ("broker_code", "name", "short_name", "website")
    readonly_fields = ("directory_synced_at", "updated_at")


@admin.register(IntradayCandle)
class IntradayCandleAdmin(admin.ModelAdmin):
    list_display = ("company", "interval", "bucket_start", "open", "high", "low", "close", "volume", "trade_count")
    list_filter = ("interval",)
    search_fields = ("company__symbol",)
    date_hierarchy = "bucket_start"
    list_select_related = ("company",)
