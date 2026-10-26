# users

Users, roles, permissions and per-company access.

| Where | What |
|---|---|
| `models.py` | User, CustomRole, RolePermissionConfig, UserCompanyAccess, Watchlist, WatchlistItem |
| `api/` | /api/users/ and /api/admin/users/ |
| `permissions.py` | HasAppPermission and friends; company_access.py narrows querysets to the user's companies |

Tests: `tests/`. Layout and the page map: `Backend/docs/architecture.md`.
