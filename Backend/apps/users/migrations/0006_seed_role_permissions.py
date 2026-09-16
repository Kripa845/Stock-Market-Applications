from django.db import migrations


def seed_default_permissions(apps, schema_editor):
    """
    Seed default RolePermissionConfig entries for
    Analyst and Viewer.
    """
    RolePermissionConfig = apps.get_model(
        "users",
        "RolePermissionConfig",
    )

    analyst_permissions = [
        "view_users",
        "view_companies",
        "view_market_data",
        "view_price_history",
        "view_trading_volume",
        "view_vwap",
        "view_buy_sell_pressure",
        "view_news",
        "categorize_news",
        "correct_categories",
        "view_watchlist",
        "view_crawl_runs",
        "view_crawl_logs",
        "view_analysis",
        "view_price_trends",
        "view_volume_trends",
        "view_vwap_analysis",
        "view_pressure_analysis",
        "view_reports",
        "generate_reports",
        "export_reports",
    ]

    RolePermissionConfig.objects.update_or_create(
        role_key="analyst",
        defaults={
            "name": "Analyst",
            "description": (
                "Market analysis, news review, "
                "and report generation access."
            ),
            "permissions": analyst_permissions,
            "is_active": True,
        },
    )

    viewer_permissions = [
        "view_companies",
        "view_market_data",
        "view_price_history",
        "view_trading_volume",
        "view_vwap",
        "view_buy_sell_pressure",
        "view_news",
        "view_watchlist",
        "view_analysis",
        "view_price_trends",
        "view_volume_trends",
        "view_vwap_analysis",
        "view_pressure_analysis",
        "view_reports",
    ]

    RolePermissionConfig.objects.update_or_create(
        role_key="viewer",
        defaults={
            "name": "Viewer",
            "description": (
                "Read-only access to market information."
            ),
            "permissions": viewer_permissions,
            "is_active": True,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        (
            "users",
            "0005_rolepermissionconfig",
        ),
    ]

    operations = [
        migrations.RunPython(
            seed_default_permissions,
            migrations.RunPython.noop,
        ),
    ]