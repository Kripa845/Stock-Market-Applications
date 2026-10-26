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
| `users` | Users, roles, permissions, company access | User, CustomRole, Watchlist, … |

Dependencies point one way: `users` and `companies` are the base, `market_data` / `floorsheet` / `reports`
build on them, and `analysis` / `market_intelligence` / `dashboard` read from everything below.

The floorsheet and reports models moved out of `market_data`; their `db_table` keeps the original
`market_data_*` table names, so no data was copied.

## Frontend page → backend

| Page | API | Backend |
|---|---|---|
| Dashboard | `/api/dashboard/…` | `dashboard/api/views.py` |
| Market | `/api/market/summary`, `overview`, `movers`, `heatmap`, `top-*` | `market_data/api/market_views.py` |
| Indices | `/api/market-indices/…` | `market_indices/api/views.py` |
| Dividends | `/api/market/dividends/` | `reports/api/views.py`, `reports/services/dividends.py` |
| Quarterly Report | `/api/market/quarterly-report/` | `reports/api/views.py`, `reports/services/quarterly_reports.py` |
| Companies, Stock detail | `/api/companies/…`, `/api/stocks/<symbol>/intraday/` | `companies/api/views.py`, `floorsheet/api/views.py` |
| Floorsheet | `/api/floorsheet/`, `/api/floorsheet/summary/` | `floorsheet/api/views.py` |
| Broker analysis, Top brokers, Brokers | `/api/analysis/brokers/…` | `analysis/api/views.py`, `analysis/services/brokers.py` |
| Broker accumulation / distribution | `/api/analysis/broker-summary`, `broker-signal`, `broker-flow` | `analysis/services/broker_accumulation.py` |
| Company analysis | `/api/analysis/…`, `/api/market-intelligence/…` | `analysis/`, `market_intelligence/` |
| Technical charts | `/api/market-intelligence/…` | `market_intelligence/services/technicals.py` |
| Watchlist | `/api/market/watchlists/…` | `market_data/api/watchlists.py`, `market_data/services/watchlist.py` |
| News | `/api/news/…` | `news/api/views.py` |
| Crawl | `/api/crawler-runs/…` | `crawler_runs/api/views.py`, `crawler_runs/tasks.py` |
| Reports (export) | `/api/reports/export/…` | `reports/exports/` |
| Users | `/api/users/admin/…` | `users/api/views.py` |

All routes are wired in `config/urls.py`.

## Other folders

| Folder | Contents |
|---|---|
| `config/` | settings, root URLs, Celery app and beat schedule |
| `crawlers/` | Scrapy project: spiders and pipelines that fill the tables above |
| `scripts/` | one-off scripts run by hand (`crawl_company_logos.py`) |
| `data/` | seed files (`brokers.csv`, `stock_sectors.csv`, `company_logos.json`) and `backups/` |
