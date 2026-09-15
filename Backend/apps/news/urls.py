from django.urls import path
from .views import (
    CategorizationCorrectionListAPIView,
    NewsArticleDetailAPIView,
    NewsArticleListAPIView,
    NewsRecategorizeAPIView,
)

urlpatterns = [
    path(
        "",
        NewsArticleListAPIView.as_view(),
        name="news-list",
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
]