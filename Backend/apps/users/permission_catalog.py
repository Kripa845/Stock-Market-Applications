"""
Backend/apps/users/permission_catalog.py   (NEW FILE)

Single source of truth for the permission catalogue: one group per sidebar page,
in sidebar order. apps/users/api/serializers.py should import from here instead
of defining ROLE_PERMISSIONS / VALID_PERMISSION_KEYS / _build_dependencies itself.

Dependency rules
  * Group with a "base" key (usually the View key): every other key in the group
    requires that base key.
  * Group with base = None (Market Overview, Summary, Broker Analysis): the view keys
    are independent sub-pages. Actions such as export use "requires_any", meaning
    "at least one of these view keys".
  * Groups never depend on each other.
"""
from __future__ import annotations

BROKER_VIEWS = [
    "view_top_broker",
    "view_broker_explorer",
    "view_broker_list",
    "view_broker_accumulation",
    "view_broker_acc_dist_chart",
]

# Order here = order of the cards on the Roles & Permissions page = sidebar order.
PERMISSION_GROUPS: list[dict] = [
    {"key": "dashboard", "label": "Dashboard", "base": "view_dashboard",
     "permissions": [("view_dashboard", "View Dashboard")]},

    {"key": "market_overview", "label": "Market Overview", "base": None,
     "permissions": [
         ("view_top_gainer", "View Top Gainer"),
         ("view_top_losers", "View Top Losers"),
         ("view_top_turnover", "View Top Turnover"),
         ("view_top_volume", "View Top Volume"),
         ("view_top_transactions", "View Top Transactions"),
     ]},

    {"key": "indices", "label": "Indices", "base": "view_indices",
     "permissions": [("view_indices", "View Indices")]},

    {"key": "dividends", "label": "Proposed Dividend", "base": "view_dividends",
     "permissions": [
         ("view_dividends", "View Dividends"),
         ("export_dividends", "Export Dividends"),
     ]},

    {"key": "calendar", "label": "Market Calendar", "base": "view_calendar",
     "permissions": [
         ("view_calendar", "View Calendar"),
         ("create_events", "Create Events"),
         ("edit_events", "Edit Events"),
         ("delete_events", "Delete Events"),
     ]},

    {"key": "summary", "label": "Summary", "base": None,
     "permissions": [
         ("view_nepse_day_by_day", "View NEPSE Day by Day"),
         ("view_nepse_month_by_month", "View NEPSE Month by Month"),
         ("view_weekday_summary", "View Weekday Summary"),
         ("view_floorsheet_summary", "View Floorsheet Summary"),
     ]},

    {"key": "latest_reports", "label": "Latest Report", "base": "view_latest_reports",
     "permissions": [("view_latest_reports", "View Latest Reports")]},

    {"key": "companies", "label": "Companies", "base": "view_companies",
     "permissions": [
         ("view_companies", "View Companies"),
         ("create_companies", "Create Companies"),
         ("edit_companies", "Edit Companies"),
         ("delete_companies", "Delete Companies"),
         ("manage_tracked_companies", "Manage Tracked Companies"),
     ]},

    {"key": "charts", "label": "Technical Charts", "base": "view_charts",
     "permissions": [
         ("view_charts", "View Charts"),
         ("use_indicators", "Use Indicators"),
         ("save_layouts", "Save Layouts"),
     ]},

    {"key": "floorsheet", "label": "Floorsheet", "base": "view_floorsheet",
     "permissions": [
         ("view_floorsheet", "View Floorsheet"),
         ("export_floorsheet", "Export Floorsheet"),
     ]},

    {"key": "broker_analysis", "label": "Broker Analysis", "base": None,
     "permissions": [
         ("view_top_broker", "View Top Broker"),
         ("view_broker_explorer", "View Broker Explorer"),
         ("view_broker_list", "View Broker List"),
         ("view_broker_accumulation", "View Broker Accumulation"),
         ("view_broker_acc_dist_chart", "View Broker Acc/Dist Chart"),
         ("export_broker_analysis", "Export Broker Analysis"),
     ],
     "requires_any": {"export_broker_analysis": BROKER_VIEWS}},

    {"key": "watchlist", "label": "Watchlist", "base": "view_watchlist",
     "permissions": [
         ("view_watchlist", "View Watchlist"),
         ("add_watchlist", "Add Companies"),
         ("remove_watchlist", "Remove Companies"),
     ]},

    {"key": "live_trading", "label": "Live Trading", "base": "view_live_trading",
     "permissions": [("view_live_trading", "View Live Trading")]},

    {"key": "stock_comparison", "label": "Stock Comparison", "base": "view_stock_comparison",
     "permissions": [
         ("view_stock_comparison", "View Stock Comparison"),
         ("export_stock_comparison", "Export Stock Comparison"),
     ]},

    {"key": "watchlist_comparison", "label": "Watchlist Comparison", "base": "view_watchlist_comparison",
     "permissions": [
         ("view_watchlist_comparison", "View Watchlist Comparison"),
         ("export_watchlist_comparison", "Export Watchlist Comparison"),
     ]},

    {"key": "news", "label": "News Feed", "base": "view_news",
     "permissions": [
         ("view_news", "View News"),
         ("categorize_news", "Categorize News"),
         ("correct_categories", "Correct Categories"),
     ]},

    {"key": "announcements", "label": "Announcements", "base": "view_announcements",
     "permissions": [
         ("view_announcements", "View Announcements"),
         ("create_announcements", "Create Announcements"),
         ("edit_announcements", "Edit Announcements"),
         ("delete_announcements", "Delete Announcements"),
     ]},

    {"key": "stock_details", "label": "Stock Details", "base": "view_stock_details",
     "permissions": [("view_stock_details", "View Stock Details")]},

    {"key": "crawler", "label": "Crawl Management", "base": "view_crawl_runs",
     "permissions": [
         ("view_crawl_runs", "View Crawl Runs"),
         ("run_crawler", "Run Crawler"),
         ("view_crawl_logs", "View Crawl Logs"),
         ("retry_failed_crawl", "Retry Failed Crawl"),
     ]},

    {"key": "financial_reports", "label": "Financial Reports", "base": "view_financial_reports",
     "permissions": [
         ("view_financial_reports", "View Financial Reports"),
         ("export_financial_reports", "Export Financial Reports"),
         ("upload_financial_reports", "Upload Financial Reports"),
     ]},

    {"key": "reports", "label": "Reports", "base": "view_reports",
     "permissions": [
         ("view_reports", "View Reports"),
         ("export_reports", "Export Reports"),
     ]},

    {"key": "users", "label": "User Management", "base": "view_users",
     "permissions": [
         ("view_users", "View Users"),
         ("create_users", "Create Users"),
         ("edit_users", "Edit Users"),
         ("delete_users", "Delete Users"),
         ("change_user_roles", "Change User Roles"),
         ("activate_users", "Activate / Deactivate Users"),
     ]},

    {"key": "roles_permissions", "label": "Roles & Permissions", "base": "view_roles",
     "permissions": [
         ("view_roles", "View Roles"),
         ("create_roles", "Create Roles"),
         ("edit_roles", "Edit Roles"),
         ("delete_roles", "Delete Roles"),
         ("assign_roles", "Assign Roles"),
     ]},
]

