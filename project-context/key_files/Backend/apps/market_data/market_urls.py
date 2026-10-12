from django.urls import path

from .market_views import (
    BasketIndexAPIView,
    CompanyBrokerActivityAPIView,
    CompanyNewsAPIView,
    CompanySignalsAPIView,
    DividendListAPIView,
    PublicTrackedSnapshotAPIView,
    TrackedMoversAPIView,
    TrackedSummaryAPIView,
    TrackedTopAPIView,
    WatchlistAPIView,
)

# Mounted at /api/market/ -- tracked companies only (see market_views).
urlpatterns = [
    path("public/snapshot/", PublicTrackedSnapshotAPIView.as_view(), name="market-public-snapshot"),
    path("summary/", TrackedSummaryAPIView.as_view(), name="market-summary"),
    path("movers/", TrackedMoversAPIView.as_view(), name="market-movers"),
    path("top-turnover/", TrackedTopAPIView.as_view(metric="turnover"), name="market-top-turnover"),
    path("top-volume/", TrackedTopAPIView.as_view(metric="volume"), name="market-top-volume"),
    path("top-transactions/", TrackedTopAPIView.as_view(metric="transactions"), name="market-top-transactions"),
    path("brokers/<str:symbol>/", CompanyBrokerActivityAPIView.as_view(), name="market-company-brokers"),
    path("signals/<str:symbol>/", CompanySignalsAPIView.as_view(), name="market-company-signals"),
    path("basket-index/", BasketIndexAPIView.as_view(), name="market-basket-index"),
    path("dividends/", DividendListAPIView.as_view(), name="market-dividends"),
    path("watchlist/", WatchlistAPIView.as_view(), name="market-watchlist"),
    path("watchlist/<str:symbol>/", WatchlistAPIView.as_view(), name="market-watchlist-item"),
    path("news/<str:symbol>/", CompanyNewsAPIView.as_view(), name="market-company-news"),
]
