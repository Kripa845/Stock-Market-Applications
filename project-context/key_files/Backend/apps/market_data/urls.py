from django.urls import path

from .views import CompanyPriceList,FloorsheetListAPIView, TrackedMoversListView, TrackedMoversView


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
  path("movers/tracked/", TrackedMoversView.as_view()),
path("movers/tracked/list/", TrackedMoversListView.as_view()),  
]