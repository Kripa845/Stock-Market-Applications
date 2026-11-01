"""
Create the known portals and point every existing article at one.

- Source labels are matched ignoring case/spaces ("FiscalNepal" -> Fiscal Nepal);
  an unknown label gets its own inactive source so no article is left without one.
- normalized_url / canonical_hash are computed; content_hash is recomputed with
  the new normalisation, except seeded rows whose "hash_..." value is their
  marker (0008).
- ingest_run = the raw article's crawl run: the old pipeline returned early for
  known URLs, so that run is the one that inserted the row.
Cross-source story links are not made here; run `manage.py dedupe_news --apply`.
"""
import re

from django.db import migrations
from django.utils.text import slugify

from apps.news.services.normalize import (
    compute_canonical_hash,
    compute_content_hash,
    normalize_url,
)

SOURCES = [
    # slug, name, base_url, logo_url, brand_color
    ("share-sansar", "ShareSansar", "https://www.sharesansar.com", "https://www.sharesansar.com/favicon.ico", "#1d4ed8"),
    ("mero-lagani", "MeroLagani", "https://merolagani.com", "https://merolagani.com/favicon.ico", "#dc2626"),
    ("fiscal-nepal", "Fiscal Nepal", "https://www.fiscalnepal.com", "https://www.fiscalnepal.com/favicon.ico", "#0ea5e9"),
    ("bizmandu", "Bizmandu", "https://www.bizmandu.com", "https://www.bizmandu.com/favicon.ico", "#f59e0b"),
    ("arthakhabar", "Arthakhabar", "https://www.arthakhabar.com", "https://www.arthakhabar.com/favicon.ico", "#16a34a"),
    ("nepse-alpha", "NepseAlpha", "https://www.nepsealpha.com", "https://www.nepsealpha.com/favicon.ico", "#8b5cf6"),
]
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _key(value):
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def backfill(apps, schema_editor):
    NewsSource = apps.get_model("news", "NewsSource")
    NewsArticle = apps.get_model("news", "NewsArticle")
    RawArticle = apps.get_model("news", "RawArticle")

    by_key = {}
    for slug, name, base_url, logo_url, color in SOURCES:
        source, _ = NewsSource.objects.get_or_create(
            slug=slug,
            defaults={"name": name, "base_url": base_url, "logo_url": logo_url, "brand_color": color},
        )
        by_key[_key(slug)] = by_key[_key(name)] = source

    def source_for(label):
        key = _key(label) or "unknown"
        if key not in by_key:
            name = (label or "").strip() or "Unknown"
            by_key[key] = NewsSource.objects.create(
                slug=slugify(name)[:50] or "unknown", name=name, base_url="https://invalid.local", is_active=False,
            )
        return by_key[key]

    batch = []
    for article in NewsArticle.objects.select_related("raw_article").iterator(chunk_size=500):
        source = source_for(article.source)
        article.news_source = source
        article.source = source.name
        article.normalized_url = normalize_url(article.url) or article.url
        article.canonical_hash = compute_canonical_hash(article.headline)
        if SHA256.match(article.content_hash or ""):
            article.content_hash = compute_content_hash(article.headline, article.body)
        article.ingest_run_id = article.raw_article.crawl_run_id
        article.last_seen_at = article.updated_at
        batch.append(article)
        if len(batch) >= 500:
            _flush(NewsArticle, batch)
    _flush(NewsArticle, batch)

    for label in RawArticle.objects.values_list("source", flat=True).distinct():
        name = source_for(label).name
        if name != label:
            RawArticle.objects.filter(source=label).update(source=name)


def _flush(NewsArticle, batch):
    NewsArticle.objects.bulk_update(
        batch,
        ["news_source", "source", "normalized_url", "canonical_hash", "content_hash", "ingest_run", "last_seen_at"],
    )
    batch.clear()


class Migration(migrations.Migration):

    dependencies = [
        ("news", "0009_news_sources_and_dedup_fields"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
