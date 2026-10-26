from django.urls import path

from apps.market_data.api.views import CompanyPriceList
from apps.floorsheet.api.views import FloorsheetListAPIView


urlpatterns = [
    path(
        "",
        CompanyPriceList.as_view(),
        name="price-list",
    ),
    path(
    "floorsheet/",
    FloorsheetListAPIView.as_view(),
    name="floorsheet-list",
),
]