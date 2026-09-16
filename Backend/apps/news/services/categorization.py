"""
Production-grade AI/ML News Auto-Categorization Service.

Combines:
1. Deterministic company alias / entity lexical matching
2. Semantic sentence embeddings (SentenceTransformers / cosine similarity)
3. Multi-label independent confidence scoring
4. Manual Analyst correction precedence and audit trail
"""

import logging
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from django.conf import settings
from django.db import transaction

from apps.companies.models import Company
from apps.news.models import ArticleCompanyTag, NewsArticle

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global In-Memory Singletons & Caches (Worker/Process Lifetime)
# ---------------------------------------------------------------------------
_EMBEDDING_MODEL = None
_COMPANY_EMBEDDINGS_CACHE: Dict[int, Dict[str, Any]] = {}


def normalize_text(text: Any) -> str:
    """
    Normalize text for robust entity matching and embedding extraction:
    - Strips HTML remnants
    - Performs Unicode NFKC normalization
    - Converts to lowercase using casefold()
    - Replaces punctuation with spaces for lexical matching
    - Collapses multiple whitespace characters
    """
    if text is None:
        return ""

    text = str(text)

    # Strip HTML tags if any
    text = re.sub(r"<[^>]+>", " ", text)

    # Unicode normalization
    text = unicodedata.normalize("NFKC", text)

    # Convert to lowercase
    text = text.casefold()

    # Convert punctuation/symbols into spaces while preserving words and digits
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)

    # Collapse repeated whitespace
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def build_article_text(article: NewsArticle) -> str:
    """
    Build clean normalized text representation from headline and body.
    Original NewsArticle database fields remain unmodified.
    """
    headline = normalize_text(article.headline or "")
    body = normalize_text(article.body or "")

    if headline and body:
        return f"{headline}\n\n{body}"
    elif headline:
        return headline
    elif body:
        return body
    return ""


def build_company_profile(company: Company) -> str:
    """
    Generate a standardized semantic profile for a company.
    Example:
      "Company: Nabil Bank Limited. Symbol: NABIL. Sector: Commercial Bank. Aliases: Nabil Bank, Nabil, NABIL."
    """
    aliases = company.aliases or []
    if isinstance(aliases, list):
        clean_aliases = [str(a).strip() for a in aliases if a and str(a).strip()]
    else:
        clean_aliases = []

    # Ensure official symbol and name are included in aliases list for completeness
    all_names = list(dict.fromkeys([company.name, company.symbol] + clean_aliases))
    aliases_str = ", ".join(all_names) if all_names else company.name

    return (
        f"Company: {company.name}. "
        f"Symbol: {company.symbol}. "
        f"Sector: {company.sector}. "
        f"Aliases: {aliases_str}."
    )


# ---------------------------------------------------------------------------
# Embedding Model & Vector Utilities
# ---------------------------------------------------------------------------

def get_embedding_model():
    """
    Lazy process-level singleton loader for the sentence-transformers model.
    Reuses the model in memory across articles and requests.
    """
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is None:
        model_name = getattr(
            settings,
            "CATEGORIZATION_EMBEDDING_MODEL",
            "all-MiniLM-L6-v2",
        )
        logger.info("Initializing SentenceTransformer model: %s", model_name)
        try:
            from sentence_transformers import SentenceTransformer
            _EMBEDDING_MODEL = SentenceTransformer(model_name)
            logger.info("SentenceTransformer model %s loaded successfully.", model_name)
        except Exception as exc:
            logger.exception("Failed to load SentenceTransformer model %s: %s", model_name, exc)
            raise RuntimeError(f"Embedding model initialization failed: {exc}") from exc

    return _EMBEDDING_MODEL


def encode_text(text: str) -> np.ndarray:
    """
    Encode text into a normalized dense embedding vector.
    """
    if not text.strip():
        # Return zero vector if text is completely empty
        return np.zeros(384, dtype=np.float32)

    model = get_embedding_model()
    embedding = model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
    return np.asarray(embedding, dtype=np.float32)


