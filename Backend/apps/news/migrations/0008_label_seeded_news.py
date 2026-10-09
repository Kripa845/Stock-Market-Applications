"""
Label the synthetic articles written by ``seed_market_data`` as
``data_provenance="seeded"`` so read paths can exclude them.  Nothing is
deleted.  The seeder's own marker is a ``content_hash`` of the form
``hash_<n>_<random>``; a crawled article's hash is a 64-character SHA-256.
Reversible: going back restores "unverified" on exactly these rows.
"""

from django.db import migrations

SEEDER_HASH_PREFIX = "hash_"


def label_seeded(apps, schema_editor):
    NewsArticle = apps.get_model("news", "NewsArticle")
    NewsArticle.objects.filter(content_hash__startswith=SEEDER_HASH_PREFIX).update(data_provenance="seeded")


def unlabel_seeded(apps, schema_editor):
    NewsArticle = apps.get_model("news", "NewsArticle")
    NewsArticle.objects.filter(
        content_hash__startswith=SEEDER_HASH_PREFIX, data_provenance="seeded",
    ).update(data_provenance="unverified")


class Migration(migrations.Migration):

    dependencies = [
        ("news", "0007_newsarticle_image_url"),
    ]

    operations = [
        migrations.RunPython(label_seeded, unlabel_seeded),
    ]
