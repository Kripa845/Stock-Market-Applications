


from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.companies.models import Company
from apps.crawler_runs.models import CrawlRun
from apps.news.services.normalize import normalize_url


class NewsSource(models.Model):
    """A portal articles are collected from. Articles hold a PROTECT FK to it,
    so a source with articles can't be deleted (set is_active=False instead)."""

    class FetchType(models.TextChoices):
        RSS = "rss", "RSS"
        SCRAPE = "scrape", "Scrape"
        API = "api", "API"

    slug = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100, unique=True)
    base_url = models.URLField(max_length=300)
    logo_url = models.URLField(max_length=500, blank=True, default="")
    brand_color = models.CharField(max_length=7, blank=True, default="")
    fetch_type = models.CharField(max_length=10, choices=FetchType.choices, default=FetchType.SCRAPE)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class RawArticle(models.Model):
    # PROTECT: deleting a crawl run must not cascade into the articles it produced.
    crawl_run = models.ForeignKey(
        CrawlRun,
        on_delete=models.PROTECT,
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
    SOURCE_CHOICES = [("crawled", "Crawled"), ("seeded", "Seeded"), ("manual", "Manual"), ("unverified", "Unverified")]
    raw_article = models.OneToOneField(
        RawArticle,
        on_delete=models.CASCADE,
        related_name="article",
    )
    data_provenance = models.CharField(max_length=16, choices=SOURCE_CHOICES, default="unverified", db_index=True)
    news_source = models.ForeignKey(NewsSource, on_delete=models.PROTECT, related_name="articles")
    # news_source.name copied at ingest; kept because the API filters and serialises it.
    source = models.CharField(max_length=100)
    # The exact URL the article was taken from ...
    url = models.URLField(max_length=1000, unique=True)
    # ... and its identity form (services/ingest.py::normalize_url).
    normalized_url = models.CharField(max_length=1000)
    # The portal's own article id, when it exposes one; "" otherwise.
    external_id = models.CharField(max_length=200, blank=True, default="")
    # Run that first inserted the row (RawArticle.crawl_run is the latest fetch).
    ingest_run = models.ForeignKey(
        CrawlRun, on_delete=models.PROTECT, null=True, blank=True, related_name="ingested_articles",
    )
    headline = models.TextField()
    body = models.TextField()
    published_at = models.DateTimeField()
    # Lead image on the source site (og:image or the first article image).
    # Only the URL is stored; empty when the page had none.
    image_url = models.URLField(max_length=1000, blank=True, default="")
    # SHA-256 of normalised title + body: detects edits and exact copies.
    content_hash = models.CharField(max_length=64, db_index=True)
    # SHA-256 of the canonical title (services/ingest.py::canonical_title); "" for
    # titles too short to identify a story. Groups the same story across sources.
    canonical_hash = models.CharField(max_length=64, blank=True, default="", db_index=True)
    # Root article of the story group when another source published it first.
    # Always points at a root, never at another copy.
    duplicate_of = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="also_reported",
    )
    language = models.CharField(max_length=20, default="unknown")
    
    sentiment = models.FloatField(
        null=True,
        blank=True,
        help_text="Tone score in [-1.0, +1.0]. NULL when unavailable.",
    )
    sentiment_label = models.CharField(
        max_length=20,
        blank=True,
        help_text="positive (>= +0.05) / negative (<= -0.05) / neutral.",
    )
    sentiment_status = models.CharField(
        max_length=32,
        default="pending",
        db_index=True,
        choices=[
            ("pending", "Not yet processed"),
            ("ok", "Scored"),
            ("no_lexicon_match", "Scored, no tone-bearing vocabulary"),
            ("insufficient_content", "Article too short to score"),
            ("unsupported_language", "No lexicon for detected language"),
            ("error", "Analyser failed"),
        ],
        help_text=(
            "Lets the frontend distinguish 'sentiment unavailable' from "
            "'sentiment successfully calculated'. A NULL score alone cannot."
        ),
    )
    sentiment_method = models.CharField(
        max_length=40,
        blank=True,
        help_text="Analyser identifier, so a later model swap is auditable.",
    )
    sentiment_language = models.CharField(
        max_length=20,
        blank=True,
        help_text="Language detected at scoring time.",
    )
    sentiment_error = models.TextField(
        blank=True,
        help_text="Populated only when sentiment_status is 'error'.",
    )
    sentiment_processed_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    is_processed = models.BooleanField(default=False)
    # created_at is the first time the article was seen.
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_seen_at = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        if not self.normalized_url:
            self.normalized_url = normalize_url(self.url)
        super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["news_source", "normalized_url"],
                name="unique_article_source_normalized_url",
            ),
            models.UniqueConstraint(
                fields=["news_source", "external_id"],
                condition=~models.Q(external_id=""),
                name="unique_article_source_external_id",
            ),
            models.CheckConstraint(
                condition=~models.Q(url="") & ~models.Q(normalized_url=""),
                name="article_source_url_required",
            ),
        ]
        indexes = [
            models.Index(fields=["source", "published_at"]),
            models.Index(fields=["content_hash"]),
            models.Index(fields=["-published_at"], name="news_article_published_desc"),
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


class ArticleLike(models.Model):
    """One row per user per article; counts are derived from these rows."""
    article = models.ForeignKey(NewsArticle, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="article_likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["article", "user"], name="unique_article_like_per_user"),
        ]


class ArticleComment(models.Model):
    article = models.ForeignKey(NewsArticle, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="article_comments")
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["article", "created_at"], name="news_comment_article_created")]
