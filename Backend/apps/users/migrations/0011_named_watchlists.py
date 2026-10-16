from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def move_items_to_primary(apps, schema_editor):
    """Existing saved companies go into a "Primary" default list per user."""
    Watchlist = apps.get_model("users", "Watchlist")
    WatchlistItem = apps.get_model("users", "WatchlistItem")
    user_ids = WatchlistItem.objects.values_list("user_id", flat=True).distinct()
    for user_id in user_ids:
        watchlist, _ = Watchlist.objects.get_or_create(
            user_id=user_id, name="Primary", defaults={"is_default": True},
        )
        WatchlistItem.objects.filter(user_id=user_id).update(watchlist=watchlist)


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0010_strip_retired_permission_keys"),
        ("companies", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Watchlist",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=60)),
                ("is_default", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="watchlists",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-is_default", "created_at"],
                "constraints": [
                    models.UniqueConstraint(fields=("user", "name"), name="unique_user_watchlist_name"),
                ],
            },
        ),
        migrations.AddField(
            model_name="watchlistitem",
            name="watchlist",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="items",
                to="users.watchlist",
            ),
        ),
        migrations.AddField(
            model_name="watchlistitem",
            name="units",
            field=models.PositiveBigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="watchlistitem",
            name="wacc",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.RunPython(move_items_to_primary, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="watchlistitem",
            name="watchlist",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="items",
                to="users.watchlist",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="watchlistitem",
            name="unique_user_watchlist_company",
        ),
        migrations.AddConstraint(
            model_name="watchlistitem",
            constraint=models.UniqueConstraint(fields=("watchlist", "company"), name="unique_watchlist_company"),
        ),
    ]
