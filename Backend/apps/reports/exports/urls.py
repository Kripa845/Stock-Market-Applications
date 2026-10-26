from django.urls import path

from apps.reports.exports.companies import ExportCompanyListAPIView
from apps.reports.exports.floorsheet import ExportBrokerActivityAPIView, ExportFloorsheetAPIView
from apps.reports.exports.news import ExportNewsAPIView
from apps.reports.exports.report import ExportReportAPIView
from apps.reports.exports.trading import ExportTradingAPIView

# Reachable under BOTH prefixes registered in config/urls.py:
#   /api/dashboard/export/...
#   /api/reports/export/...
#
# Permission: export_reports (existing dynamic permission key).
# Every view validates company_id server-side before touching data.
urlpatterns = [
    # Company list -- populates the frontend company dropdown
    path("export/companies/", ExportCompanyListAPIView.as_view(), name="export-companies"),
    # News export  (CSV | XLSX | PDF)
    path("export/news/", ExportNewsAPIView.as_view(), name="export-news"),
    # Trading (daily price) export  (CSV | XLSX | PDF)
    path("export/trading/", ExportTradingAPIView.as_view(), name="export-trading"),
    # Floorsheet export  (CSV | XLSX)
    path("export/brokers/", ExportBrokerActivityAPIView.as_view(), name="export-broker-activity"),
    path("export/floorsheet/", ExportFloorsheetAPIView.as_view(), name="export-floorsheet"),
    # Combined analysis report  (PDF | XLSX)
    path("export/report/", ExportReportAPIView.as_view(), name="export-report"),
]
