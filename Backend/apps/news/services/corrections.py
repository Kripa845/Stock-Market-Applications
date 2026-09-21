"""
Persistent manual corrections to automatic categorization.

THE BUG THIS FIXES
------------------
``categorize_article`` guarded manual tags with ``if existing_tag and
existing_tag.is_manual``. That guard can only protect a tag that still
EXISTS. When an analyst removes a tag, the row is deleted, so on the next
automatic run ``existing_tag`` is ``None``, the model re-predicts the
company above threshold, and the tag is silently recreated. The analyst's
correction is lost, and it is lost again on every subsequent run.

``CategorizationCorrection`` rows were already being written but were
never read back by the categorizer, so the audit trail existed while the
behaviour it was supposed to drive did not.

THE MINIMAL ARCHITECTURE
------------------------
No new model is needed. The existing pieces are sufficient:

    ArticleCompanyTag.is_manual    -- this tag is human-owned, do not touch
    CategorizationCorrection       -- the durable log of what a human did

The one missing piece is *reading* the correction log before writing
tags. A removal is a correction with no surviving row, so the log is the
only place that fact can live. This module turns that log into a decision
table the categorizer consults.

Resolution rule: for each (article, company) the LATEST correction wins.
An analyst who removes a tag and later re-adds it gets the re-add.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

from django.db import transaction

from apps.news.models import ArticleCompanyTag, CategorizationCorrection

logger = logging.getLogger(__name__)


ACTION_ADD = "add"
ACTION_REMOVE = "remove"
ACTION_UPDATE = "update"

VALID_ACTIONS = frozenset({ACTION_ADD, ACTION_REMOVE, ACTION_UPDATE})

#: Method string stamped on tags a human created or edited, so manual and
#: automatic provenance stay distinguishable in the API and in exports.
METHOD_MANUAL = "manual"


def get_correction_map(article) -> Dict[int, CategorizationCorrection]:
    """
    Latest correction per company for one article, keyed by ``company_id``.

    Ordering by ``corrected_at`` then ``id`` makes the result stable even
    when two corrections land inside the same clock tick, which matters
    because ``auto_now_add`` has limited resolution and tests routinely
    create several corrections in the same millisecond.
    """
    corrections = (
        CategorizationCorrection.objects
        .filter(article=article)
        .order_by("corrected_at", "id")
    )

    latest: Dict[int, CategorizationCorrection] = {}

    for correction in corrections:
        latest[correction.company_id] = correction

    return latest


def is_suppressed(correction: Optional[CategorizationCorrection]) -> bool:
    """True when a human removed this company and has not re-added it."""
    return correction is not None and correction.action == ACTION_REMOVE


def is_pinned(correction: Optional[CategorizationCorrection]) -> bool:
    """True when a human added or edited this tag and it must be preserved."""
    return correction is not None and correction.action in {
        ACTION_ADD,
        ACTION_UPDATE,
    }


# ---------------------------------------------------------------------------
# Correction operations
# ---------------------------------------------------------------------------

@transaction.atomic
def apply_remove(article, company, user=None, reason: str = ""):
    """
    Remove a company tag and record the correction so it persists.

    Deleting the row alone is not enough -- the next automatic run would
    recreate it. The ``CategorizationCorrection`` row is what makes the
    removal durable.

    Idempotent: removing an already-removed tag records the intent again
    but changes nothing else.
    """
    existing = (
        ArticleCompanyTag.objects
        .filter(article=article, company=company)
        .first()
    )

    correction = CategorizationCorrection.objects.create(
        article=article,
        company=company,
        previous_confidence=existing.confidence if existing else None,
        previous_method=existing.method if existing else "",
        action=ACTION_REMOVE,
        reason=reason,
        corrected_by=user,
    )

    if existing:
        existing.delete()

    logger.info(
        "Manual REMOVE | article_id=%s | company=%s | by=%s",
        article.id,
        company.symbol,
        getattr(user, "username", "system"),
    )

    return correction


@transaction.atomic
def apply_add(article, company, confidence: float = 1.0,
              user=None, reason: str = ""):
    """
    Add a company tag manually and record the correction.

    The tag is written with ``is_manual=True`` so automatic runs skip it,
    AND a correction row is written so the intent survives even if the
    tag row is later lost or rebuilt.
    """
    _validate_confidence(confidence)

    existing = (
        ArticleCompanyTag.objects
        .filter(article=article, company=company)
        .first()
    )

    correction = CategorizationCorrection.objects.create(
        article=article,
        company=company,
        previous_confidence=existing.confidence if existing else None,
        previous_method=existing.method if existing else "",
        action=ACTION_ADD,
        reason=reason,
        corrected_by=user,
    )

    tag, _ = ArticleCompanyTag.objects.update_or_create(
        article=article,
        company=company,
        defaults={
            "confidence": float(confidence),
            "method": METHOD_MANUAL,
            "is_manual": True,
            "evidence": {
                "source": "manual_correction",
                "action": ACTION_ADD,
                "corrected_by": getattr(user, "username", None),
                "reason": reason,
                "note": (
                    "Analyst-assigned tag. Confidence is an analyst "
                    "assertion, not a model score."
                ),
            },
        },
    )

    logger.info(
        "Manual ADD | article_id=%s | company=%s | by=%s",
        article.id,
        company.symbol,
        getattr(user, "username", "system"),
    )

    return tag, correction


@transaction.atomic
def apply_update(article, company, confidence: Optional[float] = None,
                 user=None, reason: str = ""):
    """
    Update an existing tag's confidence and mark it human-owned.

    Raises ``ArticleCompanyTag.DoesNotExist`` when there is nothing to
    update; callers should surface that as a 404 rather than silently
    creating a tag, because "update" and "add" are different analyst
    intentions and conflating them hides mistakes.
    """
    tag = ArticleCompanyTag.objects.filter(
        article=article, company=company,
    ).first()

    if tag is None:
        raise ArticleCompanyTag.DoesNotExist(
            f"No tag for article={article.id} company={company.symbol}"
        )

    if confidence is not None:
        _validate_confidence(confidence)

    correction = CategorizationCorrection.objects.create(
        article=article,
        company=company,
        previous_confidence=tag.confidence,
        previous_method=tag.method,
        action=ACTION_UPDATE,
        reason=reason,
        corrected_by=user,
    )

    if confidence is not None:
        tag.confidence = float(confidence)

    tag.is_manual = True
    tag.method = METHOD_MANUAL

    evidence = dict(tag.evidence or {})
    evidence.update({
        "source": "manual_correction",
        "action": ACTION_UPDATE,
        "corrected_by": getattr(user, "username", None),
        "reason": reason,
        "previous_confidence": correction.previous_confidence,
        "previous_method": correction.previous_method,
    })
    tag.evidence = evidence

    tag.save(update_fields=["confidence", "is_manual", "method", "evidence", "updated_at"])

    logger.info(
        "Manual UPDATE | article_id=%s | company=%s | by=%s",
        article.id,
        company.symbol,
        getattr(user, "username", "system"),
    )

    return tag, correction


def _validate_confidence(value):
    """Confidence is a bounded score; reject anything outside [0, 1]."""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        raise ValueError("confidence must be a number between 0.0 and 1.0")

    if not (0.0 <= numeric <= 1.0):
        raise ValueError("confidence must be between 0.0 and 1.0")

    return numeric
