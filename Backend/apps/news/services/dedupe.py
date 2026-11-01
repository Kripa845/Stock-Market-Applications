"""
Find and resolve duplicate articles already in the DB (manage.py dedupe_news).

Same source, same story -> merged into one row:
  - same normalized URL (the collector re-saved one page under URL variants)
  - same content_hash (the portal re-posted identical text under a new URL)
Different sources, same story -> linked, never merged (attribution is kept):
  - same content_hash, or same canonical_hash within ingest.STORY_WINDOW

Same-source articles that only share a title are left alone: portals reuse
headlines like "सुनचाँदीको मूल्य बढ्यो" for different days' news.
"""
import logging
from dataclasses import dataclass, field

from django.db import transaction
from django.db.models import Count

from apps.news.models import ArticleCompanyTag, ArticleLike, NewsArticle
from apps.news.selectors import SEEDED
from apps.news.services.ingest import find_story_root

logger = logging.getLogger(__name__)

# Which row survives a merge: real data first, then the first one seen.
PROVENANCE_RANK = {"crawled": 0, "manual": 1, "unverified": 2, SEEDED: 3}


@dataclass
class DedupeReport:
    url_groups: list = field(default_factory=list)       # [[survivor_id, loser_id, ...], ...]
    content_groups: list = field(default_factory=list)
    links: list = field(default_factory=list)            # [(article_id, root_id), ...]
    same_source_title_groups: int = 0


def _groups(field_name):
    """Same-source groups of ids sharing `field_name`, survivor first."""
    keys = (
        NewsArticle.objects.exclude(**{field_name: ""})
        .values("news_source", field_name)
        .annotate(n=Count("id"))
        .filter(n__gt=1)
    )
    groups = []
    for key in keys:
        key.pop("n")
        members = sorted(
            NewsArticle.objects.filter(**key).only("id", "data_provenance"),
            key=lambda a: (PROVENANCE_RANK.get(a.data_provenance, 9), a.id),
        )
        groups.append([a.id for a in members])
    return groups


def find_duplicates() -> DedupeReport:
    report = DedupeReport()
    report.url_groups = _groups("normalized_url")
    report.content_groups = _groups("content_hash")
    report.same_source_title_groups = (
        NewsArticle.objects.exclude(canonical_hash="")
        .values("news_source", "canonical_hash")
        .annotate(n=Count("id"))
        .filter(n__gt=1)
        .count()
    )
    return report


def merge_into(survivor: NewsArticle, loser: NewsArticle):
    """Move everything that hangs off `loser` onto `survivor`, then delete it."""
    for tag in ArticleCompanyTag.objects.filter(article=loser):
        kept = ArticleCompanyTag.objects.filter(article=survivor, company_id=tag.company_id).first()
        if kept is None:
            tag.article = survivor
            tag.save(update_fields=["article"])
        elif tag.is_manual and not kept.is_manual:
            # A human decision outranks an automatic one.
            kept.delete()
            tag.article = survivor
            tag.save(update_fields=["article"])
        else:
            tag.delete()

    loser.corrections.update(article=survivor)
    loser.comments.update(article=survivor)
    liked = set(ArticleLike.objects.filter(article=survivor).values_list("user_id", flat=True))
    loser.likes.exclude(user_id__in=liked).update(article=survivor)
    fields = ["last_seen_at"]
    if survivor.duplicate_of_id == loser.pk:
        # Pointing at the row being deleted would SET_NULL and orphan the group.
        survivor.duplicate_of_id = None if loser.duplicate_of_id == survivor.pk else loser.duplicate_of_id
        fields.append("duplicate_of")
    loser.also_reported.exclude(pk=survivor.pk).update(duplicate_of=survivor.duplicate_of_id or survivor.pk)

    survivor.last_seen_at = max(survivor.last_seen_at, loser.last_seen_at)
    if not survivor.image_url and loser.image_url:
        survivor.image_url = loser.image_url
        fields.append("image_url")
    if not survivor.external_id and loser.external_id:
        survivor.external_id = loser.external_id
        fields.append("external_id")
    if survivor.duplicate_of_id is None and loser.duplicate_of_id not in (None, survivor.pk):
        survivor.duplicate_of_id = loser.duplicate_of_id
        if "duplicate_of" not in fields:
            fields.append("duplicate_of")
    survivor.save(update_fields=fields)

    logger.info("Merged article %s into %s (%s)", loser.pk, survivor.pk, loser.url)
    # Deleting the raw row cascades to the article (one-to-one).
    loser.raw_article.delete()


def _merge_groups(groups):
    merged = 0
    for ids in groups:
        with transaction.atomic():
            rows = {a.pk: a for a in NewsArticle.objects.select_for_update().filter(pk__in=ids)}
            survivor = rows.get(ids[0])
            if survivor is None:
                continue
            for loser_id in ids[1:]:
                if loser_id in rows:
                    merge_into(survivor, rows[loser_id])
                    merged += 1
    return merged


def plan_story_links():
    """(article_id, root_id) for cross-source copies not linked yet.
    Processed oldest first, so each story's earliest article becomes the root."""
    links = []
    linked = {}
    qs = (
        NewsArticle.objects.exclude(data_provenance=SEEDED)
        # Roots stay roots, so links never form chains.
        .filter(duplicate_of__isnull=True, also_reported__isnull=True)
        .order_by("published_at", "id")
        .only("id", "news_source_id", "content_hash", "canonical_hash", "published_at")
    )
    for article in qs.iterator(chunk_size=500):
        root_id = find_story_root(
            exclude_source_id=article.news_source_id,
            exclude_article_id=article.pk,
            content_hash=article.content_hash,
            canonical_hash=article.canonical_hash,
            published_at=article.published_at,
        )
        if root_id is None:
            continue
        root_id = linked.get(root_id, root_id)
        root = NewsArticle.objects.only("published_at", "id").get(pk=root_id)
        # Only link to an earlier article; a later one will link to this one instead.
        if (root.published_at, root.pk) < (article.published_at, article.pk):
            links.append((article.pk, root_id))
            linked[article.pk] = root_id
    return links


def run(apply: bool) -> DedupeReport:
    report = find_duplicates()
    if apply:
        _merge_groups(report.url_groups)
        # URL merges can change content groups; recompute before merging those.
        report.content_groups = find_duplicates().content_groups
        _merge_groups(report.content_groups)
    report.links = plan_story_links()
    if apply:
        with transaction.atomic():
            for article_id, root_id in report.links:
                NewsArticle.objects.filter(pk=article_id).update(duplicate_of_id=root_id)
    return report
