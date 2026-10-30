# API

Every route is under `/api/` and wired in `Backend/config/urls.py`. Requests send `Authorization: Bearer <access>` (SimpleJWT: access 30 min, refresh 7 days, rotating) unless marked **public**. Default page size is 20. Feature specs with response details: [broker accumulation](features/broker-accumulation.md), [quarterly report](features/quarterly-report.md), [news categorization](features/news-categorization.md).

## How access is checked

Two layers, both on the backend:

1. **App permission.** The view sets `permission_key = "<key>"` and uses `HasAppPermission`. Views whose permission depends on the method use `HasViewMethodPermissions` + `get_required_permissions(request)` (e.g. GET needs `view_watchlist`, POST `add_watchlist`, DELETE `remove_watchlist`). The keys and their groups are in `apps/users/api/serializers.py` → `ROLE_PERMISSIONS`. Within a group, each key implies the earlier ones are needed.
2. **Company access.** Non-admin users can be limited to some companies (`UserCompanyAccess`). Helpers in `apps/users/company_access.py`: `filter_company_queryset()`, `require_company_access()`, `get_accessible_company_ids()` (None = unrestricted). They apply to company lists, prices, floorsheet, analysis, market intelligence, dashboards, crawl runs, watchlists and exports. **Not** narrowed: reading news, dividends, the quarterly report, the market-wide indices, and public-issue (IPO) events on the market calendar (its dividend events are narrowed). Manual news correction needs `correct_categories` **and** access to that company.

When adding an endpoint: choose a `permission_key`, apply a company-access helper if it returns per-company data, and add the matching frontend rule in `config/routePermissions.ts`.

## Endpoints

Permission = the key for GET. Write methods may need more, so check the view.

### `users/`
| Endpoint | Permission |
|---|---|
| `login/`, `register/`, `token/refresh/` | public (throttled 10/min) |
| `me/`, `me/permissions/` (includes `company_access: {all, company_ids}`) | authenticated |
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
| `support-resistance/` | `view_analysis` |

### `market-calendar/`
Bikram Sambat month calendar (`market_calendar/services/calendar.py`). The NEPSE index figures are whole-market; dividend events (book closure, bonus listing, cash distribution, announcement) cover **tracked companies only, narrowed by company access**. Public-issue events (`ipo_open` / `ipo_close`: IPO, FPO, right share, mutual fund, debenture, from `IpoIssue`) are whole-market and not narrowed, since the issuer is usually not listed or tracked yet. `data_notes` contains `ipo_not_crawled` until `IpoIssue` has rows.

| Endpoint | Permission |
|---|---|
| `month/?bs_year=2083&bs_month=7` (both or neither; default today's BS month) | `view_market_data` |
| `day/?date=YYYY-MM-DD` (default today): full index row and event detail. `&include=market` adds that session's summary, top 5 gainers / losers / volume / transactions (tracked companies, narrowed by company access; `market_calendar/services/market_day.py` reuses `movers.py`) and top 5 brokers by turnover (only with `view_analysis`). `market.available` is false when no prices were crawled for that exact day: it never falls back to the previous session. | `view_market_data` |
| `weekdays/?weeks=4\|6\|13\|26&scope=` (4W, 6W, 3M, 6M; default 6): average move by weekday over the last N traded weeks, each week's days and move, and findings (`market_calendar/services/weekday_summary.py`). Tracked companies only. `scope`: `tracked` (default) or `tracked:<sector>`, an equal-weighted basket of the tracked companies **narrowed by company access** (400 when none); a day = average of the companies' `movers.py` session change, a week = the daily averages compounded. `scopes` lists the choices for this user. Weeks with no session are skipped and listed in `closed_weeks`; the window never crosses a trading-week change. | `view_market_data` |
| `months/?index=NEPSE&calendar=bs\|ad&months=6\|12\|24` (defaults NEPSE, bs, 12): "NEPSE day by day", one row per BS or AD month (newest first, never before the index's first stored session), one tile per day with that index's `source_change_pct` (falls back to the previous stored close), plus month change (last close vs the last close before the month; `partial` while running or when history starts inside it), this year's best / worst month, the strongest weekday (≥ 2 sessions) and the up-day share (`market_calendar/services/month_summary.py`). `index` = NEPSE or any sub-index code; `indices` lists them. Whole market, no company scope. | `view_market_data` |

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
