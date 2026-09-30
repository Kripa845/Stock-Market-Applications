from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("market_data", "0005_floorsheettransaction_traded_at"),
    ]

    operations = [
        migrations.RenameField(
            model_name="floorsheettransaction",
            old_name="traded_at",
            new_name="trade_time",
        ),
    ]
