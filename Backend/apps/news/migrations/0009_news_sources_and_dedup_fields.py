"""
Schema for source provenance and de-duplication. New article fields start
nullable/blank; 0010 backfills them and 0011 enforces NOT NULL + uniqueness.
"""
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("news", "0008_label_seeded_news"),
        ("crawler_runs", "0013_crawlrun_articles_duplicate"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="NewsSource",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(unique=True)),
                ("name", models.CharField(max_length=100, unique=True)),
                ("base_url", models.URLField(max_length=300)),
                ("logo_url", models.URLField(blank=True, default="", max_length=500)),
                ("brand_color", models.CharField(blank=True, default="", max_length=7)),
                ("fetch_type", models.CharField(
                    choices=[("rss", "RSS"), ("scrape", "Scrape"), ("api", "API")], default="scrape", max_length=10,
                )),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.AlterField(
            model_name="rawarticle",
            name="crawl_run",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="raw_articles", to="crawler_runs.crawlrun",
            ),
        ),
        migrations.AddField(
            model_name="newsarticle",
            name="news_source",
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.PROTECT, related_name="articles", to="news.newssource",
            ),
        ),
        migrations.AddField(
            model_name="newsarticle",
            name="normalized_url",
            field=models.CharField(default="", max_length=1000),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="newsarticle",
            name="external_id",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
        migrations.AddField(
            model_name="newsarticle",
            name="ingest_run",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="ingested_articles", to="crawler_runs.crawlrun",
            ),
        ),
        migrations.AddField(
            model_name="newsarticle",
            name="canonical_hash",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="newsarticle",
            name="duplicate_of",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="also_reported", to="news.newsarticle",
            ),
        ),
        migrations.AddField(
            model_name="newsarticle",
            name="last_seen_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.CreateModel(
            name="ArticleLike",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("article", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="likes", to="news.newsarticle",
                )),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="article_likes",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("article", "user"), name="unique_article_like_per_user"),
                ],
            },
        ),
        migrations.CreateModel(
            name="ArticleComment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("body", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("article", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="comments", to="news.newsarticle",
                )),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="article_comments",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "ordering": ["created_at"],
                "indexes": [models.Index(fields=["article", "created_at"], name="news_comment_article_created")],
            },
        ),
    ]
