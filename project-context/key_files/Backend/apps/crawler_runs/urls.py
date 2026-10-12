from django.urls import path

from .views import (
    CrawlRunCancelAPIView,
    CrawlRunDetailAPIView,
    CrawlRunListCreateAPIView,
    CrawlRunRetryAPIView,
)


urlpatterns = [
    path(
        "",
        CrawlRunListCreateAPIView.as_view(),
        name="crawl-run-list-create",
    ),

    path(
        "<int:pk>/",
        CrawlRunDetailAPIView.as_view(),
        name="crawl-run-detail",
    ),

    path(
        "<int:pk>/cancel/",
        CrawlRunCancelAPIView.as_view(),
        name="crawl-run-cancel",
    ),

    path(
        "<int:pk>/retry/",
        CrawlRunRetryAPIView.as_view(),
        name="crawl-run-retry",
    ),
]