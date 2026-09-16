"""
Celery background tasks for asynchronous News Auto-Categorization.
"""

import logging
from typing import Optional

from celery import shared_task
from django.db import DatabaseError

from apps.news.models import NewsArticle
from apps.news.services.categorization import (
    categorize_article,
    invalidate_company_cache,
)

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    name="apps.news.tasks.categorize_article_task",
)
def categorize_article_task(
    self,
    article_id: int,
    threshold: Optional[float] = None,
):
    """
    Asynchronous Celery task to categorize a newly crawled or updated NewsArticle.
    Ensures that ML inference and embedding computations run in the background
    without blocking Scrapy spiders or REST API requests.
    """
    logger.info("Executing categorize_article_task for article_id=%d", article_id)
    try:
        article = NewsArticle.objects.filter(pk=article_id).first()
        if not article:
            logger.warning("categorize_article_task: NewsArticle id=%d not found.", article_id)
            return {"article_id": article_id, "success": False, "error": "Article not found"}

        tags = categorize_article(article, threshold=threshold)
        tag_symbols = [f"{t.company.symbol}:{t.confidence:.2f}" for t in tags]

        logger.info(
            "Successfully categorized article_id=%d with %d tags: %s",
            article_id,
            len(tags),
            ", ".join(tag_symbols) if tag_symbols else "None (needs_review)",
        )
        return {
            "article_id": article_id,
            "success": True,
            "tag_count": len(tags),
            "tags": tag_symbols,
        }

    except DatabaseError as db_exc:
        logger.exception(
            "Database error during categorization of article_id=%d: %s. Retrying...",
            article_id,
            db_exc,
        )
        raise self.retry(exc=db_exc)
    except Exception as exc:
        logger.exception("Unexpected error categorizing article_id=%d: %s", article_id, exc)
        return {
            "article_id": article_id,
            "success": False,
            "error": str(exc),
        }


@shared_task(name="apps.news.tasks.categorize_unprocessed_news_task")
def categorize_unprocessed_news_task(batch_size: int = 50):
    """
    Periodic or background task to find unprocessed articles and categorize them.
    """
    unprocessed_articles = (
        NewsArticle.objects
        .filter(is_processed=False)
        .order_by("-id")[:batch_size]
    )

    count = 0
    success_count = 0
    for article in unprocessed_articles:
        count += 1
        try:
            categorize_article(article)
            success_count += 1
        except Exception as exc:
            logger.exception("Error in batch processing for article_id=%d: %s", article.id, exc)

    logger.info(
        "Batch categorization task complete. Attempted=%d, Succeeded=%d",
        count,
        success_count,
    )
    return {
        "attempted": count,
        "succeeded": success_count,
    }


@shared_task(name="apps.news.tasks.recategorize_all_news_task")
def recategorize_all_news_task(threshold: Optional[float] = None):
    """
    Recategorize all articles in the database.
    Useful when company profiles or aliases change.
    """
    invalidate_company_cache()
    articles = NewsArticle.objects.all().order_by("-id")
    total = articles.count()
    processed = 0

    for article in articles.iterator(chunk_size=100):
        try:
            categorize_article(article, threshold=threshold)
            processed += 1
        except Exception as exc:
            logger.exception("Error recategorizing article_id=%d: %s", article.id, exc)

    logger.info("Recategorize all complete: processed %d / %d articles.", processed, total)
    return {"total": total, "processed": processed}
