from django.contrib import admin
from .models import  NewsArticle,ArticleCompanyTag


@admin.register(NewsArticle)
class NewsArticleAdmin(admin.ModelAdmin):

    list_display = (
        "headline",
        "source",
        "published_at",
        "url",
    )

    search_fields = (
        "headline",
        "body",
        "source",
    )

    list_filter = (
        "source",
        "published_at",
    )
admin.site.register(ArticleCompanyTag)
