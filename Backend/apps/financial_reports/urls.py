from django.urls import path

from . import views

app_name = "financial_reports"

urlpatterns = [
    path("financial-reports/", views.financial_reports_page, name="financial_reports"),
    path("api/financial-reports/", views.financial_reports_api, name="financial_reports_api"),
    path("api/financial-reports/filters/", views.financial_reports_filters, name="financial_reports_filters"),
]
