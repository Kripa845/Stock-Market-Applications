"""
Single write path for news articles: normalise, hash, upsert, link stories.

Identity of an article is (news_source, external_id) when the source has its
own id, else (news_source, normalized_url); both are unique in the DB, so a
re-run of any collector can never create a second row. The same story on
another portal is kept (attribution matters) and linked through duplicate_of.
See apps/news/README.md "Adding a news source".
"""
import logging
import re
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.news.models import NewsArticle, NewsSource, RawArticle
from apps.news.selectors import SEEDED
from apps.news.services.normalize import (
    compute_canonical_hash,
    compute_content_hash,
    normalize_text,
    normalize_url,
)

logger = logging.getLogger(__name__)

# Same normalised title only counts as the same story if published this close
# together; recurring headlines ("Share market update") would otherwise chain
# months of unrelated articles.
STORY_WINDOW = timedelta(days=3)


class IngestRejected(ValueError):
    """The item lacks something an article must have (source, URL, title, date, body)."""


@dataclass
class IngestResult:
    status: str  # "inserted" | "updated" | "duplicate"
    article_id: int
    duplicate_of_id: Optional[int] = None


def _source_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def resolve_source(label: str) -> Optional[NewsSource]:
    """NewsSource for a spider's source label, ignoring case, spaces and
    hyphens ("FiscalNepal", "Fiscal Nepal" and "fiscal-nepal" are one source)."""
    key = _source_key(label)
    if not key:
        return None
    for source in NewsSource.objects.all():
        if key in {_source_key(source.slug), _source_key(source.name)}:
            return source
    return None


def find_story_root(*, exclude_source_id, exclude_article_id=None, content_hash, canonical_hash, published_at):
    """Earliest article from another source carrying the same story, as the
    group's root (never a chain: a match that is itself a copy yields its root)."""
    match = Q(content_hash=content_hash)
    if canonical_hash:
        match |= Q(
            canonical_hash=canonical_hash,
            published_at__gte=published_at - STORY_WINDOW,
            published_at__lte=published_at + STORY_WINDOW,
        )
    candidate = (
        NewsArticle.objects.filter(match)
        .exclude(data_provenance=SEEDED)
        .exclude(news_source_id=exclude_source_id)
        .exclude(pk=exclude_article_id)
        .order_by("published_at", "id")
        .only("id", "duplicate_of_id")
        .first()
    )
    if candidate is None:
        return None
    return candidate.duplicate_of_id or candidate.id


def _require(raw_item, *keys):
    for key in keys:
        value = raw_item.get(key)
        if value:
            return value
    return None


