from django.urls import path

from apps.floorsheet.api.views import StockIntradayCandlesAPIView


urlpatterns = [
    path(
        "<str:symbol>/intraday/",
        StockIntradayCandlesAPIView.as_view(),
        name="stock-intraday-candles",
    ),
]