# ---- Derived structures (same names your code already imports) -------------------
# Same shape as your old ROLE_PERMISSIONS: {group_key: [{"key":..., "name":...}, ...]}
ROLE_PERMISSIONS: dict[str, list[dict]] = {
    g["key"]: [{"key": k, "name": n} for k, n in g["permissions"]] for g in PERMISSION_GROUPS
}
ALL_PERMISSION_KEYS: list[str] = [k for g in PERMISSION_GROUPS for k, _ in g["permissions"]]
VALID_PERMISSION_KEYS: frozenset[str] = frozenset(ALL_PERMISSION_KEYS)
PERMISSION_LABELS: dict[str, str] = {k: label for g in PERMISSION_GROUPS for k, label in g["permissions"]}
GROUP_LABELS: dict[str, str] = {g["key"]: g["label"] for g in PERMISSION_GROUPS}


def _build_rules() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    deps: dict[str, list[str]] = {}
    any_of: dict[str, list[str]] = {}
    for g in PERMISSION_GROUPS:
        base = g["base"]
        if base:
            for key, _ in g["permissions"]:
                if key != base:
                    deps[key] = [base]
        any_of.update(g.get("requires_any", {}))
    return deps, any_of


# key -> [keys that must ALL be granted]
# key -> [keys of which AT LEAST ONE must be granted]
PERMISSION_DEPENDENCIES, PERMISSION_REQUIRES_ANY = _build_rules()


def normalize_permissions(keys) -> list[str]:
    """
    Drop unknown keys and add whatever the selected keys require
    (e.g. edit_users -> view_users; export_broker_analysis -> first Broker view if none picked).
    Returned in catalogue order.
    """
    result = {k for k in keys if k in VALID_PERMISSION_KEYS}
    changed = True
    while changed:
        changed = False
        for key in list(result):
            for dep in PERMISSION_DEPENDENCIES.get(key, []):
                if dep not in result:
                    result.add(dep)
                    changed = True
            options = PERMISSION_REQUIRES_ANY.get(key)
            if options and not result.intersection(options):
                result.add(options[0])
                changed = True
    return [k for k in ALL_PERMISSION_KEYS if k in result]


def validate_permission_dependencies(permissions) -> list[str]:
    """
    Drop-in replacement for the function of the same name in serializers.py.
    Returns human-readable errors; an empty list means the combination is valid.
    Supports both "requires ALL of" (dependencies) and "requires AT LEAST ONE of" rules.
    """
    perm_set = set(permissions)
    errors: list[str] = []
    for key in permissions:
        missing = [d for d in PERMISSION_DEPENDENCIES.get(key, []) if d not in perm_set]
        if missing:
            errors.append(
                f"{PERMISSION_LABELS.get(key, key)} requires: "
                f"{', '.join(PERMISSION_LABELS.get(m, m) for m in missing)}."
            )
        options = PERMISSION_REQUIRES_ANY.get(key)
        if options and not perm_set.intersection(options):
            errors.append(
                f"{PERMISSION_LABELS.get(key, key)} requires at least one of: "
                f"{', '.join(PERMISSION_LABELS.get(o, o) for o in options)}."
            )
    return errors


def definitions_payload() -> dict:
    """Response body for GET /api/users/admin/role-permissions/ (feeds the Roles page)."""
    return {
        "groups": [
            {
                "key": g["key"],
                "name": g["label"],  # "name", to match your existing API/frontend
                "permissions": [{"key": k, "name": n} for k, n in g["permissions"]],
            }
            for g in PERMISSION_GROUPS
        ],
        "dependencies": PERMISSION_DEPENDENCIES,
        "requires_any": PERMISSION_REQUIRES_ANY,
    }