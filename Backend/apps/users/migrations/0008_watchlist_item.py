from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        (
            "users",
            "0007_user_company_access",
        ),
        (
            "companies",
            "0001_initial",
        ),
    ]

    operations = [
        migrations.CreateModel(
            name="WatchlistItem",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="watchlist_items",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="watchlist_items",
                        to="companies.company",
                    ),
                ),
            ],
            options={
                "ordering": [
                    "-created_at"
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=(
                            "user",
                            "company",
                        ),
                        name="unique_user_watchlist_company",
                    )
                ],
            },
        ),
    ]