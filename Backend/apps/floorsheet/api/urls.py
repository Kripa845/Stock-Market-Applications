from django.urls import path

from apps.floorsheet.api.views import FloorsheetListAPIView, FloorsheetSummaryAPIView

# Mounted at /api/floorsheet/
urlpatterns = [
    path("summary/", FloorsheetSummaryAPIView.as_view(), name="floorsheet-summary"),
    path("", FloorsheetListAPIView.as_view(), name="floorsheet-api"),
]