def calculate_cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """
    Calculate cosine similarity between two 1D vectors:
    sim = (a . b) / (||a|| * ||b||)
    Returns float in range [0.0, 1.0].
    """
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    similarity = float(np.dot(vec_a, vec_b) / (norm_a * norm_b))
    # Clamp to [0.0, 1.0] for cosine similarity of semantic embeddings
    return float(max(0.0, min(1.0, similarity)))


# ---------------------------------------------------------------------------
# Cached Company Profiles & Profile Embeddings
# ---------------------------------------------------------------------------

def invalidate_company_cache() -> None:
    """Clear the cached company profile embeddings."""
    global _COMPANY_EMBEDDINGS_CACHE
    _COMPANY_EMBEDDINGS_CACHE.clear()
    logger.info("Company profile embeddings cache cleared.")


def get_company_profiles_cache(force_refresh: bool = False) -> Dict[int, Dict[str, Any]]:
    """
    Retrieve or compute cached company profile embeddings for all active/tracked companies.
    Avoids recomputing company embeddings for every incoming article.
    """
    global _COMPANY_EMBEDDINGS_CACHE

    if force_refresh or not _COMPANY_EMBEDDINGS_CACHE:
        companies = (
            Company.objects
            .filter(is_active=True)
            .order_by("symbol")
        )

        new_cache = {}
        for company in companies:
            profile_text = build_company_profile(company)
            vector = encode_text(profile_text)
            new_cache[company.id] = {
                "company": company,
                "profile_text": profile_text,
                "vector": vector,
            }

        _COMPANY_EMBEDDINGS_CACHE = new_cache
        logger.info("Generated and cached profile embeddings for %d companies.", len(new_cache))

    return _COMPANY_EMBEDDINGS_CACHE


# ---------------------------------------------------------------------------
# Lexical / Entity Matching Layer
# ---------------------------------------------------------------------------

def _compile_pattern(term: str) -> re.Pattern:
    """
    Create a safe word-boundary regular expression.
    Prevents false substrings (e.g., matching 'NICA' inside 'Nicaragua').
    """
    normalized_term = normalize_text(term)
    escaped = re.escape(normalized_term)
    return re.compile(rf"(?<!\w){escaped}(?!\w)", flags=re.IGNORECASE | re.UNICODE)


