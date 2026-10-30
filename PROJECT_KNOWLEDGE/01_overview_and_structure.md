# StockScope: Project Knowledge (1/3): Overview & Structure

Files: **01** overview, map, flow, glossary · **02** code, setup · **03** decisions, mistakes, status, next steps, learning path.
Snapshot date: **2026-10-30**. Repo: `C:\Stock-Market-Application-crawling-2`, branch `main`, 64 commits.
For an AI continuing the work, read all three files plus `CLAUDE.md` and `docs/status.md` before changing code.

---

## 1. OVERVIEW

- **What it is:** StockScope, a personal research web app for the **Nepal Stock Exchange (NEPSE)**.
- **Collects:** daily prices, the floorsheet (every trade with buyer and seller broker), live prices, indices, dividends, quarterly reports, IPO issues and news, all from unofficial Nepali websites/APIs.
- **Analyses:** gainers/losers ("movers"), broker accumulation/distribution, broker positions, ~110 technical indicators, support/resistance, volume anomalies, news→company tagging, calendar views (day-by-day, month-by-month, weekday).
- **Shows:** a React dashboard with login, roles (Admin / Analyst / Viewer / custom) and per-user company access.
- **Scope:** only about 20 **tracked companies** (`TrackedCompany`), not the whole market. Exceptions: indices, dividends, IPOs and market-wide broker pages.
- **Hard principle:** real crawled data only. Missing data is shown as missing, never invented.
- **Who it's for:** the owner (Kripa), personal use. **Not deployed**: it runs locally on Windows or with `docker compose`. Not financial advice.

---

## 2. FILE/FOLDER MAP

```
/
├── CLAUDE.md                 Rules for AI agents (commands, hard rules). READ FIRST.
├── ARCHITECTURE.md           Components, data-flow diagram, route→API→backend table, design decisions
├── README.md                 Features, stack, setup
├── docker-compose.yml        db (Postgres16), redis, backend, worker, beat, frontend (nginx)
├── .env.example              Env var template (copy to .env, never commit .env)
├── StockScope_project_context.zip   Not used by code; owner says it needn't stay (safe to remove)
├── docs/
│   ├── status.md             Known bugs, failing tests, data gaps. READ before touching movers/crawls/routing
│   ├── project-log.md        Feature history, newest first (add an entry for every feature)
│   ├── DATABASE.md · API.md · DATA_SOURCES.md · SECURITY.md · TESTING.md · DEPLOYMENT.md · GLOSSARY.md
│   └── features/             broker-accumulation.md, quarterly-report.md, news-categorization.md
├── Backend/                  Django project (run commands from here)
│   ├── manage.py · requirements.txt · pytest.ini · Dockerfile
│   ├── config/
│   │   ├── settings.py       Env vars, CELERY_BEAT_SCHEDULE, NEPSE_TRADING_WEEKS, thresholds
│   │   ├── settings_test.py  In-memory SQLite, throttles off (used by pytest)
│   │   ├── urls.py           Wires every app under /api/
│   │   └── celery.py
│   ├── apps/                 One Django app per area, all with the same layout:
│   │   │                     models.py, api/(urls,views,serializers), services/, tasks.py,
│   │   │                     management/commands/, tests/test_<feature>.py, README.md
│   │   ├── users/            User, roles, permission keys, company access
│   │   │   ├── permissions.py        HasAppPermission (permission_key on view)
│   │   │   └── company_access.py     filter_company_queryset / require_company_access
│   │   ├── companies/        Company, TrackedCompany; services/selection.py; seed_admin, seed_companies
│   │   ├── market_data/      DailyPrice, TradingHoliday, LiveFeedStatus, watchlists
│   │   │   └── services/     movers.py (ONLY source of gainers/losers), price_source.py,
│   │   │                     trading_days.py, trading_calendar.py, live_prices.py, circuit_breaker.py
│   │   ├── floorsheet/       FloorsheetTransaction, Broker, IntradayCandle
│   │   │   └── services/     sharehub_floorsheet.py, sharehub_time.py, intraday_candles.py,
│   │   │                     trade_filters.py*, footprint.py*, floorsheet_quality.py*, trade_time_backfill.py*
│   │   ├── reports/          Dividends, EPS, QuarterlyReport, IpoIssue, CSV/XLSX/PDF exports
│   │   ├── market_indices/   NEPSE + 13 sub-indices, whole-market rows, index replication
│   │   ├── market_intelligence/  indicators/registry.py (~110 indicators), breadth, S/R
│   │   ├── analysis/         broker_accumulation.py, broker_position.py, floorsheet_grid.py, DailyAnalysis
│   │   ├── news/             NewsArticle, tags, categorization.py (embeddings + keywords)
│   │   ├── crawler_runs/     CrawlRun, tasks that launch spiders
│   │   ├── dashboard/        Role dashboards, export endpoints (no models, no tests)
│   │   └── market_calendar/  BS/AD calendar, weekday/day-by-day/month-by-month (derived, no models)
│   ├── crawlers/             Separate Scrapy project
│   │   ├── runner.py         Runs each spider as a subprocess; spider lists (NEWS_SPIDERS, ...)
│   │   └── crawlers/         settings.py (politeness), items.py, pipelines.py (writes Django models),
│   │       │                 market_wide_pipeline.py (parse_decimal), dividend/ipo pipelines, utils/dates.py
│   │       └── spiders/      trading_data, floorsheet, dividends, ipo_issues, brokers, news spiders;
│   │                         merolagani.py = actually the `market_stocks` spider (misnamed)
│   ├── data/                 brokers.csv, stock_sectors.csv, company_logos.json, backups/ (old dumps)
│   └── backups/              JSON backups written by trade-time repair commands
└── frontend/                 React 19 + TypeScript + Vite + Tailwind
    └── src/
        ├── App.tsx           All routes
        ├── api/client.ts     axios + JWT + shared-promise token refresh; one api module per backend area
        ├── hooks/            TanStack Query wrappers
        ├── pages/            One file per route (e.g. TopMoversPage, AccDistPage, BrokerPositionPage)
        ├── components/       market/ (format.ts, heatGrid.tsx), brokers/, charts/, calendar/, admin/, layout/ (Sidebar)
        ├── config/routePermissions.ts   Frontend copy of permission rules
        └── contexts/AuthContext.tsx     user, permissions, tokens
```
`*` = new, **uncommitted** files (2026-10-30).

