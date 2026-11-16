"""Add page grants alongside any surviving legacy grants.

Migration 0012 already expanded and normalized many stored legacy keys. This
follow-up is deliberately additive: it keeps every existing value and only
adds page keys when an old key is still present. The lists are frozen here so
later catalogue changes cannot alter migration behavior.
"""
from django.db import migrations


LEGACY_TO_PAGE = {
    "view_market_data": [
        "view_dashboard", "view_top_gainer", "view_top_losers", "view_top_turnover",
        "view_top_volume", "view_top_transactions", "view_indices", "view_dividends",
        "view_calendar", "view_nepse_day_by_day", "view_nepse_month_by_month",
        "view_weekday_summary", "view_floorsheet_summary", "view_latest_reports",
        "view_stock_details", "view_live_trading",
    ],
    "view_price_history": ["view_charts", "use_indicators"],
    "view_trading_volume": ["view_floorsheet", "view_floorsheet_summary"],
    "view_analysis": [
        "view_top_broker", "view_broker_explorer", "view_broker_list",
        "view_broker_accumulation", "view_broker_acc_dist_chart",
        "view_stock_comparison", "view_watchlist_comparison", "view_charts",
        "use_indicators",
    ],
}


def additive_permissions(keys):
    result = list(keys or [])
    present = set(result)
    for old_key, page_keys in LEGACY_TO_PAGE.items():
        if old_key in present:
            for key in page_keys:
                if key not in present:
                    result.append(key)
                    present.add(key)
    return result


def forwards(apps, schema_editor):
    for model_name in ("RolePermissionConfig", "CustomRole"):
        Model = apps.get_model("users", model_name)
        for role in Model.objects.all().iterator():
            updated = additive_permissions(role.permissions)
            if updated != (role.permissions or []):
                role.permissions = updated
                role.save(update_fields=["permissions"])


class Migration(migrations.Migration):
    dependencies = [("users", "0012_migrate_permission_keys")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
