# Company Access backend completion

These files are intended to be copied into the existing `Backend/` project.

## Database

Run:

```powershell
python manage.py migrate
```

The new migration is `apps/users/migrations/0008_user_watchlist.py`.

The existing `0007_user_company_access.py` already creates `UserCompanyAccess`.

## Main API

Admin User Management:

- `GET /api/users/admin/users/<user_id>/company-access/`
- `POST /api/users/admin/users/<user_id>/company-access/`
- `PUT /api/users/admin/users/<user_id>/company-access/`

Body:

```json
{
  "company_access": [
    {"company_id": 1, "status": 1},
    {"company_id": 2, "status": 0}
  ]
}
```

Current-user permissions now include:

```json
"company_access": {
  "all": false,
  "company_ids": [1, 5, 8]
}
```

Watchlist:

- `GET /api/watchlist/`
- `POST /api/watchlist/` with `{ "company_id": 1 }`
- `DELETE /api/watchlist/<company_id>/`
- Equivalent `/api/users/me/watchlist/` routes are also available.

## Enforcement

The backend applies Company Access to company lists, prices, floorsheet, analysis, dashboards, crawler runs, watchlist operations, and exports. News viewing remains unrestricted because the existing project explicitly treats Company Access as a requirement for **manual categorization/correction**, not general news viewing. Manual correction still requires both `correct_categories` and access to the target company.

## Existing RBAC

Dynamic roles and permissions are not replaced. Company Access is a separate per-user restriction layered on top of the existing `has_app_permission()` checks.
