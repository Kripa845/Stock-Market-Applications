from django.contrib import admin
from .models import Company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("symbol", "name", "sector", "listed_shares", "ltp", "previous_close", "prices_updated_at", "is_active")
    list_editable = ("listed_shares",)
    list_filter = ("sector", "is_active")
    search_fields = ("symbol", "name")
