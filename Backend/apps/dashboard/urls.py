from django.urls import path

from .views import (
    AdminDashboardAPIView,
    AnalystDashboardAPIView,
    DashboardSummaryAPIView,
    ViewerDashboardAPIView,
)
from .export_views import (
    ExportCompanyListAPIView,
    ExportFloorsheetAPIView,
    ExportNewsAPIView,
    ExportReportAPIView,
    ExportTradingAPIView,
)


urlpatterns = [
    # ── Dashboard ───────────────────────────────────────────────────────
    path(
        "summary/",
        DashboardSummaryAPIView.as_view(),
        name="dashboard-summary",
    ),
    path(
        "admin/",
        AdminDashboardAPIView.as_view(),
        name="admin-dashboard",
    ),
    path(
        "analyst/",
        AnalystDashboardAPIView.as_view(),
        name="analyst-dashboard",
    ),
    path(
        "viewer/",
        ViewerDashboardAPIView.as_view(),
        name="viewer-dashboard",
    ),

    # ── Export endpoints ────────────────────────────────────────────────
    #
    # All routes below are reachable under BOTH prefixes registered in
    # config/urls.py:
    #   /api/dashboard/export/...
    #   /api/reports/export/...
    #
    # Permission: export_reports (existing dynamic permission key).
    # Every view validates company_id server-side before touching data.

    # Company list — populates the frontend company dropdown
    path(
        "export/companies/",
        ExportCompanyListAPIView.as_view(),
        name="export-companies",
    ),

    # News export  (CSV | XLSX | PDF)
    path(
        "export/news/",
        ExportNewsAPIView.as_view(),
        name="export-news",
    ),

    # Trading (daily price) export  (CSV | XLSX | PDF)
    path(
        "export/trading/",
        ExportTradingAPIView.as_view(),
        name="export-trading",
    ),

    # Floorsheet export  (CSV | XLSX)
    path(
        "export/floorsheet/",
        ExportFloorsheetAPIView.as_view(),
        name="export-floorsheet",
    ),

    # Combined analysis report  (PDF | XLSX)
    path(
        "export/report/",
        ExportReportAPIView.as_view(),
        name="export-report",
    ),
]
