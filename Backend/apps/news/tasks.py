# """
# Celery background tasks for asynchronous News Auto-Categorization.
# """

# import logging
# from typing import Optional

# from celery import shared_task
# from django.db import DatabaseError

# from apps.news.models import NewsArticle
# from apps.news.services.categorization import (
#     categorize_article,
#     invalidate_company_cache,
# )

# logger = logging.getLogger(__name__)


# @shared_task(
#     bind=True,
#     max_retries=3,
#     default_retry_delay=10,
#     name="apps.news.tasks.categorize_article_task",
# )
# def categorize_article_task(
#     self,
#     article_id: int,
#     threshold: Optional[float] = None,
# ):
   
#     logger.info("Executing categorize_article_task for article_id=%d", article_id)
#     try:
#         article = NewsArticle.objects.filter(pk=article_id).first()
#         if not article:
#             logger.warning("categorize_article_task: NewsArticle id=%d not found.", article_id)
#             return {"article_id": article_id, "success": False, "error": "Article not found"}

#         tags = categorize_article(article, threshold=threshold)
#         tag_symbols = [f"{t.company.symbol}:{t.confidence:.2f}" for t in tags]

#         logger.info(
#             "Successfully categorized article_id=%d with %d tags: %s",
#             article_id,
#             len(tags),
#             ", ".join(tag_symbols) if tag_symbols else "None (needs_review)",
#         )
#         return {
#             "article_id": article_id,
#             "success": True,
#             "tag_count": len(tags),
#             "tags": tag_symbols,
#         }

#     except DatabaseError as db_exc:
#         logger.exception(
#             "Database error during categorization of article_id=%d: %s. Retrying...",
#             article_id,
#             db_exc,
#         )
#         raise self.retry(exc=db_exc)
#     except Exception as exc:
#         logger.exception("Unexpected error categorizing article_id=%d: %s", article_id, exc)
#         return {
#             "article_id": article_id,
#             "success": False,
#             "error": str(exc),
#         }


# @shared_task(name="apps.news.tasks.categorize_unprocessed_news_task")
# def categorize_unprocessed_news_task(batch_size: int = 50):
    
#     unprocessed_articles = (
#         NewsArticle.objects
#         .filter(is_processed=False)
#         .order_by("-id")[:batch_size]
#     )

#     count = 0
#     success_count = 0
#     for article in unprocessed_articles:
#         count += 1
#         try:
#             categorize_article(article)
#             success_count += 1
#         except Exception as exc:
#             logger.exception("Error in batch processing for article_id=%d: %s", article.id, exc)

#     logger.info(
#         "Batch categorization task complete. Attempted=%d, Succeeded=%d",
#         count,
#         success_count,
#     )
#     return {
#         "attempted": count,
#         "succeeded": success_count,
#     }


# @shared_task(name="apps.news.tasks.recategorize_all_news_task")
# def recategorize_all_news_task(threshold: Optional[float] = None):
    
#     invalidate_company_cache()
#     articles = NewsArticle.objects.all().order_by("-id")
#     total = articles.count()
#     processed = 0

#     for article in articles.iterator(chunk_size=100):
#         try:
#             categorize_article(article, threshold=threshold)
#             processed += 1
#         except Exception as exc:
#             logger.exception("Error recategorizing article_id=%d: %s", article.id, exc)

#     logger.info("Recategorize all complete: processed %d / %d articles.", processed, total)
#     return {"total": total, "processed": processed}
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


# ===========================================================================
# SENTIMENT PROCESSING
# ===========================================================================
#
# Sentiment never runs inside a DRF request. It is a whole-text pass over
# every unscored article, so doing it on the request path would make page
# load time a function of how many articles the crawler happened to add.
# API views read the stored columns.

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    name="apps.news.tasks.analyze_article_sentiment_task",
)
def analyze_article_sentiment_task(self, article_id: int):
    """
    Score one article and persist the result.

    Idempotent: the score is a pure function of the stored headline and
    body, so re-running rewrites the same values.
    """
    from apps.news.services.sentiment import apply_sentiment

    article = NewsArticle.objects.filter(pk=article_id).first()

    if not article:
        logger.warning("analyze_article_sentiment_task: article id=%d not found", article_id)
        return {"article_id": article_id, "success": False, "error": "Article not found"}

    try:
        result = apply_sentiment(article)
    except DatabaseError as db_exc:
        logger.exception("DB error scoring article_id=%d: %s", article_id, db_exc)
        raise self.retry(exc=db_exc)

    logger.info(
        "Sentiment | article_id=%d | status=%s | language=%s | score=%s | label=%s",
        article_id,
        result.status,
        result.language,
        result.score,
        result.label or "-",
    )

    return {
        "article_id": article_id,
        "success": True,
        "status": result.status,
        "score": result.score,
        "label": result.label,
        "language": result.language,
    }


@shared_task(name="apps.news.tasks.analyze_unscored_sentiment_task")
def analyze_unscored_sentiment_task(batch_size: int = 200):
    """
    Score every article still marked ``pending``.

    One article failing must never abort the batch, so each is wrapped
    individually and failures are counted and reported rather than
    raised. That is the difference between losing one article's score and
    losing the whole crawl's worth of scores.
    """
    from apps.news.services.sentiment import (
        STATUS_ERROR,
        apply_sentiment,
    )

    articles = (
        NewsArticle.objects
        .filter(sentiment_status="pending")
        .order_by("-id")[:batch_size]
    )

    attempted = 0
    succeeded = 0
    failed = 0
    by_status = {}

    for article in articles:
        attempted += 1
        try:
            result = apply_sentiment(article)
            by_status[result.status] = by_status.get(result.status, 0) + 1

            if result.status == STATUS_ERROR:
                failed += 1
            else:
                succeeded += 1

        except Exception as exc:  # noqa: BLE001 - isolate per-article failure
            failed += 1
            logger.exception("Sentiment failed for article_id=%d: %s", article.id, exc)
            try:
                NewsArticle.objects.filter(pk=article.id).update(
                    sentiment_status=STATUS_ERROR,
                    sentiment_error=f"{type(exc).__name__}: {exc}",
                )
            except Exception:  # noqa: BLE001
                logger.exception("Could not record sentiment error for %d", article.id)

    logger.info(
        "Sentiment batch complete | attempted=%d | succeeded=%d | failed=%d | statuses=%s",
        attempted,
        succeeded,
        failed,
        by_status,
    )

    return {
        "attempted": attempted,
        "succeeded": succeeded,
        "failed": failed,
        "by_status": by_status,
    }


@shared_task(name="apps.news.tasks.rescore_all_sentiment_task")
def rescore_all_sentiment_task():
    """
    Re-score every article, e.g. after a lexicon change.

    Resets status to pending first so the batch task picks them all up.
    """
    total = NewsArticle.objects.update(sentiment_status="pending")
    logger.info("Reset %d articles to pending for re-scoring.", total)

    processed = 0
    while True:
        outcome = analyze_unscored_sentiment_task(batch_size=500)
        if outcome["attempted"] == 0:
            break
        processed += outcome["attempted"]

    return {"reset": total, "processed": processed}
