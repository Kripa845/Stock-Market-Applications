"""
Recompute normalized_url now that normalize_url folds http:// into https://.
Stops with the clashing ids instead of violating the unique constraint when an
http and an https row of the same source would get the same identity.
"""
from collections import defaultdict

from django.db import migrations

from apps.news.services.normalize import normalize_url


def refold(apps, schema_editor):
    NewsArticle = apps.get_model("news", "NewsArticle")

    taken = defaultdict(list)
    changed = []
    for article in NewsArticle.objects.only("id", "news_source_id", "url", "normalized_url").iterator(chunk_size=500):
        new = normalize_url(article.url) or article.normalized_url
        taken[(article.news_source_id, new)].append(article.pk)
        if new != article.normalized_url:
            article.normalized_url = new
            changed.append(article)

    clashes = [ids for ids in taken.values() if len(ids) > 1]
    if clashes:
        raise RuntimeError(
            "http/https variants of the same article exist for one source (ids "
            + "; ".join(",".join(map(str, ids)) for ids in clashes[:20])
            + "). Keep one row per group (move tags/corrections like dedupe.merge_into), then migrate again."
        )
    NewsArticle.objects.bulk_update(changed, ["normalized_url"], batch_size=500)


class Migration(migrations.Migration):

    dependencies = [
        ("news", "0011_enforce_article_identity"),
    ]

    operations = [
        migrations.RunPython(refold, migrations.RunPython.noop),
    ]
