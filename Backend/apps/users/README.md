# users

Users, roles, permissions and per-company access.

| Where | What |
|---|---|
| `models.py` | User, CustomRole, RolePermissionConfig, UserCompanyAccess, Watchlist, WatchlistItem |
| `api/` | /api/users/ and /api/admin/users/ |
| `permissions.py` | HasAppPermission any-of checks, method permissions, and company-access helpers |
| `api/serializers.py` | Existing permission keys, sidebar-page groups, dependency validation, and the legacy-key list |
| `migrations/0013_add_page_permissions.py` | Additive page grants for roles that still contain a broad legacy key |

Page-level grants coexist with `view_market_data`, `view_price_history`, `view_trading_volume`, and `view_analysis`. Existing views accept either the former key or the matching page key. A role that retains one of those four broad keys can still open every page mapped to it; remove that broad key to restrict access to selected pages.

The role-definition endpoint returns page groups in sidebar order, dependency maps, and a separate `legacy_groups` list. Permissions for features without backend endpoints are intentionally omitted.

Tests: `tests/`. Layout and the page map: `ARCHITECTURE.md` (repo root).
