from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crawler_runs", "0012_dividends_crawled"),
    ]

    operations = [
        migrations.AddField(
            model_name="crawlrun",
            name="articles_duplicate",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
