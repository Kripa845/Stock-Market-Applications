# Backend architecture

Django project in `Backend/`. Every app under `apps/` has the same layout:

```
apps/<app>/
├── models.py              database tables
├── api/                   urls.py, views.py, serializers.py  (what the frontend calls)
├── services/              business logic, one file per feature
├── tasks.py               Celery jobs (scheduled in config/settings.py → CELERY_BEAT_SCHEDULE)
├── management/commands/   `python manage.py <command>`
├── tests/                 test_<feature>.py
└── README.md              what the app owns
```

## Apps

| App | Owns | Models |
|---|---|---|
| `companies` | Company list, tracked companies | Company, TrackedCompany |
| `market_data` | Daily prices, live prices, market overview, movers, heatmap, watchlists, trading calendar | DailyPrice, TradingHoliday, LiveFeedStatus |
| `floorsheet` | Floorsheet trades, broker directory, intraday candles | FloorsheetTransaction, Broker, IntradayCandle |
| `reports` | Dividends, EPS, quarterly reports, CSV / XLSX / PDF exports | DividendAnnouncement, CompanyEarnings, QuarterlyReport, YearlyDPPS |
| `market_indices` | NEPSE and sector indices, index replication | MarketIndex, IndexDaily, … |
| `market_intelligence` | Technical indicators, breadth, sector rotation, support / resistance | *Snapshot models, SupportResistance* |
| `analysis` | Broker accumulation, daily pressure, volume anomalies, news vs price | DailyAnalysis, VolumeAnomaly, NewsPriceCorrelation |
| `news` | Crawled news, categorization, sentiment | RawArticle, NewsArticle, ArticleCompanyTag |
| `crawler_runs` | Running Scrapy spiders and their history | CrawlRun |
| `dashboard` | Admin / analyst / viewer dashboard summaries | — |
| `market_calendar` | Bikram Sambat month calendar: NEPSE index per day, trading holidays, dividend events | — |
| `users` | Users, roles, permissions, company access | User, CustomRole, Watchlist, … |

Dependencies point one way: `users` and `companies` are the base, `market_data` / `floorsheet` / `reports`
build on them, and `analysis` / `market_intelligence` / `dashboard` / `market_calendar` read from everything below.

The floorsheet and reports models moved out of `market_data`; their `db_table` keeps the original
`market_data_*` table names, so no data was copied.

## Frontend page → backend

Routes are in `frontend/src/App.tsx`, their permission rules in `config/routePermissions.ts`. Page files are in `frontend/src/pages/`.

| Route → page | API | Backend |
|---|---|---|
| `/dashboard` → `Dashboard.tsx` | `/api/dashboard/…` | `dashboard/api/views.py` |
| `/market` → `Market.tsx` | `/api/market/summary`, `overview`, `movers`, `heatmap` | `market_data/api/market_views.py` |
| `/market/gainers`, `/market/losers` → `TopMoversPage.tsx` | `/api/market/movers/`, `top-gainers/` | `market_data/services/movers.py`, `top_movers.py` |
| `/market/turnover`, `volume`, `transactions` → `TopActivityPage.tsx` | `/api/market/top-activity/`, `top-*` | `market_data/api/market_views.py` |
| `/market/indices` → `IndicesPage.tsx` | `/api/market-indices/…` | `market_indices/api/views.py` |
| `/market/dividends` → `DividendsPage.tsx` | `/api/market/dividends/` | `reports/api/views.py`, `reports/services/dividends.py` |
| `/market/quarterly-report/:sector` → `QuarterlyReportPage.tsx` | `/api/market/quarterly-report/` | `reports/services/quarterly_reports.py`, `quarterly_metrics.py` |
| `/companies` → `admin/CompaniesPage.tsx` (`/tracked` redirects here) | `/api/companies/` | `companies/api/views.py` |
| `/companies/:symbol` → `StockDetail.tsx` | `/api/companies/<id>/…`, `/api/stocks/<symbol>/intraday/`, `/api/analysis/broker-*` | `companies/`, `floorsheet/`, `analysis/services/broker_accumulation.py` |
| `/floorsheet` → `FloorsheetPage.tsx` | `/api/floorsheet/`, `summary/` | `floorsheet/api/views.py` |
| `/technical-charts` → `TechnicalCharts.tsx` | `/api/market-intelligence/…`, `/api/market-indices/…` | `market_intelligence/indicators/`, `services/technicals.py` |
| `/company-analysis` → `CompanyAnalysisDashboard.tsx` | `/api/analysis/…`, `/api/market-intelligence/…` | `analysis/`, `market_intelligence/` |
| `/broker-analysis[/:brokerId]` → `BrokerAnalysisPage.tsx` | `/api/analysis/brokers/…` | `analysis/services/brokers.py` |
| `/top-brokers[/:broker]` → `TopBrokerPage.tsx`, `TopBrokerStocksPage.tsx` | `/api/analysis/brokers/top/`, `brokers/<id>/` | `analysis/services/brokers.py` |
| `/brokers` → `BrokerListPage.tsx` | `/api/analysis/brokers/list/` | `analysis/api/views.py` |
| `/broker-acc-dist` → `AccDistPage.tsx` (`/brokers-distribution` redirects here) | `/api/analysis/acc-dist/` | `analysis/services/broker_accumulation.py` |
| `/watchlist` → `MyWatchlistPage.tsx` | `/api/market/watchlists/…` | `market_data/api/watchlists.py`, `services/watchlist.py` |
| `/live-trading` → `WatchlistPage.tsx` (admin: `admin/WatchlistPage.tsx`), `/watchlist-comparison` → `WatchlistComparison.tsx` | `/api/market/…`, `/api/floorsheet/` | `market_data/`, `floorsheet/` |
| `/news[/:id]` → `News.tsx`, `NewsDetail.tsx` | `/api/news/…` | `news/api/views.py` |
| `/crawl` → `CrawlerStatus.tsx` | `/api/crawler-runs/…` | `crawler_runs/api/views.py`, `tasks.py` |
| `/reports` → `ExportPage.tsx` | `/api/reports/export/…` | `reports/exports/` |
| `/users`, `/roles-permissions` → `admin/UserManagementPage.tsx`, `admin/RolesPermissionPage.tsx` | `/api/users/admin/…` | `users/api/views.py` |

`/admin/*` and `/analyst/*` are redirects to the routes above. Full endpoint list with permissions: [`docs/api.md`](../../docs/api.md). All API routes are wired in `config/urls.py`.

## Other folders

| Folder | Contents |
|---|---|
| `config/` | settings, root URLs, Celery app and beat schedule |
| `crawlers/` | Scrapy project: spiders and pipelines that fill the tables above |
| `scripts/` | one-off scripts run by hand (`crawl_company_logos.py`) |
| `data/` | seed files (`brokers.csv`, `stock_sectors.csv`, `company_logos.json`, `quarterly_reports_template.csv`) and `backups/` |

Tables, keys and data rules: [`docs/data-model.md`](../../docs/data-model.md).