def ingest_article(source_id, raw_item, *, ingest_run_id, provenance="crawled") -> IngestResult:
    """Normalise, hash and upsert one article.

    raw_item keys: url, headline (or title), body (or content), published_at
    (aware datetime), and optionally external_id, image_url, raw_html, http_status.

    inserted:  new row (duplicate_of_id set when another source has the story)
    updated:   existing row whose title/body/image changed
    duplicate: existing row seen again unchanged, or an exact copy of another
               article from the same source under a different URL
    """
    url = (raw_item.get("url") or "").strip()
    headline = normalize_text(_require(raw_item, "headline", "title") or "")
    body = (_require(raw_item, "body", "content") or "").strip()
    published_at = raw_item.get("published_at")
    external_id = str(raw_item.get("external_id") or "").strip()
    image_url = (raw_item.get("image_url") or "").strip()

    if not source_id:
        raise IngestRejected("source_id is required")
    if not ingest_run_id:
        raise IngestRejected("ingest_run_id is required: every article records the run that created it")
    normalized = normalize_url(url)
    if not normalized:
        raise IngestRejected(f"source URL missing or not absolute: {url!r}")
    if not headline:
        raise IngestRejected(f"title missing: {url}")
    if not body:
        raise IngestRejected(f"body missing: {url}")
    if published_at is None or timezone.is_naive(published_at):
        raise IngestRejected(f"published_at missing or naive: {url}")

    content_hash = compute_content_hash(headline, body)
    canonical_hash = compute_canonical_hash(headline)
    now = timezone.now()

    with transaction.atomic():
        source = NewsSource.objects.filter(pk=source_id).first()
        if source is None:
            raise IngestRejected(f"unknown source_id {source_id}")

        existing = _find_existing(source.pk, external_id, normalized)
        if existing is not None:
            return _refresh(existing, raw_item, headline, body, image_url, external_id,
                            content_hash, canonical_hash, now)

        # Exact copy re-posted by the same portal under another URL.
        same_source_copy = (
            NewsArticle.objects.select_for_update()
            .filter(news_source=source, content_hash=content_hash)
            .first()
        )
        if same_source_copy is not None:
            same_source_copy.last_seen_at = now
            same_source_copy.save(update_fields=["last_seen_at"])
            return IngestResult("duplicate", same_source_copy.pk, same_source_copy.duplicate_of_id)

        root_id = find_story_root(
            exclude_source_id=source.pk,
            content_hash=content_hash,
            canonical_hash=canonical_hash,
            published_at=published_at,
        )
        try:
            with transaction.atomic():
                raw, _ = RawArticle.objects.update_or_create(
                    source=source.name,
                    url=url,
                    defaults={
                        "crawl_run_id": ingest_run_id,
                        "http_status": raw_item.get("http_status") or 200,
                        "raw_html": raw_item.get("raw_html") or "",
                    },
                )
                article = NewsArticle.objects.create(
                    raw_article=raw,
                    news_source=source,
                    source=source.name,
                    url=url,
                    normalized_url=normalized,
                    external_id=external_id,
                    headline=headline,
                    body=body,
                    published_at=published_at,
                    image_url=image_url,
                    content_hash=content_hash,
                    canonical_hash=canonical_hash,
                    duplicate_of_id=root_id,
                    ingest_run_id=ingest_run_id,
                    last_seen_at=now,
                    data_provenance=provenance,
                )
        except IntegrityError:
            # A concurrent run inserted the same article between lookup and insert.
            existing = _find_existing(source.pk, external_id, normalized)
            if existing is None:
                raise
            return _refresh(existing, raw_item, headline, body, image_url, external_id,
                            content_hash, canonical_hash, now)

    return IngestResult("inserted", article.pk, root_id)


def _find_existing(source_id, external_id, normalized_url):
    qs = NewsArticle.objects.select_for_update().filter(news_source_id=source_id)
    if external_id:
        found = qs.filter(external_id=external_id).first()
        if found is not None:
            return found
    return qs.filter(normalized_url=normalized_url).first()


def _refresh(article, raw_item, headline, body, image_url, external_id,
             content_hash, canonical_hash, now) -> IngestResult:
    """Touch last_seen_at; rewrite only fields the source actually changed."""
    fields = ["last_seen_at"]
    article.last_seen_at = now
    changed = False

    if article.content_hash != content_hash:
        article.headline = headline
        article.body = body
        article.content_hash = content_hash
        article.canonical_hash = canonical_hash
        fields += ["headline", "body", "content_hash", "canonical_hash"]
        changed = True
    if image_url and image_url != article.image_url:
        article.image_url = image_url
        fields.append("image_url")
        changed = True
    if external_id and not article.external_id:
        article.external_id = external_id
        fields.append("external_id")

    if changed:
        fields.append("updated_at")
        raw = article.raw_article
        raw.raw_html = raw_item.get("raw_html") or raw.raw_html
        raw.http_status = raw_item.get("http_status") or raw.http_status
        raw.save(update_fields=["raw_html", "http_status"])
    article.save(update_fields=fields)

    return IngestResult("updated" if changed else "duplicate", article.pk, article.duplicate_of_id)
