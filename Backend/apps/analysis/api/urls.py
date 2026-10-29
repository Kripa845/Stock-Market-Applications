from django.urls import path
from apps.analysis.api.views import (
    AccDistAPIView,
    CompanyBehaviorSummaryAPIView,
    CompanyBrokerActivityAPIView,
    BrokerAnalysisAPIView,
    BrokerDetailAPIView,
    BrokerFlowAPIView,
    BrokerListAPIView,
    BrokerSignalAPIView,
    BrokerSummaryAPIView,
    TopBrokerAPIView,
    CompanyCategorizedNewsAPIView,
    CompanyNewsPriceCorrelationAPIView,
    CrossCompanyAnalysisAPIView,
    DailyAnalysisListAPIView,
    DashboardSummaryAPIView,
    FloorsheetGridAPIView,
)

urlpatterns = [
    path("brokers/", BrokerAnalysisAPIView.as_view(), name="broker-analysis"),
    # Before brokers/<broker_id>/ so "top" / "list" are not read as broker ids.
    path("brokers/top/", TopBrokerAPIView.as_view(), name="top-brokers"),
    path("brokers/list/", BrokerListAPIView.as_view(), name="broker-list"),
    path("brokers/<str:broker_id>/", BrokerDetailAPIView.as_view(), name="broker-detail"),
    # Accumulation / distribution for one stock (?symbol=&window= or start_date/end_date).
    path("broker-summary/", BrokerSummaryAPIView.as_view(), name="broker-summary"),
    path("broker-signal/", BrokerSignalAPIView.as_view(), name="broker-signal"),
    path("broker-flow/", BrokerFlowAPIView.as_view(), name="broker-flow"),
    # Market-wide (stock, broker) net buying / selling (?period=1D..3Y).
    path("acc-dist/", AccDistAPIView.as_view(), name="acc-dist"),
    # Floor Sheet Summary: one session's trades in N-minute buckets (?date=&minutes=).
    path("floorsheet-grid/", FloorsheetGridAPIView.as_view(), name="floorsheet-grid"),
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
