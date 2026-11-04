from django.contrib import admin
from .models import Company

from .models import Shareholding

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("symbol", "name", "sector", "listed_shares", "ltp", "previous_close", "prices_updated_at", "is_active")
    list_editable = ("listed_shares",)
    list_filter = ("sector", "is_active")
    search_fields = ("symbol", "name")
    
@admin.register(Shareholding)
class ShareholdingAdmin(admin.ModelAdmin):
    list_display = ("company", "as_of", "promoter_pct", "public_pct")
    list_filter = ("company",)