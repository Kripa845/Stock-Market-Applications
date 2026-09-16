from django.urls import path
from .views import (
    CategorizationCorrectionListAPIView,
    NewsArticleDetailAPIView,
    NewsArticleListAPIView,
    NewsRecategorizeAPIView,
    NewsStatsAPIView,
    NewsTriggerCategorizeAPIView,
)

urlpatterns = [
    path(
        "",
        NewsArticleListAPIView.as_view(),
        name="news-list",
    ),
    path(
        "stats/",
        NewsStatsAPIView.as_view(),
        name="news-stats",
    ),
    path(
        "corrections/",
        CategorizationCorrectionListAPIView.as_view(),
        name="news-corrections",
    ),
    path(
        "<int:pk>/",
        NewsArticleDetailAPIView.as_view(),
        name="news-detail",
    ),
    path(
        "<int:pk>/recategorize/",
        NewsRecategorizeAPIView.as_view(),
        name="news-recategorize",
    ),
    path(
        "<int:pk>/trigger-categorize/",
        NewsTriggerCategorizeAPIView.as_view(),
        name="news-trigger-categorize",
    ),
]