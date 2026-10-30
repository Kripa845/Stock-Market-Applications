# Security

How authentication, authorisation, secrets and credentials are actually handled, plus the known gaps. The app is a personal tool that is **not deployed** ([DEPLOYMENT.md](DEPLOYMENT.md)); several gaps below only matter if that changes.

## Authentication

* **JWT via SimpleJWT** (`REST_FRAMEWORK.DEFAULT_AUTHENTICATION_CLASSES`). Login: `POST /api/users/login/` with `username` + `password` (`CustomTokenObtainPairView`), which returns `access`, `refresh` and a `user` object.
* **Lifetimes** (`SIMPLE_JWT` in `config/settings.py`): access 30 min, refresh 7 days, `ROTATE_REFRESH_TOKENS = True`, `BLACKLIST_AFTER_ROTATION = True` (`rest_framework_simplejwt.token_blacklist` is installed). Each refresh returns a new refresh token and kills the old one.
* **Logout is client-side only.** `AuthContext.logout()` clears `localStorage`; there is no logout endpoint, so the current refresh token stays valid until it expires or is rotated.
* **Throttling**: login and register use `ScopedRateThrottle` scope `auth` (`AUTH_THROTTLE_RATE`, 10/min per client). Public endpoints use scope `public` (60/min). Tests raise both (`settings_test.py`).
* **Registration** (`POST /api/users/register/`) is open, always creates a **Viewer**, and runs `AUTH_PASSWORD_VALIDATORS` (`MinimumLengthValidator`, `CommonPasswordValidator`).
* **Passwords** use Django's default hasher (PBKDF2-SHA256).
* **Django admin** at `/admin/` uses Django session login, separate from the JWT API.

### Frontend token handling

`frontend/src/api/client.ts`:

* `access_token` and `refresh_token` are kept in **`localStorage`** and sent as `Authorization: Bearer …`. Any XSS on the origin could read them.
* On a 401 the client refreshes once, sharing one in-flight refresh promise between concurrent requests, stores the rotated refresh token, and retries. If refresh fails it clears storage and redirects to `/login`.
* On a 403 it fires `auth:forbidden` so `AuthContext` re-fetches permissions.

## Authorisation

Two backend layers; the frontend only mirrors them for navigation.

1. **Permission keys.** `DEFAULT_PERMISSION_CLASSES = IsAuthenticated`. Views set `permission_key` and use `HasAppPermission`, or `HasViewMethodPermissions` with `get_required_permissions(request)` for per-method keys (`apps/users/permissions.py`). **A view with no `permission_key` denies everyone** (fail closed). Keys live in `apps/users/api/serializers.py` → `ROLE_PERMISSIONS`; `User.get_app_permissions()` gives admins every key, otherwise the custom role's keys, otherwise the built-in role's `RolePermissionConfig`.
2. **Company access.** `apps/users/company_access.py`. Admins are unrestricted (`None`). Everyone else sees only companies with an active `UserCompanyAccess` row (`status=1`); **no rows means no companies**. Per-company endpoints use `filter_company_queryset()` / `require_company_access()`. Deliberate exceptions (whole-market or news data) are listed in [API.md](API.md#how-access-is-checked).

Frontend: `config/routePermissions.ts`, `PermissionRoute`, `PermissionGate`, `usePermissions`, and a permission-filtered sidebar. These hide UI only; the backend enforces.

Tests: `apps/users/tests/test_rbac_matrix.py` and `test_permission_dependencies.py` cover the matrix; see [TESTING.md](TESTING.md).

### Public (unauthenticated) endpoints

| Endpoint | Throttle |
|---|---|
| `POST /api/users/login/`, `register/` | `auth` |
| `POST /api/users/token/refresh/` | none (plain SimpleJWT `TokenRefreshView`; needs a valid refresh token) |
| `GET /api/market/public/snapshot/`, `public/chart/` | `public` |
| `GET /api/news/public/latest/` | `public` |

`test_no_unauthenticated_price_endpoint` expects no public price endpoint and currently fails. TODO: confirm whether the public market endpoints stay.

## Secrets and configuration

* All secrets come from environment variables read in `config/settings.py` (`os.getenv`), loaded from `.env` at the repo root (template `.env.example`; `.env` is gitignored). Full list: [DEPLOYMENT.md](DEPLOYMENT.md#environment-variables).
* **Data sources need no keys.** No credentials for any source are configured; the NEPSE client (`nepse-data-api`) authenticates on construction without any configured secret (TODO: confirm how the library obtains its token).
* Celery uses JSON serialisation only (`CELERY_ACCEPT_CONTENT = ["json"]`), so no pickle payloads.
* CORS: an allow-list (`FRONTEND_URL` plus localhost :5173 / :5174 / :3000), `CORS_ALLOW_CREDENTIALS = True`; `CORS_ALLOW_ALL_ORIGINS` defaults to `False`.
* Middleware includes `SecurityMiddleware`, `CsrfViewMiddleware` and `XFrameOptionsMiddleware`. No `SECURE_*` / HSTS / secure-cookie settings are configured (fine on localhost; needed behind HTTPS).

## Known issues

| Issue | Where | Risk / suggested fix |
|---|---|---|
| Hardcoded admin credentials `admin1` / `Admin@123`, printed to the console; re-running resets the password | `apps/companies/management/commands/seed_admin.py` | Anyone who knows the default can log in until it is changed. Read them from env or prompt. |
| Old superuser password hash and an (expired) session committed to git | `Backend/data/backups/data.json` (commit `7ca19b5`) | Hash is crackable offline if the repo is shared. Remove the file; if that password is reused anywhere, change it. Removing it from history needs a rewrite. |
| Insecure `SECRET_KEY` fallback | `config/settings.py` | The app starts with `django-insecure-change-me-in-production` when unset. Fail at startup when `DEBUG` is off instead. |
| JWT in `localStorage`, no server-side logout | `frontend/src/api/client.ts`, `AuthContext.tsx` | XSS could steal tokens; a stolen refresh token lives up to 7 days. |
| Compose runs `runserver` with source mounted | `docker-compose.yml` | Development only; don't expose it. |
| Placeholder email `admin@.com` | `seed_admin.py` | Invalid address; cosmetic. |
| Naive `datetime.now()` in export headers | `apps/reports/exports/` | Not a security issue; noted for audit timestamps. |

## Rules

* Never hardcode or log keys, passwords or tokens; read them from env.
* Never commit `.env`, database dumps or fixtures that contain users.
* Every new endpoint: a `permission_key`, a company-access helper when it returns per-company data, and the matching frontend rule.
