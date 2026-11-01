from django.urls import path

from apps.comparison.api.views import CompareAPIView, CompareCompaniesAPIView, CompareCoverageAPIView

urlpatterns = [
    path("", CompareAPIView.as_view(), name="compare"),
    path("companies/", CompareCompaniesAPIView.as_view(), name="compare-companies"),
    path("coverage/", CompareCoverageAPIView.as_view(), name="compare-coverage"),
]
