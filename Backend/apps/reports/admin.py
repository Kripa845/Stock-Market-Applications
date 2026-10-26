from django.contrib import admin

from apps.reports.models import CompanyEarnings, DividendAnnouncement, QuarterlyReport, YearlyDPPS


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
