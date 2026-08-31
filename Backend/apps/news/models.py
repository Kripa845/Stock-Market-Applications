from django.db import models
from django.conf import settings
from apps.companies.models import Company
from apps.crawler_runs.models import CrawlRun
# Create your models here.

class RawArticle(models.Model):
    crawl_run = models.ForeignKey(
        CrawlRun,
        on_delete=models.CASCADE,
        related_name="raw_articles",
    )
    source = models.CharField(max_length=100)
    url = models.URLField(max_length=1000)
    fetched_at = models.DateTimeField(auto_now_add=True)
    http_status = models.PositiveIntegerField(null=True, blank=True)
    raw_html = models.TextField(blank=True)
    extraction_error = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source", "url"],
                name="unique_raw_source_url",
            )
        ]


class NewsArticle(models.Model):
    raw_article = models.OneToOneField(
        RawArticle,
        on_delete=models.CASCADE,
        related_name="article",
    )
    source = models.CharField(max_length=100)
    url = models.URLField(max_length=1000, unique=True)
    headline = models.TextField()
    body = models.TextField()
    published_at = models.DateTimeField(null=True, blank=True)
    content_hash = models.CharField(max_length=64, db_index=True)
    language = models.CharField(max_length=20, default="unknown")
    sentiment = models.FloatField(null=True, blank=True)
    sentiment_label = models.CharField(max_length=20, blank=True)
    is_processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["source", "published_at"]),
            models.Index(fields=["content_hash"]),
        ]


class ArticleCompanyTag(models.Model):
    article = models.ForeignKey(
        NewsArticle,
        on_delete=models.CASCADE,
        related_name="company_tags",
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="article_tags",
    )
    confidence = models.FloatField()
    method = models.CharField(max_length=50)
    evidence = models.JSONField(default=dict)
    is_manual = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["article", "company"],
                name="unique_article_company_tag",
            )
        ]

    def __str__(self):
        return (
            f"{self.company.symbol} "
            f"({self.confidence:.2f})"
        )
class CategorizationCorrection(models.Model):
    article = models.ForeignKey(
        NewsArticle,
        on_delete=models.CASCADE,
        related_name="corrections",
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="categorization_corrections",
    )
    previous_confidence = models.FloatField(null=True, blank=True)
    previous_method = models.CharField(max_length=50, blank=True)
    action = models.CharField(
        max_length=20,
        choices=[
            ("add", "Add"),
            ("remove", "Remove"),
            ("update", "Update"),
        ],
    )
    reason = models.TextField(blank=True)
    corrected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    corrected_at = models.DateTimeField(auto_now_add=True)


 
