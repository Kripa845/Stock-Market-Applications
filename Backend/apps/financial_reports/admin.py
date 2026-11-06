from django.contrib import admin

from .models import FinancialReport


@admin.register(FinancialReport)
class FinancialReportAdmin(admin.ModelAdmin):
    list_display = ("symbol", "fiscal_year_bs", "duration", "report_date_bs", "title")
    list_filter = ("duration", "fiscal_year_bs")
    search_fields = ("symbol", "company_name", "title")