---

## 3. HOW IT WORKS (step by step)

**Three parts, one PostgreSQL database:** collectors (Scrapy + HTTP clients) → Django/DRF backend → React frontend.

1. **Celery beat** (a scheduler) fires tasks at fixed NPT times, stored in the DB (`DatabaseScheduler`).
2. Tasks go through **Redis** to one **Celery worker** (`--pool=solo`, queue `crawling`, one task at a time).
3. Crawl tasks call `crawlers/runner.py::run_spider(name)`, which starts `python -m scrapy crawl <name>` as a **subprocess** with a timeout, and record a `CrawlRun`.
4. The spider fetches pages politely (robots.txt, 1 request/domain, 2 s delay). Scrapy **pipelines** bootstrap Django and **upsert** rows, so re-running is safe.
5. Some data comes from direct HTTP services instead: live prices (NEPSE via `nepse-data-api`), ShareHub floorsheet with trade times, index history, nepsetrading quarterly reports.
6. **Derive tasks** then compute analysis tables (DailyAnalysis, VolumeAnomaly, market-intelligence snapshots, support/resistance).
7. The **frontend** logs in (JWT) and calls `/api/...`. Each view checks the **permission key**, narrows the result to the **user's allowed companies**, and calls a **service**.
8. Services read only `source="crawled"` prices and return JSON with `"scope": "tracked_companies"` and `null` + `reason` for missing data.

**Daily timeline (NPT, trading days Mon–Fri):**
- 08:30 IPO issues · 11:00–15:15 live prices every 2 min, index ticks + intraday candles every 5 min
- 15:15/15:45/18:30 index history · 15:30 final candles · 16:00 index replication check
- 18:00 prices → chain (price fields → analysis → S/R) · 18:10 whole-market rows · 18:15 floorsheet
- 18:45 analysis again · 19:00 market intelligence · 19:30 dividends · 19:45 quarterly reports
- Hourly news; every 10 min news tagging; every 2 h mark stuck crawls failed; Sat 20:00 broker list.

**A page request:** `PermissionRoute` (frontend) → `api/*.ts` with `Bearer` token → on 401 refresh once and retry → DRF `HasAppPermission` → `company_access` helper → service → JSON.

---

## 4. KEY CONCEPTS & TERMS

