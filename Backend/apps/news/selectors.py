

SEEDED = "seeded"


def real_articles(queryset):
    return queryset.exclude(data_provenance=SEEDED)


def real_tags(queryset):
    """ArticleCompanyTag rows whose article is real."""
    return queryset.exclude(article__data_provenance=SEEDED)
