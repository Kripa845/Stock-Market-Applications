from django.urls import path

from apps.market_indices.api.views import (
    IndexHistoryAPIView,
    IndexIntradayAPIView,
    IndexSupportResistanceAPIView,
    IndexVerificationAPIView,
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
    path("history/", IndexHistoryAPIView.as_view(), name="market-index-history"),
    path("verify/", IndexVerificationAPIView.as_view(), name="market-index-verify"),
    path("intraday/", IndexIntradayAPIView.as_view(), name="market-index-intraday"),
    path("support-resistance/", IndexSupportResistanceAPIView.as_view(), name="market-index-support-resistance"),
]
