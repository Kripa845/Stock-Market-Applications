from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("market_data", "0006_rename_traded_at_trade_time")]

    operations = [
        migrations.CreateModel(
            name="Broker",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("broker_code", models.CharField(max_length=100, unique=True)),
                ("name", models.CharField(max_length=200)),
                ("short_name", models.CharField(blank=True, max_length=100)),
                ("logo", models.CharField(blank=True, max_length=255)),
                ("website", models.URLField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["broker_code"]},
        ),
    ]
