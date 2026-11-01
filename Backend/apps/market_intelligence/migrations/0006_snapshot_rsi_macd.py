from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("market_intelligence", "0005_support_resistance"),
    ]

    operations = [
        migrations.AddField(
            model_name="companytechnicalsnapshot",
            name="rsi_14",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=15, null=True),
        ),
        migrations.AddField(
            model_name="companytechnicalsnapshot",
            name="macd",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=15, null=True),
        ),
        migrations.AddField(
            model_name="companytechnicalsnapshot",
            name="macd_signal",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=15, null=True),
        ),
        migrations.AddField(
            model_name="companytechnicalsnapshot",
            name="macd_hist",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=15, null=True),
        ),
    ]
