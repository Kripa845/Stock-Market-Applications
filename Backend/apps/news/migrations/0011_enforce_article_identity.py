"""
NOT NULL source/date and unique (source, normalized_url) / (source, external_id).
Stops with a readable message if old data still has same-source duplicates;
`manage.py dedupe_news --apply` merges them, then re-run migrate.
"""
from django.db import migrations, models
from django.db.models import Count


def check_no_duplicates(apps, schema_editor):
    NewsArticle = apps.get_model("news", "NewsArticle")
    problems = []
    dup_urls = (
        NewsArticle.objects.values("news_source", "normalized_url")
        .annotate(n=Count("id")).filter(n__gt=1).count()
    )
    if dup_urls:
        problems.append(f"{dup_urls} same-source normalized URL groups")
    if NewsArticle.objects.filter(news_source__isnull=True).exists():
        problems.append("articles without a source")
    if NewsArticle.objects.filter(published_at__isnull=True).exists():
        problems.append("articles without published_at (fix with repair_news_dates)")
    if problems:
        raise RuntimeError(
            "Cannot enforce article identity: " + "; ".join(problems)
            + ". Run `manage.py dedupe_news --apply`, then `migrate` again."
        )


class Migration(migrations.Migration):

    dependencies = [
        ("news", "0010_backfill_news_sources"),
    ]

    operations = [
        migrations.RunPython(check_no_duplicates, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="newsarticle",
            name="news_source",
            field=models.ForeignKey(
                on_delete=models.deletion.PROTECT, related_name="articles", to="news.newssource",
            ),
        ),
        migrations.AlterField(
            model_name="newsarticle",
            name="published_at",
            field=models.DateTimeField(),
        ),
        migrations.AddConstraint(
            model_name="newsarticle",
            constraint=models.UniqueConstraint(
                fields=("news_source", "normalized_url"), name="unique_article_source_normalized_url",
            ),
        ),
        migrations.AddConstraint(
            model_name="newsarticle",
            constraint=models.UniqueConstraint(
                condition=models.Q(("external_id", ""), _negated=True),
                fields=("news_source", "external_id"),
                name="unique_article_source_external_id",
            ),
        ),
        migrations.AddConstraint(
            model_name="newsarticle",
            constraint=models.CheckConstraint(
                condition=models.Q(models.Q(("url", ""), _negated=True), models.Q(("normalized_url", ""), _negated=True)),
                name="article_source_url_required",
            ),
        ),
        migrations.AddIndex(
            model_name="newsarticle",
            index=models.Index(fields=["-published_at"], name="news_article_published_desc"),
        ),
    ]
