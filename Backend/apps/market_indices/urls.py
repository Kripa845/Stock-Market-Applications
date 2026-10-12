from django.urls import path

from .views import (
    IndicesAPIView,
    MarketAnalysisAPIView,
    MarketTopAPIView,
    SubIndicesAPIView,
    TrackedSectorsAPIView,
)

# Mounted at /api/market-indices/
urlpatterns = [
    path("indices/", IndicesAPIView.as_view(), name="market-indices"),
    path("sub-indices/", SubIndicesAPIView.as_view(), name="market-sub-indices"),
    path("analysis/", MarketAnalysisAPIView.as_view(), name="market-indices-analysis"),
    path("top/", MarketTopAPIView.as_view(), name="market-indices-top"),
    path("tracked-sectors/", TrackedSectorsAPIView.as_view(), name="market-tracked-sectors"),
]
