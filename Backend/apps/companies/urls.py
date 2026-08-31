from django.contrib import admin
from django.urls import path

from apps.companies.views import CompanyListAPIView,CompanyDetailView


urlpatterns = [

   

    path(
        "api/companies/",
        CompanyListAPIView.as_view()
    ),
       path(
        "<int:pk>/",
        CompanyDetailView.as_view(),
        name="company-detail",
    ),
]