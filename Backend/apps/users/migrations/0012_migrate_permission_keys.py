"""
Backend/apps/users/migrations/0012_migrate_permission_keys.py   (NEW FILE)

Rename to the next number in your migrations folder and set `dependencies` to your
latest existing users migration. Run: python manage.py makemigrations users --check
first to make sure no schema migration is pending.

What it does
  Rewrites the JSON permission lists on RolePermissionConfig (analyst/viewer) and
  CustomRole, replacing the 4 retired keys with the new page-level keys, so no
  existing role silently loses access when the old keys stop being valid.

EDIT OLD_TO_NEW if my guesses do not match what each old key really protected.
"""
from django.db import migrations

# Imported from the live catalogue. Fine for this migration; if you later change the
# catalogue and re-run on a fresh DB, results follow the catalogue of that time.
from apps.users.permission_catalog import normalize_permissions

MARKET_PAGES = [
    "view_dashboard",
    "view_top_gainer", "view_top_losers", "view_top_turnover", "view_top_volume", "view_top_transactions",
    "view_indices",
    "view_dividends", "view_calendar",
    "view_nepse_day_by_day", "view_nepse_month_by_month", "view_weekday_summary", "view_floorsheet_summary",
    "view_latest_reports", "view_stock_details", "view_live_trading",
]
BROKER_PAGES = [
    "view_top_broker", "view_broker_explorer", "view_broker_list",
    "view_broker_accumulation", "view_broker_acc_dist_chart",
]
CHART_PERMS = ["view_charts", "use_indicators", "save_layouts"]

OLD_TO_NEW = {
    # old key           -> new keys it becomes
    "view_market_data": MARKET_PAGES,
    "view_trading_volume": ["view_floorsheet"] + BROKER_PAGES,   # /floorsheet used this key
    "view_price_history": CHART_PERMS,
    "view_analysis": CHART_PERMS + BROKER_PAGES + ["view_stock_comparison", "view_watchlist_comparison"],
    # keys that stay but now also cover the new sibling pages
    "view_news": ["view_news", "view_announcements"],
    "view_reports": ["view_reports", "view_financial_reports"],
    "export_reports": ["export_reports", "export_financial_reports"],
}


def forwards(apps, schema_editor):
    RolePermissionConfig = apps.get_model("users", "RolePermissionConfig")
    CustomRole = apps.get_model("users", "CustomRole")

    for model in (RolePermissionConfig, CustomRole):
        for obj in model.objects.all():
            new_keys = set()
            for key in obj.permissions or []:
                new_keys.update(OLD_TO_NEW.get(key, [key]))
            obj.permissions = normalize_permissions(new_keys)
            obj.save(update_fields=["permissions"])


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0011_named_watchlists"),   # <-- CHANGE THIS
    ]
    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),  # lossy, so no reverse
    ]