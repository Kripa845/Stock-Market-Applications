from django.urls import path
from .views import (
    CompanyBehaviorSummaryAPIView,
    CompanyNewsPriceCorrelationAPIView,
    CrossCompanyAnalysisAPIView,
    DailyAnalysisListAPIView,
    DashboardSummaryAPIView,
)

urlpatterns = [
    path(
        "daily/",
        DailyAnalysisListAPIView.as_view(),
        name="daily-analysis-list",
    ),
    path(
        "cross-company/",
        CrossCompanyAnalysisAPIView.as_view(),
        name="cross-company-analysis",
    ),
    path(
        "dashboard-summary/",
        DashboardSummaryAPIView.as_view(),
        name="dashboard-summary",
    ),
    path(
        "companies/<int:pk>/behaviorsummary/",
        CompanyBehaviorSummaryAPIView.as_view(),
        name="company-behavior-summary",
    ),
    path(
        "companies/<int:pk>/news-pricecorrelation/",
        CompanyNewsPriceCorrelationAPIView.as_view(),
        name="company-news-price-correlation",
    ),
]