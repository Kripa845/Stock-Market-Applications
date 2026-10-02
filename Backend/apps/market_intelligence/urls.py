from django.urls import path

from apps.market_intelligence.views import (
    CompanyIndicatorSeriesAPIView,
    CompanyTechnicalsAPIView,
    IndicatorRegistryAPIView,
    MarketBreadthAPIView,
    MarketHeatmapAPIView,
    MarketRankingsAPIView,
    RelativeStrengthAPIView,
    SectorRotationAPIView,
)

urlpatterns = [
    path("breadth/", MarketBreadthAPIView.as_view(), name="market-intelligence-breadth"),
    path("heatmap/", MarketHeatmapAPIView.as_view(), name="market-intelligence-heatmap"),
    path("rankings/", MarketRankingsAPIView.as_view(), name="market-intelligence-rankings"),
    path("sectors/rotation/", SectorRotationAPIView.as_view(), name="market-intelligence-sector-rotation"),
    path("relative-strength/", RelativeStrengthAPIView.as_view(), name="market-intelligence-relative-strength"),
    path("companies/<int:company_id>/technicals/", CompanyTechnicalsAPIView.as_view(), name="company-technicals"),
    path("indicators/registry/", IndicatorRegistryAPIView.as_view(), name="indicator-registry"),
    path("companies/<int:company_id>/indicators/", CompanyIndicatorSeriesAPIView.as_view(), name="company-indicators"),
]
