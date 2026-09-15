from django.urls import path

from .views import (
    AdminDashboardAPIView,
    AnalystDashboardAPIView,
    DashboardSummaryAPIView,
    ViewerDashboardAPIView,
)

urlpatterns = [
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
]