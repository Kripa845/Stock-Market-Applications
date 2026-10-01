from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [("market_data", "0007_broker")]

    operations = [
        migrations.AddField(
            model_name="broker",
            name="broker_no",
            field=models.PositiveIntegerField(blank=True, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="broker",
            name="tms_link",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="broker",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]
