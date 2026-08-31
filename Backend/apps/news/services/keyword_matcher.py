import re

from apps.news.models import NewsArticle, Company


def normalize_text(text):
    """
    Normalize text for reliable company-name matching.
    """
    if not text:
        return ""

    text = text.lower()

    # Replace punctuation with spaces
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    # Remove duplicate whitespace
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def find_company_candidates(article: NewsArticle):
    """
    Find companies potentially related to an article.

    Matching sources:
    - Company symbol
    - Company name
    - Company aliases

    Returns a list of candidate companies with
    matching evidence.
    """

    article_text = normalize_text(
        f"{article.headline} {article.body}"
    )

    candidates = []

    companies = Company.objects.filter(
        is_active=True
    )

    for company in companies:

        possible_names = [
            company.symbol,
            company.name,
        ]

        # Add aliases from JSONField
        if company.aliases:
            possible_names.extend(company.aliases)

        matched_aliases = []

        for name in possible_names:

            if not name:
                continue

            normalized_name = normalize_text(str(name))

            if not normalized_name:
                continue

            # Word-boundary matching prevents partial matches.
            pattern = rf"\b{re.escape(normalized_name)}\b"

            if re.search(pattern, article_text):
                matched_aliases.append(str(name))

        if matched_aliases:

            # Remove duplicates while preserving order
            matched_aliases = list(
                dict.fromkeys(matched_aliases)
            )

            candidates.append(
                {
                    "company": company,
                    "keyword_score": 1.0,
                    "evidence": {
                        "matched_aliases": matched_aliases,
                    },
                }
            )

    return candidates