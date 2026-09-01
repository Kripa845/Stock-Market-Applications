# NEPSE Watch — Frontend

React + Vite + TypeScript dashboard for the Omway Technologies "Stock Market Application"
assignment. Built against the Django backend in `Backend/` (from
`Stock-Market-Application-crawling-2.zip`).

All types in `src/types/index.ts` are modeled directly on the DRF serializers in
`Backend/apps/*/serializers.py` (or, for the three routes that aren't wired up yet, on the
model fields + the assignment spec — see below).

## Two backend fixes needed before this will connect

I read through the backend while building this. Two small things need fixing in
`Backend/config/settings.py` and `Backend/apps/companies/urls.py` or the frontend
cannot talk to the API at all — everything else below assumes these are applied.

### 1. CORS middleware is missing (blocks every request from the browser)

`settings.py` has `corsheaders` in `INSTALLED_APPS` and sets `CORS_ALLOWED_ORIGINS`,
but `corsheaders.middleware.CorsMiddleware` is never added to `MIDDLEWARE`, so no
CORS headers are actually sent. The browser will block every request from
`localhost:5173`. Add it as the **first** entry:

```python
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",       # add this line
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    ...
]
```

### 2. Companies list URL is double-prefixed

`config/urls.py` mounts the companies app at `api/companies/`, but
`apps/companies/urls.py` *also* prefixes the list route with `api/companies/`,
so the real path today is `/api/companies/api/companies/` instead of
`/api/companies/`. Fix the list route in `Backend/apps/companies/urls.py`:

```python
urlpatterns = [
    path("", CompanyListAPIView.as_view()),          # was "api/companies/"
    path("<int:pk>/", CompanyDetailView.as_view(), name="company-detail"),
]
```

This frontend is written against the corrected `/api/companies/` path.

## What's wired up vs. stubbed

The backend snapshot in the zip implements: auth (`register` / `login` /
`token/refresh` / `me`), companies (list/detail), daily prices, and floorsheet.
It does **not** yet implement the `news`, `analysis`, or admin `crawl-runs`
endpoints described in the assignment's Section 7 — `apps/news/urls.py` and
`apps/analysis/urls.py` are empty `urlpatterns` lists, and `apps/crawler_runs`
has no `urls.py` at all, even though the models (`NewsArticle`,
`ArticleCompanyTag`, `DailyAnalysis`, `CrawlRun`) and services/Celery tasks
already exist.

This frontend calls those endpoints using the exact paths documented in the
assignment spec (`src/api/news.js`, `src/api/analysis.js`, `src/api/admin.js`),
and every panel that depends on them (news feed, behavior summary, admin crawl
trigger, admin user list) catches the resulting 404 and shows a clear
"not implemented yet" state instead of breaking. Once you add the views +
URLs on the backend, no frontend changes are needed — those panels populate
automatically.

Also worth knowing:
- `GET /api/market-data/` currently returns **all** `DailyPrice` rows for
  every active company, unpaginated, with no `?company_id=`/`?range=` filter.
  The frontend fetches the full set once and filters/slices client-side
  (`src/api/marketData.js`). Fine for the assignment's data volume (5–10
  companies × ~1 month), but worth adding server-side filtering later.
- The floorsheet endpoint *does* support server-side filtering
  (`?company=&date=&buyer_broker=&seller_broker=`) and is paginated.
- Role-based UI (Admin/Analyst/Viewer) is implemented in the frontend
  (`ProtectedRoute`, `RoleGate`), but today's backend views only check
  `IsAuthenticated` — none of them yet check `request.user.role`. The
  assignment explicitly requires server-side role enforcement on every
  endpoint, so that's the next thing to add on the backend side (DRF custom
  permission classes keyed off `user.role`/`user.is_admin()` etc., which
  already exist as methods on the `User` model).

## Setup

```bash
cd frontend
cp .env.example .env      # point at your backend, defaults to http://localhost:8000/api
npm install
npm run dev                # http://localhost:5173
npm run typecheck          # tsc -b --noEmit, no bundling
npm run build               # tsc -b && vite build
```

Backend (after applying the two fixes above):

```bash
cd Backend
# ...your existing venv / migrate / runserver flow
python manage.py runserver
```

Then in the app: **Register** a user (starts as `viewer`), promote yourself to
`admin` via Django admin or the shell (`user.role = "admin"; user.save()`) to
see the Admin page, log in, and browse.

## Project structure

```
src/
  types/        index.ts — shared types mirroring the backend serializers/models
  api/          one file per backend app: auth, companies, marketData, news, analysis, admin
  context/      AuthContext — JWT storage, login/register/logout, current user + role
  components/   ProtectedRoute, RoleGate, Navbar, PriceChart, FloorsheetTable, NewsFeed, BehaviorSummary
  pages/        Login, Register, Dashboard (watchlist + cross-company comparison),
                CompanyDetail (chart + behavior + news + floorsheet), Admin
```

`tsconfig.json` is a project-references root pointing at `tsconfig.app.json` (the `src/`
app, strict mode on) and `tsconfig.node.json` (just `vite.config.ts`) — the standard split
the Vite React-TS template uses, so editors and `tsc -b` both resolve correctly.

## Auth model

JWT access + refresh tokens (SimpleJWT) stored in `localStorage`. An axios
response interceptor (`src/api/client.js`) catches a 401, silently calls
`/users/token/refresh/`, retries the original request once, and only logs the
user out if the refresh itself fails.
