from django.urls import path
from apps.analysis.views import (
    CompanyBehaviorSummaryAPIView,
    CompanyNewsPriceCorrelationAPIView,
)
from .views import (
    CompanyDetailUpdateDestroyAPIView,
    CompanyFloorsheetAPIView,
    CompanyListCreateAPIView,
    CompanyPricesAPIView,
    CompanyToggleTrackAPIView,
)

urlpatterns = [
    path(
        "",
        CompanyListCreateAPIView.as_view(),
        name="company-list-create",
    ),
    path(
        "<int:pk>/",
        CompanyDetailUpdateDestroyAPIView.as_view(),
        name="company-detail",
    ),
    path(
        "<int:pk>/toggle-track/",
        CompanyToggleTrackAPIView.as_view(),
        name="company-toggle-track",
    ),
    path(
        "<int:pk>/prices/",
        CompanyPricesAPIView.as_view(),
        name="company-prices",
    ),
    path(
        "<int:pk>/floorsheet/",
        CompanyFloorsheetAPIView.as_view(),
        name="company-floorsheet",
    ),
    path(
    "<int:pk>/behavior/",
    CompanyBehaviorSummaryAPIView.as_view(),
    name="company-behavior-summary",
),

    path(
        "<int:pk>/behavior-summary/",
        CompanyBehaviorSummaryAPIView.as_view(),
        name="company-behavior-summary-spec",
    ),

path(
    "<int:pk>/news-correlation/",
    CompanyNewsPriceCorrelationAPIView.as_view(),
    name="company-news-correlation",
),

path(
    "<int:pk>/news-price-correlation/",
    CompanyNewsPriceCorrelationAPIView.as_view(),
    name="company-news-price-correlation-spec",
),
]