**Stock market / NEPSE**
- **NEPSE:** Nepal Stock Exchange, and the name of its main index. Plus 13 **sub-indices** (BANKING, HYDROPOWER, ...).
- **Session:** one trading day, 11:00–15:00 NPT. **Sun–Thu until 2026-04-05, Mon–Fri from 2026-04-06.** Holidays come from the `TradingHoliday` table.
- **NPT:** Nepal Time, UTC+05:45.
- **OHLC:** open, high, low, close prices. **LTP:** last traded price (live). **Turnover:** value traded (qty × rate). **Volume:** shares traded.
- **Floorsheet:** list of every trade: transaction id, buyer broker no., seller broker no., quantity, rate.
- **Broker:** a trading member (by number, e.g. 58). One broker = many clients.
- **Odd lot:** trade under 10 shares; doesn't set the official close/high/low.
- **Pre-open auction:** opening fills stamped ~10:46 NPT at one price.
- **Accumulation / distribution:** a broker net buying / net selling a stock over N sessions.
- **Circuit (price limit):** NEPSE limits daily moves to ~10%; a bigger move suggests a **corporate action** (bonus/right share/split).
- **Book closure, bonus, cash dividend, AGM, SEBON (regulator), IPO/FPO/right share.**
- **EPS, BV, DPPS, PE, PB:** earnings/book value/distributable profit per share; price ÷ EPS; price ÷ BV.
- **Fiscal year:** Nepali year like `2082/2083`, starts mid-July; quarterly figures are cumulative.
- **BS / AD:** Bikram Sambat (Nepali calendar) vs Gregorian. Store AD; convert with `nepali_datetime`.
- **VWAP:** volume-weighted average price. **RVOL:** relative volume. **Breadth:** advancers vs decliners.
- **Support / resistance:** price levels where price repeatedly turned.
- **Tick rule:** classify a trade as buy if price went up vs previous trade, sell if down. An estimate.
- **Footprint chart:** per time bar and price level, buy vs sell volume (order flow).
- **Index replication / K:** recompute an index as market cap × constant K to verify it.

**Project terms**
- **Tracked company:** `TrackedCompany.is_tracked`; most features cover only these.
- **Whole-market tables:** keyed by `symbol`: `MarketStockDaily`, `CompanyDaily`, `StockSector`, `DividendAnnouncement`, `IpoIssue`.
- **`DailyPrice.source`:** `crawled` (real) vs `unverified` / `seeded` / `manual` (synthetic/old). Only `crawled` may be used.
- **Movers buckets:** gainer / loser / unchanged, or excluded: `missing_price`, `not_traded`, `missing_previous_session`, `prev_close_zero`, `possible_corporate_action`.
- **Tracked Basket:** the app's own index of tracked companies (not official).
- **Permission key:** string like `view_market_data` required by a view.
- **Company access:** which companies a non-admin may see (`UserCompanyAccess`); none granted = sees none.
- **CrawlRun:** DB record of one spider run.
- **Circuit breaker (app):** after 3 failed NEPSE calls, stop calling for 30 min (state in Redis).

**Libraries & techniques**
- **Django:** Python web framework (models = DB tables, migrations, admin). **DRF:** Django REST Framework for JSON APIs.
- **SimpleJWT:** login returns `access` (30 min) + `refresh` (7 days, rotating, old one blacklisted) tokens.
- **PostgreSQL:** the database. **Redis:** in-memory store used as Celery's message broker.
- **Celery:** background task queue; **beat** = its scheduler; `django_celery_beat` keeps the schedule in the DB.
- **Scrapy:** crawling framework: spiders (fetch+parse) → items → pipelines (save). Runs on Twisted.
- **Upsert:** insert-or-update by a unique key (`update_or_create`, `bulk_create(ignore_conflicts=True)`).
- **nepse-data-api:** unofficial Python client for NEPSE's site.
- **sentence-transformers (`all-MiniLM-L6-v2`):** turns text into vectors; cosine similarity = meaning similarity.
- **Decimal:** exact base-10 numbers for money (floats have rounding errors).
- **Timezone-aware datetimes:** datetimes carrying a zone; DB stores UTC.
- **React / TypeScript / Vite / Tailwind:** UI library / typed JS / dev server+bundler / utility CSS.
- **TanStack Query:** fetches and caches API data in React. **axios:** HTTP client with interceptors.
- **klinecharts:** candlestick charts; **recharts:** other charts.
- **RBAC:** role-based access control.
- **Docker Compose:** runs all services in containers with one command.
