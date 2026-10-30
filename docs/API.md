# API

Every route is under `/api/` and wired in `Backend/config/urls.py`. Requests send `Authorization: Bearer <access>` (SimpleJWT: access 30 min, refresh 7 days, rotating) unless marked **public**. Feature specs with response details: [broker accumulation](features/broker-accumulation.md), [quarterly report](features/quarterly-report.md), [news categorization](features/news-categorization.md). Auth design: [SECURITY.md](SECURITY.md).

## Conventions

* **Auth by default.** `DEFAULT_PERMISSION_CLASSES = IsAuthenticated`; public views opt out with `AllowAny` and a throttle scope (`auth` 10/min, `public` 60/min).
* **Pagination.** DRF `PageNumberPagination`, `PAGE_SIZE = 20`, on generic list views: `{"count", "next", "previous", "results"}`. Most analysis / market views return their own JSON instead.
* **Errors.** DRF's default handler: `{"detail": "..."}` for 401 / 403 / 404 and hand-written 400s; field errors as `{"field": ["message"]}`.
* **Numbers.** Mixed, depending on how the view builds its response. Views that return dicts send `Decimal` values as JSON **numbers** (DRF's encoder calls `float()`), and some services round with `round(float(x), 4)`. Views using serializer `DecimalField`s send **strings** such as `"22000.0000"`. TODO: confirm which one the frontend should rely on (two failing tests in `test_broker_api.py` are about this).
* **Dates.** `YYYY-MM-DD` (AD). Datetimes are ISO 8601 with an offset, but which offset depends on the view: serializer `DateTimeField`s convert to Asia/Kathmandu (`+05:45`); datetimes put straight into a dict keep the value Django read from the DB (UTC, `+00:00`) unless the service converts it. Always parse the offset.
* **Scope.** Tracked-company responses carry `"scope": "tracked_companies"`. Data with no source gets `null`, plus `reason` / `action` / `warning` fields, never a made-up value.
* **Caching.** Several read views cache their response in Django's cache for 60 s (`market_views.py`, `market_indices/api/views.py`, `reports/api/views.py`); broker accumulation for `BROKER_ACCUMULATION_CACHE_SECONDS` (1 h). The key includes the user's company scope.

## Examples

**Log in**: `POST /api/users/login/` (throttled 10/min). The login field is `username` (the `User` model keeps Django's default `USERNAME_FIELD`; email is unique but not used to log in).

```http
POST /api/users/login/
Content-Type: application/json

{"username": "analyst", "password": "..."}
```
```json
{
  "refresh": "eyJ...",
  "access": "eyJ...",
  "user": {"id": 3, "username": "analyst", "email": "analyst@example.com", "first_name": "", "last_name": "",
           "role": "analyst", "custom_role": null, "is_active": true}
}
```

**Refresh**: `POST /api/users/token/refresh/` with `{"refresh": "..."}` → `{"access": "...", "refresh": "..."}`. The old refresh token is blacklisted (`ROTATE_REFRESH_TOKENS` + `BLACKLIST_AFTER_ROTATION`), so store the new one (`frontend/src/api/client.ts` does).

**Register**: `POST /api/users/register/` → `201 {"message": "Registration successful.", "user": {...}}`. Always creates a Viewer.

**Effective permissions**: `GET /api/users/me/permissions/`

```json
{"permissions": ["view_analysis", "view_market_data", "view_news"], "role": "analyst",
 "custom_role_id": null, "custom_role_name": null, "effective_role": "analyst"}
```

Company access is not in this response; admins read it at `admin/users/<id>/company-access/`.

**Movers**: `GET /api/market/movers/?period=1D&limit=5` (`view_market_data`; periods in `movers.PERIODS`: `1D`, `2S`, `3S`, `5S`, `7S`, `20S` …, aliases `1W`, `1M`)

```json
{
  "scope": "tracked_companies", "units": {"price": "NPR", "change": "NPR", "...": "..."},
  "as_of": "2026-10-29", "period": "1D", "period_label": "Today", "base_date": "2026-10-28",
  "gainers": [{"company_id": 4, "symbol": "NABIL", "name": "...", "sector": "...", "bucket": "gainer",
               "close": 512.0, "prev_close": 505.0, "change": 7.0, "change_pct": 1.386139,
               "change_basis": "...", "possible_corporate_action": false,
               "volume": 120345, "turnover": 61234567.8, "transactions": 812, "price_source": "crawled",
               "sparkline": [...]}],
  "losers": [...], "unchanged": [...], "excluded": [...],
  "tracked_count": 20, "gainers_count": 9, "losers_count": 8, "unchanged_count": 1,
  "not_traded_count": 1, "missing_price_count": 1,
  "excluded_counts": {"missing_price": 1, "not_traded": 1, "missing_previous_session": 0,
                      "prev_close_zero": 0, "possible_corporate_action": 0},
  "provenance": {"table": "market_data_dailyprice", "price_source": "crawled", "...": "..."},
  "warning": "...only when part of the session is missing...",
  "note": "..."
}
```

Field names are from `ROW_FIELDS` and `tracked_movers()` in `market_data/services/movers.py`; the values here are illustrative. With no crawled session, `as_of` is `null` and `reason` / `action` explain how to back-fill.

**Errors**

```json
// 400: GET /api/market/movers/?period=9X
{"detail": "period must be one of 1D, 2S, 3S, 5S, 7S, 20S, ... (aliases 1W, 1M)."}
// 401: missing or expired access token
{"detail": "Given token not valid for any token type", "code": "token_not_valid", "messages": [...]}
// 403: missing permission key
{"detail": "You do not have permission to perform this action."}
```

## Public endpoints

`/api/market/public/snapshot/`, `/api/market/public/chart/` (landing page movers / turnover and the NEPSE chart) and `/api/news/public/latest/` need no login. `test_no_unauthenticated_price_endpoint` says prices must not be public, so that test fails. TODO: confirm whether these endpoints stay.

## How access is checked

Two layers, both on the backend:

1. **App permission.** The view sets `permission_key = "<key>"` and uses `HasAppPermission`. Views whose permission depends on the method use `HasViewMethodPermissions` + `get_required_permissions(request)` (e.g. GET needs `view_watchlist`, POST `add_watchlist`, DELETE `remove_watchlist`). The keys and their groups are in `apps/users/api/serializers.py` → `ROLE_PERMISSIONS`. Within a group, each key implies the earlier ones are needed.
2. **Company access.** Admins see every company. Every other user sees only the companies granted in `UserCompanyAccess` (none granted = none visible). Helpers in `apps/users/company_access.py`: `filter_company_queryset()`, `require_company_access()`, `get_accessible_company_ids()` (`None` = unrestricted admin, `[]` = nothing). They apply to company lists, prices, floorsheet, analysis, market intelligence, dashboards, crawl runs, watchlists and exports. **Not** narrowed: reading news, dividends, the quarterly report, the market-wide indices, and public-issue (IPO) events on the market calendar (its dividend events are narrowed). Manual news correction needs `correct_categories` **and** access to that company.

When adding an endpoint: choose a `permission_key`, apply a company-access helper if it returns per-company data, and add the matching frontend rule in `config/routePermissions.ts`.

## Endpoints

Permission = the key for GET. Write methods may need more, so check the view.

### `users/`
| Endpoint | Permission |
|---|---|
| `login/`, `register/` | public (throttled 10/min) |
| `token/refresh/` | public (needs a valid refresh token; not throttled) |
| `me/` (GET, PATCH own profile), `me/permissions/` | authenticated |
| `admin/users/`, `admin/users/<id>/` (also at `/api/admin/users/`) | `view_users` / `create_users` / `edit_users` … |
| `admin/users/<id>/company-access/` | `edit_users` |
| `admin/analysts/` | `view_users` |
| `admin/roles/`, `admin/roles/<key>/`, `admin/roles/statistics/`, `admin/role-permissions/` | `view_roles` |
| `admin/custom-roles/`, `admin/custom-roles/<id>/` | roles group |

### `companies/`
| Endpoint | Permission |
|---|---|
| `` (list / create), `<id>/` | `view_companies` / `create_companies` / `edit_companies` / `delete_companies` |
| `<id>/toggle-track/` | `manage_tracked_companies` |
| `<id>/prices/`, `<id>/intraday/` | `view_price_history` |
| `<id>/floorsheet/` | `view_market_data` |
| `<symbol>/volume-anomalies/`, `<symbol>/rvol/` | `view_trading_volume` |
| `<id>/behavior/`, `<id>/behavior-summary/`, `<symbol>/news-correlation/`, `<id>/news-correlation/`, `<id>/news-price-correlation/` | `view_analysis` |
| `sectors/` | `view_companies` |
| `top-gainers/`, `top-losers/` | `view_market_data` (uses `movers.py`) |

### `market/` (tracked dashboard, plus dividends and quarterly report from `reports`)
Every tracked response carries `"scope": "tracked_companies"`.

| Endpoint | Permission |
|---|---|
| `public/snapshot/`, `public/chart/` | **public** (throttled 60/min) |
| `summary/`, `overview/`, `overview/chart/`, `overview/technical/`, `movers/?period=1D`, `movers/live/`, `heatmap/`, `top-gainers/`, `top-activity/`, `top-turnover/`, `top-volume/`, `top-transactions/`, `basket-index/` | `view_market_data` |
| `brokers/<symbol>/`, `signals/<symbol>/` | `view_analysis` |
| `watchlist/`, `watchlist/<symbol>/` (default list), `watchlists/`, `watchlists/<id>/`, `watchlists/<id>/items/`, `watchlists/<id>/items/<item_id>/` | watchlist group |
| `news/<symbol>/` | `view_news` (restricted to that company) |
| `dividends/` | `view_market_data` (whole market) |
| `quarterly-report/`, `quarterly-report/periods/` | `view_market_data` |

### `market-data/`
| Endpoint | Permission |
|---|---|
| `` (raw price list) | `view_price_history` |
| `floorsheet/` | `view_trading_volume` |

### `floorsheet/` and `stocks/`
| Endpoint | Permission |
|---|---|
| `floorsheet/` (filters `symbol`, `company_id`, `date_from`, `date_to`), `floorsheet/summary/` | `view_trading_volume` |
| `stocks/<symbol>/intraday/?interval=5m&date=` | `view_price_history` |

### `analysis/`
All `view_analysis` except `dashboard-summary/` (`view_market_data`) and `floorsheet-grid/` (`view_trading_volume` + company access; `?date=&minutes=1|5|10|15|30|45`, Floor Sheet Summary grid with its validation checks).

`daily/`, `cross-company/`, `dashboard-summary/`, `brokers/`, `brokers/top/`, `brokers/list/`, `brokers/<broker_id>/`, `broker-summary/`, `broker-signal/`, `broker-flow/`, `acc-dist/`, `broker-position/` (`?symbol=&broker=&range=1D|2D|1W|2W|1M|3M|6M|1Y`, + company access), `broker-activity/` (`?symbols=` up to 8, same ranges, + company access), `companies/<id>/behaviorsummary/`, `companies/<id>/brokers/`, `companies/<id>/news-pricecorrelation/`, `companies/<id>/categorized-news/`

### `market-intelligence/`
| Endpoint | Permission |
|---|---|
| `breadth/`, `heatmap/`, `rankings/`, `sectors/rotation/` | `view_market_data` |
| `relative-strength/`, `companies/<id>/technicals/`, `companies/<id>/support-resistance/`, `companies/<id>/indicators/`, `indicators/registry/` | `view_analysis` |

### `market-indices/` (whole market)
| Endpoint | Permission |
|---|---|
| `indices/`, `sub-indices/`, `analysis/`, `top/`, `tracked-sectors/`, `history/`, `verify/`, `intraday/` | `view_market_data` |
| `support-resistance/`, `indicators/?code=&specs=` (same query and response as `companies/<id>/indicators/`; benchmark and floorsheet indicators return a per-indicator error) | `view_analysis` |

### `market-calendar/`
Bikram Sambat month calendar (`market_calendar/services/calendar.py`). The NEPSE index figures are whole-market; dividend events (book closure, bonus listing, cash distribution, announcement) cover **tracked companies only, narrowed by company access**. Public-issue events (`ipo_open` / `ipo_close`: IPO, FPO, right share, mutual fund, debenture, from `IpoIssue`) are whole-market and not narrowed, since the issuer is usually not listed or tracked yet. `data_notes` contains `ipo_not_crawled` until `IpoIssue` has rows.

| Endpoint | Permission |
|---|---|
| `month/?bs_year=2083&bs_month=7` (both or neither; default today's BS month) | `view_market_data` |
| `day/?date=YYYY-MM-DD` (default today): full index row and event detail. `&include=market` adds that session's summary, top 5 gainers / losers / volume / transactions (tracked companies, narrowed by company access; `market_calendar/services/market_day.py` reuses `movers.py`) and top 5 brokers by turnover (only with `view_analysis`). `market.available` is false when no prices were crawled for that exact day: it never falls back to the previous session. | `view_market_data` |
| `weekdays/?weeks=4\|6\|13\|26&scope=` (4W, 6W, 3M, 6M; default 6): average move by weekday over the last N traded weeks, each week's days and move, and findings (`market_calendar/services/weekday_summary.py`). Tracked companies only. `scope`: `tracked` (default) or `tracked:<sector>`, an equal-weighted basket of the tracked companies **narrowed by company access** (400 when none); a day = average of the companies' `movers.py` session change, a week = the daily averages compounded. `scopes` lists the choices for this user. Weeks with no session are skipped and listed in `closed_weeks`; the window never crosses a trading-week change. | `view_market_data` |
| `months/?index=NEPSE&calendar=bs\|ad&months=6\|12\|24` (defaults NEPSE, bs, 12): "NEPSE day by day", one row per BS or AD month (newest first, never before the index's first stored session), one tile per day with that index's `source_change_pct` (falls back to the previous stored close), plus month change (last close vs the last close before the month; `partial` while running or when history starts inside it), this year's best / worst month, the strongest weekday (≥ 2 sessions) and the up-day share (`market_calendar/services/month_summary.py`). `index` = NEPSE or any sub-index code; `indices` lists them. Whole market, no company scope. | `view_market_data` |
| `monthly/?index=NEPSE` (default NEPSE): "NEPSE month by month", one row per BS year (newest first, down to the year the index history starts in), one tile per BS month = its last close against the last close before the month (`null` when the month had no session, has no earlier close, is in the future or before the history), each year's return = its last close against the last close before it (compounded from closes, never summed), `partial` on the running month / year and the month / year the history starts in, an `avg_row` per month and the sidebar stats (best / worst year, strongest month on average, months that closed up). AVG and the counts skip blanks (never 0); the running month counts with its return so far. Derived from `IndexDaily`; cached per index until a new close is stored (`market_calendar/services/monthly_returns.py`). Whole market, no company scope. | `view_market_data` |

Each day has a `status`: `traded`, `holiday`, `weekend` (from the trading week in force on that date), `pending` (today, before the close is stored), `no_data` (before the first stored index session), `no_session` (a trading weekday with no stored session and no `TradingHoliday` entry) or `future` (no index figures; holidays and events still shown). A stored session wins over a holiday entry, and the holiday name is kept.

### `news/`
| Endpoint | Permission |
|---|---|
| `` (filters `company_id`, `sentiment`, `source`, `search`, `confidence_min/max`, `needs_review`), `<id>/`, `stats/` | `view_news` |
| `public/latest/` | **public** |
| `<id>/recategorize/`, `corrections/` | `correct_categories` (+ company access to change a tag) |
| `<id>/trigger-categorize/` | `categorize_news` |

### `crawler-runs/` (also at `admin/crawl-runs/`)
| Endpoint | Permission |
|---|---|
| `` (list / POST trigger), `<id>/` | `view_crawl_runs` / `run_crawler` |
| `<id>/cancel/` | `run_crawler` |
| `<id>/retry/` | `retry_failed_crawl` |

### `dashboard/` (also at `reports/`)
| Endpoint | Permission |
|---|---|
| `summary/`, `admin/`, `analyst/`, `viewer/` | role-dependent, see `dashboard/api/views.py` |
| `export/companies/` | `view_reports` |
| `export/news/`, `export/trading/`, `export/brokers/`, `export/floorsheet/`, `export/report/` (CSV / XLSX / PDF) | `export_reports` + company access |
