from django.urls import path
from .views import (
    CompanyBehaviorSummaryAPIView,
    CompanyBrokerActivityAPIView,
    BrokerAnalysisAPIView,
    BrokerDetailAPIView,
    TopBrokerAPIView,
    CompanyCategorizedNewsAPIView,
    CompanyNewsPriceCorrelationAPIView,
    CrossCompanyAnalysisAPIView,
    DailyAnalysisListAPIView,
    DashboardSummaryAPIView,
)

urlpatterns = [
    path("brokers/", BrokerAnalysisAPIView.as_view(), name="broker-analysis"),
    # Before brokers/<broker_id>/ so "top" is not read as a broker id.
    path("brokers/top/", TopBrokerAPIView.as_view(), name="top-brokers"),
    path("brokers/<str:broker_id>/", BrokerDetailAPIView.as_view(), name="broker-detail"),
    path("companies/<int:pk>/categorized-news/", CompanyCategorizedNewsAPIView.as_view(), name="company-categorized-news"),
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
        "companies/<int:pk>/brokers/",
        CompanyBrokerActivityAPIView.as_view(),
        name="company-broker-activity",
    ),
    path(
        "companies/<int:pk>/news-pricecorrelation/",
        CompanyNewsPriceCorrelationAPIView.as_view(),
        name="company-news-price-correlation",
    ),
]
