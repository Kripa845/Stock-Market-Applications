from django.urls import path

from .views import CompanyPriceList,FloorsheetListAPIView


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