def calculate_lexical_score(
    article: NewsArticle,
    company: Company,
) -> Tuple[float, Dict[str, Any]]:
    """
    Deterministic company alias/entity matching.
    Evaluates official symbol, canonical name, and aliases against headline and body.

    Returns:
        (lexical_score: float in [0.0, 1.0], evidence: dict)
    """
    headline = normalize_text(article.headline or "")
    body = normalize_text(article.body or "")

    # Build search terms for this company
    terms_to_check = []

    if company.symbol:
        terms_to_check.append({"value": company.symbol, "type": "symbol"})

    if company.name:
        terms_to_check.append({"value": company.name, "type": "canonical_name"})

    aliases = company.aliases or []
    if isinstance(aliases, list):
        for alias in aliases:
            if alias and str(alias).strip():
                terms_to_check.append({"value": str(alias).strip(), "type": "alias"})

    headline_matches = []
    body_matches = []
    matched_terms = []

    symbol_matched = False
    name_matched = False
    alias_matched = False

    for term_info in terms_to_check:
        term_val = term_info["value"]
        term_type = term_info["type"]
        pattern = _compile_pattern(term_val)

        h_matches = [m.group(0) for m in pattern.finditer(headline)] if headline else []
        b_matches = [m.group(0) for m in pattern.finditer(body)] if body else []

        if h_matches:
            headline_matches.append({
                "term": term_val,
                "type": term_type,
                "count": len(h_matches),
            })
        if b_matches:
            body_matches.append({
                "term": term_val,
                "type": term_type,
                "count": len(b_matches),
            })

        if h_matches or b_matches:
            matched_terms.append({
                "term": term_val,
                "type": term_type,
                "headline_count": len(h_matches),
                "body_count": len(b_matches),
            })
            if term_type == "symbol":
                symbol_matched = True
            elif term_type == "canonical_name":
                name_matched = True
            elif term_type == "alias":
                alias_matched = True

    headline_count = sum(m["count"] for m in headline_matches)
    body_count = sum(m["count"] for m in body_matches)
    total_count = headline_count + body_count

    # Calculate normalized lexical score in [0.0, 1.0]
    if total_count == 0:
        score = 0.0
    else:
        # Base score from match type & location
        base_score = 0.0
        if symbol_matched:
            # Exact ticker match is a very strong deterministic signal
            base_score = 0.95 if headline_count > 0 else 0.85
        elif name_matched:
            # Full canonical company name is also very strong
            base_score = 0.95 if headline_count > 0 else 0.85
        elif alias_matched:
            # Recognized alias
            base_score = 0.85 if headline_count > 0 else 0.75

        # Mention frequency boost (each additional mention adds +0.03, capped at 1.0)
        frequency_boost = min(0.15, (total_count - 1) * 0.03)
        score = min(1.0, base_score + frequency_boost)

    evidence = {
        "lexical_score": round(score, 4),
        "total_match_count": total_count,
        "headline_match_count": headline_count,
        "body_match_count": body_count,
        "matched_terms": matched_terms,
        "headline_matches": headline_matches,
        "body_matches": body_matches,
    }

    return score, evidence


# ---------------------------------------------------------------------------
# Hybrid Scoring Formula
# ---------------------------------------------------------------------------

def calculate_hybrid_score(
    semantic_similarity: float,
    lexical_score: float,
    embedding_weight: Optional[float] = None,
    keyword_weight: Optional[float] = None,
) -> float:
    """
    Combine lexical evidence and semantic embedding similarity:
    final_score = (w_embed * semantic_similarity) + (w_kw * lexical_score)
    """
    if embedding_weight is None:
        embedding_weight = getattr(settings, "CATEGORIZATION_EMBEDDING_WEIGHT", 0.60)
    if keyword_weight is None:
        keyword_weight = getattr(settings, "CATEGORIZATION_KEYWORD_WEIGHT", 0.40)

    # Normalize weights so they sum to 1.0 if customized
    total_w = embedding_weight + keyword_weight
    if total_w > 0:
        w_emb = embedding_weight / total_w
        w_kw = keyword_weight / total_w
    else:
        w_emb, w_kw = 0.60, 0.40

    final_score = (w_emb * semantic_similarity) + (w_kw * lexical_score)
    return round(float(max(0.0, min(1.0, final_score))), 4)


# ---------------------------------------------------------------------------
# Main Categorization Pipeline
# ---------------------------------------------------------------------------

