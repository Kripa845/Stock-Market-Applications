from django.contrib import admin
from django.urls import include, path
from apps.users.views import AdminUserDetailAPIView, AdminUserListCreateAPIView
from apps.market_data.views import FloorsheetListAPIView

urlpatterns = [
    path("admin/", admin.site.urls),

    # Companies & Market Data
    path("api/companies/", include("apps.companies.urls")),
    path("api/market-data/", include("apps.market_data.urls")),
    path("api/floorsheet/", FloorsheetListAPIView.as_view(), name="floorsheet-api"),

    # News & Categorization
    path("api/news/", include("apps.news.urls")),

    # Behavior Analysis
    path("api/analysis/", include("apps.analysis.urls")),

    # Auth & Users
    path("api/users/", include("apps.users.urls")),

    # Admin Management (role-gated: Admin)
    path("api/crawler-runs/", include("apps.crawler_runs.urls")),
    path("api/admin/crawl-runs/", include("apps.crawler_runs.urls")),
    path("api/admin/users/", AdminUserListCreateAPIView.as_view(), name="admin-users-api"),
    path("api/admin/users/<int:pk>/", AdminUserDetailAPIView.as_view(), name="admin-user-detail-api"),

    # Dashboard & Reports / Export (role-gated: Analyst & Admin)
    path("api/dashboard/", include("apps.dashboard.urls")),
    path("api/reports/", include("apps.dashboard.urls")),
]
