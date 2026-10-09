"""
Read-side filters for news.

``seed_market_data`` writes synthetic demo articles labelled
``data_provenance="seeded"``; no page, export or calculation may show them.
Crawled and pre-provenance ("unverified") articles are real pages and are kept.
The crawl pipeline and its duplicate detection do not use these filters.
"""

SEEDED = "seeded"


def real_articles(queryset):
    return queryset.exclude(data_provenance=SEEDED)


def real_tags(queryset):
    """ArticleCompanyTag rows whose article is real."""
    return queryset.exclude(article__data_provenance=SEEDED)
