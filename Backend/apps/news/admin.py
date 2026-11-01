from django.contrib import admin
from .models import ArticleCompanyTag, NewsArticle, NewsSource


@admin.register(NewsSource)
class NewsSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "fetch_type", "is_active", "base_url")
    list_filter = ("fetch_type", "is_active")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(NewsArticle)
class NewsArticleAdmin(admin.ModelAdmin):

    list_display = (
        "headline",
        "news_source",
        "published_at",
        "url",
        "duplicate_of",
    )
    raw_id_fields = ("raw_article", "duplicate_of", "ingest_run")

    search_fields = (
        "headline",
        "body",
        "source",
    )

    list_filter = (
        "news_source",
        "published_at",
    )
admin.site.register(ArticleCompanyTag)