def categorize_article(
    article_or_id: Union[NewsArticle, int],
    threshold: Optional[float] = None,
    force_recompute: bool = False,
) -> List[ArticleCompanyTag]:
    """
    Production categorization pipeline for a single NewsArticle:
    1. Fetches article from PostgreSQL.
    2. Builds normalized article text.
    3. Generates article embedding once.
    4. Evaluates EVERY tracked company independently (Multi-Label classification).
    5. Computes lexical matching score & semantic cosine similarity.
    6. Combines signals into independent heuristic confidence score.
    7. Respects manual corrections: manual tags (is_manual=True) are NEVER overwritten.
    8. Persists ArticleCompanyTag records with confidence, method='hybrid', and evidence.
    9. Removes obsolete automatic tags that no longer meet the threshold.
    10. Marks article as processed.

    Returns:
        List of ArticleCompanyTag records for the article.
    """
    if isinstance(article_or_id, NewsArticle):
        article = article_or_id
    else:
        article = NewsArticle.objects.select_related("raw_article").get(pk=article_or_id)

    if threshold is None:
        threshold = getattr(settings, "CATEGORIZATION_THRESHOLD", 0.65)

    emb_weight = getattr(settings, "CATEGORIZATION_EMBEDDING_WEIGHT", 0.60)
    kw_weight = getattr(settings, "CATEGORIZATION_KEYWORD_WEIGHT", 0.40)

    logger.info("Starting auto-categorization for article_id=%d: '%s'", article.id, article.headline[:60])

    # 1. Build article text representation
    article_text = build_article_text(article)
    if not article_text:
        logger.warning("Article_id=%d has empty text; marking processed without tags.", article.id)
        article.is_processed = True
        article.save(update_fields=["is_processed"])
        return list(article.company_tags.all())

    # 2. Generate article embedding vector (once per article)
    article_vector = encode_text(article_text)

    # 3. Get cached company profiles & embeddings
    company_profiles = get_company_profiles_cache()
    if not company_profiles:
        logger.warning("No active companies found for categorization.")
        article.is_processed = True
        article.save(update_fields=["is_processed"])
        return []

    # 4. Fetch existing tags for the article to respect manual corrections
    existing_tags = {tag.company_id: tag for tag in article.company_tags.all()}

    generated_tags: List[ArticleCompanyTag] = []
    tagged_company_symbols = []

    with transaction.atomic():
        for company_id, comp_data in company_profiles.items():
            company = comp_data["company"]
            comp_vector = comp_data["vector"]

            # Compute signals independently
            lex_score, lex_evidence = calculate_lexical_score(article, company)
            semantic_sim = calculate_cosine_similarity(article_vector, comp_vector)
            final_confidence = calculate_hybrid_score(
                semantic_similarity=semantic_sim,
                lexical_score=lex_score,
                embedding_weight=emb_weight,
                keyword_weight=kw_weight,
            )

            existing_tag = existing_tags.get(company_id)

            # RULE: Manual correction takes precedence over automatic prediction
            if existing_tag and existing_tag.is_manual:
                logger.debug(
                    "Article_id=%d company=%s has manual tag (confidence=%.2f); skipping overwrite.",
                    article.id,
                    company.symbol,
                    existing_tag.confidence,
                )
                generated_tags.append(existing_tag)
                continue

            # Independent threshold decision for each company
            if final_confidence >= threshold:
                evidence_payload = {
                    "lexical_score": lex_score,
                    "semantic_similarity": round(semantic_sim, 4),
                    "final_score": final_confidence,
                    "weights": {
                        "embedding_weight": emb_weight,
                        "keyword_weight": kw_weight,
                    },
                    "lexical_evidence": lex_evidence,
                }

                tag, _ = ArticleCompanyTag.objects.update_or_create(
                    article=article,
                    company=company,
                    defaults={
                        "confidence": final_confidence,
                        "method": "hybrid",
                        "evidence": evidence_payload,
                        "is_manual": False,
                    },
                )
                generated_tags.append(tag)
                tagged_company_symbols.append(f"{company.symbol}({final_confidence:.2f})")
            else:
                # Remove automatic tag if it previously existed but now falls below threshold
                if existing_tag and not existing_tag.is_manual:
                    logger.info(
                        "Removing auto tag article_id=%d company=%s (confidence %.2f < threshold %.2f)",
                        article.id,
                        company.symbol,
                        final_confidence,
                        threshold,
                    )
                    existing_tag.delete()

        # Mark article as processed
        article.is_processed = True
        article.save(update_fields=["is_processed"])

    if tagged_company_symbols:
        logger.info(
            "Categorized article_id=%d with tags: %s",
            article.id,
            ", ".join(tagged_company_symbols),
        )
    else:
        logger.warning(
            "No company matched article_id=%d above threshold=%.2f (needs_review=True)",
            article.id,
            threshold,
        )

    return generated_tags
