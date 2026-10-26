from django.contrib import admin
from django.urls import include, path
from apps.users.api.views import AdminUserDetailAPIView, AdminUserListCreateAPIView

urlpatterns = [
    path("admin/", admin.site.urls),

    # Companies & Market Data
    path("api/companies/", include("apps.companies.api.urls")),
    path("api/market-data/", include("apps.market_data.api.urls")),
    path("api/market/", include("apps.market_data.api.market_urls")),
    path("api/market/", include("apps.reports.api.urls")),          # dividends, quarterly report
    path("api/floorsheet/", include("apps.floorsheet.api.urls")),
    path("api/stocks/", include("apps.floorsheet.api.stock_urls")),

    # News & Categorization
    path("api/news/", include("apps.news.api.urls")),

    # Behavior Analysis
    path("api/analysis/", include("apps.analysis.api.urls")),
    path("api/market-intelligence/", include("apps.market_intelligence.api.urls")),
    path("api/market-indices/", include("apps.market_indices.api.urls")),

    # Auth & Users
    path("api/users/", include("apps.users.api.urls")),

    # Admin Management (role-gated: Admin)
    path("api/crawler-runs/", include("apps.crawler_runs.api.urls")),
    path("api/admin/crawl-runs/", include("apps.crawler_runs.api.urls")),
    path("api/admin/users/", AdminUserListCreateAPIView.as_view(), name="admin-users-api"),
    path("api/admin/users/<int:pk>/", AdminUserDetailAPIView.as_view(), name="admin-user-detail-api"),

    # Dashboard & Reports / Export (role-gated: Analyst & Admin).
    # Both prefixes serve both URL sets; the frontend uses /api/dashboard/ and /api/reports/export/.
    path("api/dashboard/", include("apps.dashboard.api.urls")),
    path("api/dashboard/", include("apps.reports.exports.urls")),
    path("api/reports/", include("apps.dashboard.api.urls")),
    path("api/reports/", include("apps.reports.exports.urls")),
]
