import re
from typing import Any

from apps.companies.models import Company
from apps.news.models import NewsArticle


def normalize_text(text: Any) -> str:
    """
    Normalize text for reliable company/entity matching.

    The normalization:
    - converts text to lowercase using casefold()
    - converts punctuation to spaces
    - preserves word boundaries
    - collapses repeated whitespace

    Example:

        "Nabil Bank, Ltd." -> "nabil bank ltd"
    """

    if text is None:
        return ""

    text = str(text).casefold()

    # Convert punctuation/symbols into spaces.
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)

    # Collapse repeated whitespace.
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def _compile_pattern(term: str) -> re.Pattern:
    """
    Create a safe word-boundary regex for a company term.

    Word boundaries prevent false matches such as:

        NICA -> Nicaragua

    when NICA is being matched as a standalone entity.
    """

    normalized_term = normalize_text(term)

    escaped_term = re.escape(normalized_term)

    return re.compile(
        rf"(?<!\w){escaped_term}(?!\w)",
        flags=re.IGNORECASE | re.UNICODE,
    )


def _find_matches(text: str, term: str) -> list[str]:
    """
    Return the exact matched strings found in text.
    """

    if not text or not term:
        return []

    pattern = _compile_pattern(term)

    return [
        match.group(0)
        for match in pattern.finditer(text)
    ]


def _build_terms(company: Company) -> list[dict]:
    """
    Build the searchable company vocabulary.

    Each term keeps its source so the confidence layer knows whether
    it came from the official symbol, canonical name, or alias.
    """

    terms = []

    # Official ticker/symbol.
    if company.symbol:
        terms.append(
            {
                "value": company.symbol,
                "type": "symbol",
            }
        )

    # Official company name.
    if company.name:
        terms.append(
            {
                "value": company.name,
                "type": "canonical_name",
            }
        )

    # Configured aliases.
    aliases = company.aliases or []

    if isinstance(aliases, list):
        for alias in aliases:

            if alias is None:
                continue

            alias = str(alias).strip()

            if not alias:
                continue

            terms.append(
                {
                    "value": alias,
                    "type": "alias",
                }
            )

    # Remove duplicate normalized terms while preserving the strongest
    # source type.
    unique_terms = {}

    priority = {
        "symbol": 3,
        "canonical_name": 2,
        "alias": 1,
    }

    for term in terms:

        normalized = normalize_text(term["value"])

        if not normalized:
            continue

        existing = unique_terms.get(normalized)

        if (
            existing is None
            or priority[term["type"]]
            > priority[existing["type"]]
        ):
            unique_terms[normalized] = {
                "value": term["value"],
                "type": term["type"],
            }

    return list(unique_terms.values())


def find_company_candidates(article: NewsArticle) -> list[dict]:
    """
    Find all active/tracked companies that are mentioned in an article.

    This is intentionally multi-label.

    One article can return:

        NABIL
        NICA
        ADBL

    instead of selecting only one company.

    Returns candidate dictionaries containing:

        company
        evidence
    """

    headline = normalize_text(article.headline)
    body = normalize_text(article.body)

    candidates = []

    companies = (
        Company.objects
        .filter(
            is_active=True,
            tracking__is_tracked=True,
        )
        .order_by("symbol")
    )

    for company in companies:

        terms = _build_terms(company)

        headline_matches = []
        body_matches = []

        matched_terms = []
        symbol_matches = []
        canonical_name_matches = []
        alias_matches = []

        for term in terms:

            value = term["value"]
            term_type = term["type"]

            headline_occurrences = _find_matches(
                headline,
                value,
            )

            body_occurrences = _find_matches(
                body,
                value,
            )

            if headline_occurrences:
                headline_matches.append(
                    {
                        "term": value,
                        "type": term_type,
                        "count": len(headline_occurrences),
                    }
                )

            if body_occurrences:
                body_matches.append(
                    {
                        "term": value,
                        "type": term_type,
                        "count": len(body_occurrences),
                    }
                )

            if headline_occurrences or body_occurrences:

                matched_terms.append(
                    {
                        "term": value,
                        "type": term_type,
                        "headline_count": len(
                            headline_occurrences
                        ),
                        "body_count": len(
                            body_occurrences
                        ),
                    }
                )

                if term_type == "symbol":
                    symbol_matches.append(value)

                elif term_type == "canonical_name":
                    canonical_name_matches.append(value)

                elif term_type == "alias":
                    alias_matches.append(value)

        if not matched_terms:
            continue

        headline_count = sum(
            item["count"]
            for item in headline_matches
        )

        body_count = sum(
            item["count"]
            for item in body_matches
        )

        candidates.append(
            {
                "company": company,
                "evidence": {
                    "matched_terms": matched_terms,
                    "headline_matches": headline_matches,
                    "body_matches": body_matches,
                    "headline_match_count": headline_count,
                    "body_match_count": body_count,
                    "total_match_count": (
                        headline_count + body_count
                    ),
                    "symbol_matches": list(
                        dict.fromkeys(symbol_matches)
                    ),
                    "canonical_name_matches": list(
                        dict.fromkeys(
                            canonical_name_matches
                        )
                    ),
                    "alias_matches": list(
                        dict.fromkeys(alias_matches)
                    ),
                },
            }
        )

    return candidates