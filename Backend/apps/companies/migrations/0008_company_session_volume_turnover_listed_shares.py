from django.db import migrations, models


def copy_listed_shares(apps, schema_editor):
    """Start from the share counts index replication already fetched from NEPSE (latest row per symbol)."""
    Company = apps.get_model("companies", "Company")
    CompanyDaily = apps.get_model("market_indices", "CompanyDaily")
    for company in Company.objects.filter(listed_shares__isnull=True):
        row = CompanyDaily.objects.filter(symbol__iexact=company.symbol).order_by("-date").first()
        if row:
            company.listed_shares = row.listed_shares
            company.save(update_fields=["listed_shares"])


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0007_company_ltp_company_previous_close_and_more'),
        ('market_indices', '0004_index_replication'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='session_volume',
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='company',
            name='session_turnover',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=18, null=True),
        ),
        migrations.AddField(
            model_name='company',
            name='listed_shares',
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.RunPython(copy_listed_shares, migrations.RunPython.noop),
    ]
