from django.urls import path

from apps.reports.api.views import DividendListAPIView, QuarterlyReportAPIView, QuarterlyReportPeriodsAPIView

# Mounted at /api/market/ next to market_data's routes (the frontend's URLs predate this app).
urlpatterns = [
    path("dividends/", DividendListAPIView.as_view(), name="market-dividends"),
    path("quarterly-report/", QuarterlyReportAPIView.as_view(), name="market-quarterly-report"),
    path("quarterly-report/periods/", QuarterlyReportPeriodsAPIView.as_view(), name="market-quarterly-report-periods"),
]
