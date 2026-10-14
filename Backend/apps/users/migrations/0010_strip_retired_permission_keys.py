from django.db import migrations

# Keys removed from ROLE_PERMISSIONS because no feature enforced them, plus
# "manage_users", an older key some stored roles still carry.
RETIRED = {
    "view_vwap", "view_buy_sell_pressure",
    "edit_news", "delete_news",
    "edit_watchlist",
    "view_price_trends", "view_volume_trends", "view_vwap_analysis", "view_pressure_analysis",
    "generate_reports",
    "manage_users",
}


def strip_retired(apps, schema_editor):
    for model_name in ("CustomRole", "RolePermissionConfig"):
        for role in apps.get_model("users", model_name).objects.all():
            kept = [key for key in (role.permissions or []) if key not in RETIRED]
            if kept != (role.permissions or []):
                role.permissions = kept
                role.save(update_fields=["permissions"])


class Migration(migrations.Migration):
    dependencies = [("users", "0009_alter_usercompanyaccess_options_and_more")]

    operations = [migrations.RunPython(strip_retired, migrations.RunPython.noop)]
