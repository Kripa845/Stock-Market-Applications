# StockScope — Project Context (for an AI assistant)

> Paste this file (or upload the zip) at the start of a chat. It describes the whole
> project so you can help without seeing the source. When you need exact code, ask
> me to paste the specific file — every path below is relative to the repo root
> `Stock-Market-Application-crawling-2/`.
>
> Snapshot taken: **2026-10-12**.

---

## 1. What the project is

**StockScope** is a research web app for the **Nepal Stock Exchange (NEPSE)**. It:

1. **Crawls** real data from public Nepali sites (Scrapy spiders, run by Celery on a schedule):
   - daily OHLCV prices per company (ShareSansar),
   - floorsheets = every individual trade with buyer/seller broker (ShareSansar + ShareHub),
   - financial news (ShareSansar, MeroLagani, FiscalNepal, Bizmandu, Arthakhabar, NepseAlpha),
   - broker list (nepseportfoliotracker / moneymitra).
2. **Analyses** it: 110 technical indicators, VWAP, volume anomalies, buy/sell pressure,
   broker concentration, market breadth, a home-made "Tracked Basket" index, sector rotation,
   intraday candles, news sentiment and news→price reaction.
3. **Categorises news** to companies automatically (hybrid: keyword/alias matching +
   sentence-transformer embeddings), with analyst manual correction + audit trail.
4. **Serves** it via a Django REST API to a **React + TypeScript** dashboard, with
   role-based access (Admin / Analyst / Viewer + custom roles) and per-user company access.

It covers only the **tracked companies** (currently 20), never the whole NEPSE market,
and the UI is careful to label numbers "tracked companies only".

### Core principle: real data only
- `DailyPrice.source = "crawled"` is the **only** real price data. Rows with
  `source="unverified"` are old synthetic seed data (random walk from `seed_market_data`)
  and must **never** feed charts, indicators or analysis.
- No mock/simulated/back-filled numbers anywhere in the UI. Missing data is shown as
  missing (empty states, "—", warnings), never invented.

### Trading calendar facts
- Timezone: **Asia/Kathmandu (NPT, UTC+5:45)**. Session 11:00–15:00 NPT.
- NEPSE traded **Sunday–Thursday until 2026-04-05** and **Monday–Friday from 2026-04-06**.
  Defined once in `Backend/config/settings.py` → `NEPSE_TRADING_WEEKS`; read through
  `apps/market_data/services/trading_days.py`. Holidays live in the `TradingHoliday` table.
- "Previous session" is always derived from the crawled `DailyPrice` dates
  (`services/trading_calendar.py`), never from a weekday rule.

### Current data volume (2026-10-12)
| Table | Rows |
|---|---|
| Company / TrackedCompany | 20 / 20 |
| DailyPrice | 13,726 (crawled range 2023-10-04 → 2026-10-09) |
| FloorsheetTransaction | 147,227 |
| IntradayCandle | 632 |
| Broker | 92 |
| NewsArticle | 1,102 (mostly ShareSansar 509, MeroLagani 483, FiscalNepal 102) |
| ArticleCompanyTag | 151 |
| DailyAnalysis | 14,486 |
| CompanyTechnicalSnapshot | 13,716 |
| CrawlRun | 635 |
| User | 22 |

Tracked companies: ADBL, AKJCL, CBBL, CHCL, GUFL, HDL, HIDCL, LICN, MNBBL, NABIL, NICA,
NLG, NLIC, NTC, SANIMA, SCB, SHIVM, STC, TRH, UPPER.

---

## 2. Tech stack

| Layer | Tech |
|---|---|
| Backend | Python 3.13, Django 5.1, Django REST Framework 3.15, SimpleJWT (access 30 min, refresh 7 days, rotating + blacklist), django-filter, django-cors-headers |
| DB | PostgreSQL 16 (psycopg 3). Tests use `config/settings_test.py` |
| Jobs | Celery 5.4 + Redis 7, django-celery-beat (`DatabaseScheduler`), queue `crawling`, `--pool=solo` (Windows-safe) |
| Crawling | Scrapy 2.12 (separate Scrapy project in `Backend/crawlers/`, launched as a subprocess) |
| ML / NLP | sentence-transformers (`all-MiniLM-L6-v2`), torch, scikit-learn, numpy/pandas; lexicon-based sentiment; `nepali_datetime` for Bikram Sambat dates |
| Exports | openpyxl (XLSX), reportlab (PDF), CSV |
| Frontend | React 19, TypeScript 6, Vite 8, Tailwind CSS 3, react-router-dom 7, axios, recharts, **klinecharts** (candlestick charts), lucide-react icons, date-fns, oxlint |
| Deploy | `docker-compose.yml`: db, redis, backend, worker, beat, frontend (nginx) |

Dev environment: Windows 11, PowerShell/Git Bash, venv at `Backend/venv`.
Note: Windows App Control blocks some native binaries locally, so ML-model tests are
stubbed and `oxlint` may not run locally.

---

## 3. Repository layout (top level)

```
Stock-Market-Application-crawling-2/
├── README.md                 # feature overview + news-categorisation design
├── docker-compose.yml        # db, redis, backend, worker, beat, frontend
├── .env.example              # all env vars (copy to .env)
├── Backend/                  # Django project + Scrapy project
│   ├── manage.py
│   ├── requirements.txt
│   ├── pytest.ini            # DJANGO_SETTINGS_MODULE=config.settings_test
│   ├── Dockerfile
│   ├── config/               # settings, urls, celery, wsgi/asgi
│   ├── apps/                 # 8 Django apps (see §4)
│   ├── crawlers/             # Scrapy project (see §5)
│   ├── data/brokers.csv      # broker seed list
│   ├── companies.txt, company_logos.json, crawl_company_logos.py   # company/logo seed helpers
│   └── *.json / db.sqlite3.backup / dailyprice_backup.json          # old data dumps (not used at runtime)
├── frontend/                 # React + Vite app (see §7)
└── project-context/          # this document
```

---

## 4. Backend — Django apps (`Backend/apps/`)

### 4.1 `config/` (project wiring)
- `settings.py` — env-driven settings (`python-dotenv`). Key items: `AUTH_USER_MODEL="users.User"`;
  DRF default auth = JWT, default permission = `IsAuthenticated`, page size 20, throttles
  `auth` 10/min and `public` 60/min; `TIME_ZONE = CELERY_TIMEZONE = "Asia/Kathmandu"`,
  `CELERY_ENABLE_UTC=False`; `NEPSE_TRADING_WEEKS`; news categorisation thresholds;
  **`CELERY_BEAT_SCHEDULE`** (below).
- `urls.py` — mounts every app under `/api/...` (see §6).
- `celery.py` — Celery app `config`.
- `settings_test.py` — test settings used by pytest.

**Beat schedule (NPT, trading days only where noted):**
| Time | Task | What |
|---|---|---|
| every hour :00 | `crawler_runs.tasks.crawl_all_news` | all news spiders |
| every 10 min | `news.tasks.categorize_unprocessed_news_task` | tag new articles |
| 11:00–15:05 every 5 min (trading days) | `market_data.tasks.build_intraday_candles_live` | ShareHub floorsheet sync → intraday candles |
| 15:30 (trading days) | `market_data.tasks.finalize_intraday_candles` | final candle rebuild |
| 18:00 (trading days) | `crawler_runs.tasks.crawl_daily_prices` | `trading_data` spider (all tracked companies) |
| 18:15 (trading days) | `crawler_runs.tasks.crawl_floorsheet` | `floorsheet` spider |
| 18:45 (trading days) | `analysis.tasks.rebuild_all_analysis` | DailyAnalysis, VWAP, anomalies |
| 19:00 daily | `market_intelligence.tasks.build_daily_market_intelligence` | breadth, basket index, technicals, sector rotation |
| Saturday 20:00 | `crawler_runs.tasks.crawl_brokers` | broker list |
| every 2 h :30 | `crawler_runs.tasks.recover_stale_crawls` | mark hung crawl runs failed |

### 4.2 `apps/companies/` — companies & tracking
- `models.py`
  - `Company`: `symbol`, `name`, `logo_url`, `sector`, `aliases` (JSON list, used by news matching), `is_active`, `created_by`, *(WIP: `ltp`, `previous_close`, `prices_updated_at`)*.
  - `TrackedCompany`: one-to-one `company` (related name `tracking`), `is_tracked`.
- `selection.py` — `tracked_active_companies()`, `parse_symbols()`, `select_crawl_companies(symbols)` (which companies a crawl fetches).
- `views.py` — company CRUD, toggle-track, `/prices/`, `/intraday/`, `/floorsheet/`, `/volume-anomalies/`, `/rvol/`, `/news-correlation/`, sectors, legacy `top_gainers`/`top_losers` (use `Company.ltp`).
- `serializers.py` — `CompanySerializer` (adds latest change via `market_data.services.movers.company_rows`).
- `management/commands/`: `seed_companies`, `seed_admin`, `import_company_logos`, `seed_market_data` (**synthetic** — don't use for real data).
- `update_prices.py` — *WIP, uncommitted*: a `Command` to fetch live LTP via `nepse_data_api` (package not in requirements; file is not under `management/commands/` so Django can't find it yet).

### 4.3 `apps/market_data/` — prices, floorsheet, intraday, brokers, tracked dashboard
- `models.py`
  - `DailyPrice`: `company`, `source` (`crawled`|`unverified`), `date`, `open/high/low/close`, `volume`, `turnover`, `transactions` (count of floorsheet trades), `source_change_pct` (ShareSansar's published % change — vs exchange-*adjusted* previous close). Unique `(company, date)`. Previous close is **not stored**; it's derived.
  - `FloorsheetTransaction`: `company`, `date`, `trade_time` (nullable), `transaction_id`, `buyer_broker`, `seller_broker`, `quantity`, `rate`, `amount`.
  - `IntradayCandle`: `company`, `interval` (1m/5m/15m/30m/1h), `bucket_start`, OHLCV, `turnover`, `trade_count`. Unique `(company, interval, bucket_start)`.
  - `Broker` (`broker_no`, code, name, logo, website, tms_link), `TradingHoliday` (`date`, `name`), `DividendAnnouncement` (`fiscal_year`, `bonus_pct`, `cash_pct`, `book_closure_date`).
- `services/`
  - `market_stats.py` — scope helpers: `PRICE_SOURCE="crawled"`, `tracked_companies()`, `tracked_prices()`, broker activity, `signals`, `basket_index` (Tracked Basket, base 1000, turnover- and equal-weighted), dividends.
  - **`movers.py`** — single definition of session change used everywhere. `annotated_companies()` annotates every tracked company in SQL with close, prev close, change, change % and a **bucket**: `gainer` / `loser` / `unchanged`, or excluded as `missing_price` (no crawled row on that date), `not_traded` (volume 0), `missing_previous_session`, `prev_close_zero`, `possible_corporate_action` (>10% close-to-close with no source %). Change % = ShareSansar `source_change_pct` when present (marked `adjusted` if it differs from close-to-close by >0.05), else close-to-close (`unadjusted`). Public functions: `tracked_movers(period, ...)` (periods `1D` "Today", `2S`, `3S`, `5S`, `7S`, `20S` "1 month", `60S` "3 months", `80S` "4 months", `120S` "6 months", `240S` "1 year"; aliases `1W`, `1M`, `3M`, `6M`, `1Y`, `2D`…), `tracked_movers_page()` (paged/filterable), `tracked_summary()`, `top_by(metric)`, `company_rows()`, `provenance()`, `incomplete_session_warning()` (adds a `warning` when some tracked companies have no price row on the latest date).
  - `trading_calendar.py` — `trading_dates()`, `latest_trading_date()`, `previous_trading_sessions()`, rolling windows (calendar = dates present in crawled `DailyPrice`).
  - `trading_days.py` — `is_market_day()`, `market_closed_reason()` (weekday rules + holidays).
  - `intraday_candles.py` — build candles from floorsheet trades (`rebuild_day`, `rebuild_range`, `session_bounds`).
  - `sharehub_floorsheet.py` + `sharehub_time.py` — fetch floorsheet with trade times from `https://sharehubnepal.com/live/api/v2/floorsheet` (its "Z" timestamps are actually NPT).
  - `price_fields.py` — fill `DailyPrice.transactions` from floorsheet counts. `rvol.py` — relative volume. `price_source.py`, `import_prices.py`, `intraday.py`.
- `market_views.py` + `market_urls.py` → `/api/market/...` (tracked dashboard; every response has `"scope": "tracked_companies"` and cached responses).
- `views.py` + `urls.py` → `/api/market-data/...` (price list, floorsheet list, `movers/tracked/` cards + `movers/tracked/list/` paged page). `stock_urls.py` → `/api/stocks/<symbol>/intraday/`.
- `tasks.py` — intraday live/finalize tasks, `derive_price_fields_task`.
- `management/commands/`: `load_sharehub_floorsheet`, `fix_sharehub_trade_times`, `rebuild_intraday_candles`, `backfill_price_fields`, `import_brokers`, `check_brokers`.
- Tests: `test_movers.py`, `test_market_stats.py`, `test_intraday_candles.py`, `tests.py`.

### 4.4 `apps/analysis/` — per-company behaviour analysis
- `models.py`: `DailyAnalysis` (per company-day: `vwap`, `close_price`, `previous_close`, `daily_return_pct`, `volume`, `volume_average`, `volume_ratio`, `volume_anomaly`, `has_sufficient_history`, `pressure` + `pressure_score` + `pressure_method`, `news_count`), `VolumeAnomaly` (rolling mean/std, z-score), `NewsPriceCorrelation` (JSON results per company).
- `services/`: `daily_metrics.py` (VWAP, volume baseline, anomalies, pressure, `rebuild_company_analysis`), `brokers.py` (broker activity, top stocks per broker), `volume_anomaly.py`, `news_market_reaction.py`, `news_price_correlation.py`, `news_sentiment_forward.py` (exploratory, not predictive).
- `views.py` → `/api/analysis/...`: daily rows, behaviour summary, broker activity, broker list/detail, categorized news, news-price correlation, cross-company comparison, dashboard summary.
- `tasks.py`: `rebuild_company_analysis_task`, `rebuild_all_analysis`. Command: `backfill_market_analysis`.

### 4.5 `apps/market_intelligence/` — indicators & market-wide snapshots
- `indicators/` — pure-Python indicator library (lists in → same-length lists out, `None` during warm-up, never 0):
  `core.py` (sma/ema/rma/wma/rolling helpers), `moving_averages.py`, `momentum.py` (MACD, RSI, Stoch, CCI…), `trend.py` (ADX, Aroon, SAR, Supertrend, Ichimoku…), `volatility.py` (ATR, Bollinger, Keltner, Donchian…), `volume.py` (OBV, CMF, MFI…), `price.py` (pivots, 52-week high/low…), `market.py` (breadth, relative strength), `custom.py` (standard versions of NepseAlpha-named indicators), **`registry.py`** (metadata for all ~110 indicators: params, outputs, how to draw; `compute()`, `registry_payload()`).
- `models.py`: `MarketBreadthSnapshot`, `ProxyIndexSnapshot` (basket level, daily return, equal-weight level), `CompanyTechnicalSnapshot` (patterns, signal, signal_score, sufficient_history), `SectorRotationSnapshot`.
- `services/`: `snapshots.py` (breadth + proxy index from DailyPrice), `technicals.py`, `sector_rotation.py`.
- `views.py` → `/api/market-intelligence/...`: breadth, heatmap, rankings, sector rotation, relative strength, company technicals, indicator registry, company indicator series.
- Tests compare indicators against independent reference calculations.

### 4.6 `apps/news/` — news storage, categorisation, sentiment
- `models.py`: `RawArticle` (raw HTML per fetch), `NewsArticle` (`source`, `url`, `headline`, `body`, `published_at`, `image_url`, `content_hash`, `language`, `sentiment` + label/status/method, `is_processed`, `data_provenance`), `ArticleCompanyTag` (`article`, `company`, `confidence`, `method`, `evidence` JSON, `is_manual`), `CategorizationCorrection` (audit: action add/remove/update, previous values, `reason`, `corrected_by`, `corrected_at`).
- `services/`: `categorization.py` (hybrid score = 0.60 × embedding cosine + 0.40 × lexical; threshold 0.65; semantic-only 0.75; company profile cache), `keyword_matcher.py` / `confidence.py` (symbol/name/alias regex matching), `corrections.py` (manual tags always win, never overwritten by auto tagging), `sentiment.py` (lexicon sentiment, English + Nepali), `article_images.py`. Empty placeholders: `embedding_classifier.py`, `llm_classifier.py`, `ner_classifier.py`, `categorizer.py`.
- `selectors.py` — `real_articles()`, `real_tags()` (exclude synthetic).
- `views.py` → `/api/news/...`: list/detail, stats, public latest, recategorize, trigger categorize, corrections.
- `tasks.py`: categorize one/unprocessed/all, sentiment one/unscored/all.
- Commands: `categorize_news`, `backfill_news_images`, `repair_news_dates` (fixes Bikram Sambat dates parsed as Gregorian).

### 4.7 `apps/users/` — auth, roles, permissions, company access, watchlist
- `models.py`: `User` (email login, `role` = admin/analyst/viewer, optional `custom_role`), `RolePermissionConfig` (permission list per built-in role, editable), `CustomRole`, `UserCompanyAccess` (per-user allowed companies, `status`), `WatchlistItem`.
  `User.get_app_permissions()` → admins get all keys; custom role → its list; else the role's config.
- Permission keys (`serializers.py` → `ROLE_PERMISSIONS`; within a group each key requires the earlier ones):
  - users: view/create/edit/delete_users, change_user_roles, activate_users
  - companies: view/create/edit/delete_companies, manage_tracked_companies
  - market_data: view_market_data, view_price_history, view_trading_volume, view_vwap, view_buy_sell_pressure
  - news: view_news, categorize_news, correct_categories, edit_news, delete_news
  - watchlist: view/add/remove/edit_watchlist
  - crawler: view_crawl_runs, run_crawler, view_crawl_logs, retry_failed_crawl
  - analysis: view_analysis, view_price_trends, view_volume_trends, view_vwap_analysis, view_pressure_analysis
  - reports: view_reports, generate_reports, export_reports
  - roles_permissions: view/create/edit/delete_roles, assign_roles
- `permissions.py` — DRF classes (`HasAppPermission`, role classes). `company_access.py` — `filter_company_queryset()`, `require_company_access()` etc.; applied to company lists, prices, floorsheet, analysis, dashboards, crawls, watchlist, exports (not to plain news reading).
- `views.py` → `/api/users/...`: login (JWT), register, token refresh, me, me/permissions, admin users CRUD + company access, roles, custom roles, role permissions, statistics.

### 4.8 `apps/crawler_runs/` — crawl orchestration & history
- `models.py`: `CrawlRun` (`crawl_type`, `source`, `target`, `status` pending/running/success/failed/cancelled, `started_at`, `completed_at`, counters for articles/prices/floorsheet found/created/updated, `task_id`, `errors`, `logs`, `metadata`, `triggered_by`, `process_id`).
- `tasks.py`: `run_crawl` (runs `scrapy crawl` via `crawlers/runner.py` subprocess with time limits), `crawl_all_news`, `crawl_daily_prices`, `crawl_floorsheet`, `crawl_floorsheet_sample`, `crawl_brokers`, `run_full_crawl_pipeline`, `recover_stale_crawls`. Skips when the market is closed.
- `views.py` → `/api/crawler-runs/` (also `/api/admin/crawl-runs/`): list/trigger, detail, cancel, retry.
- Commands: `run_crawl`, `recover_crawls`, `backfill_floorsheet`.

### 4.9 `apps/dashboard/` — role dashboards & exports
- `views.py` → `/api/dashboard/` summary, admin, analyst, viewer.
- `export_views.py` → `/api/dashboard/export/...` and `/api/reports/export/...`: companies, news, trading (CSV/XLSX/PDF), brokers, floorsheet, combined report. Needs `export_reports` + company access.

---

## 5. Crawlers (`Backend/crawlers/`) — separate Scrapy project

- `scrapy.cfg`, `crawlers/settings.py` (pipelines: CrawlRun 100 → News 300 → TradingData 400 → Floorsheet 500; retries 2), `crawlers/items.py` (`NewsItem`, `DailyTradingDataItem`, `FloorsheetItem`), `crawlers/middlewares.py`.
- **`crawlers/pipelines.py`** (~1,500 lines): bootstraps Django, saves items. `TradingDataPipeline` uses `DailyPrice.objects.update_or_create(company, date)` → re-running a crawl is safe (updates, never duplicates). `NewsPipeline` dedupes by URL and content hash. `FloorsheetPipeline`, `BrokerPipeline`, `MoneymitraBrokerPipeline`, `CrawlRunPipeline` (records counters on `CrawlRun`).
- `runner.py` — launches `scrapy crawl` as a subprocess with timeout (`NEWS_SPIDERS`, `MARKET_DATA_SPIDERS`).
- `crawlers/spiders/`:
  | Spider | Source | Data |
  |---|---|---|
  | `trading_data` | sharesansar.com `company-price-history` (per company, CSRF token + POST) | daily OHLCV + `per_change`. Args: `-a symbols=A,B`, `-a window_days=N` (default 31), `-a max_pages=` |
  | `floorsheet` | sharesansar.com `company-floor-sheet` | trades; `mode=sample` with offsets |
  | `sharesansar`, `merolagani`, `bizmandu`, `arthakhabar`, `fiscalnepal`, `nepsealpha`, `nepalipaisa` | news portals | articles (base class `base_news.py`) |
  | `brokers` / `moneymitra_brokers` | nepseportfoliotracker.app API / moneymitra.com | broker list |
- `crawlers/utils/` — `dates.py` (incl. `parse_bikram_sambat`), `text.py`, `urls.py` (`canonicalize_url`). Older duplicates in `crawlers/utils/` and `crawlers/base/client.py`.

**Manual crawl examples** (from `Backend/crawlers/`):
```bash
../venv/Scripts/python.exe -m scrapy crawl trading_data                      # all tracked, last 31 days
../venv/Scripts/python.exe -m scrapy crawl trading_data -a symbols=NABIL,ADBL -a window_days=10
../venv/Scripts/python.exe -m scrapy crawl trading_data -a window_days=300   # backfill history
../venv/Scripts/python.exe -m scrapy crawl floorsheet
../venv/Scripts/python.exe -m scrapy crawl sharesansar
```

---

## 6. REST API map (all under `/api/`, JWT `Authorization: Bearer <access>` unless "public")

| Prefix | Endpoints |
|---|---|
| `users/` | `login/`, `register/`, `token/refresh/`, `me/`, `me/permissions/`, `admin/users/`, `admin/users/<id>/`, `admin/users/<id>/company-access/`, `admin/roles/`, `admin/roles/<key>/`, `admin/roles/statistics/`, `admin/role-permissions/`, `admin/custom-roles/`, `admin/custom-roles/<id>/`, `admin/analysts/` |
| `companies/` | `` (list/create), `<id>/`, `<id>/toggle-track/`, `<id>/prices/`, `<id>/intraday/`, `<id>/floorsheet/`, `<id>/behavior-summary/`, `<id>/news-price-correlation/`, `<symbol>/volume-anomalies/`, `<symbol>/rvol/`, `<symbol>/news-correlation/`, `sectors/`, `top-gainers/`, `top-losers/` |
| `market/` (tracked dashboard) | `public/snapshot/` (public), `summary/`, `movers/?period=1D&limit=10`, `top-turnover/`, `top-volume/`, `top-transactions/`, `brokers/<symbol>/`, `signals/<symbol>/`, `basket-index/`, `dividends/`, `watchlist/`, `watchlist/<symbol>/`, `news/<symbol>/` |
| `market-data/` | `` (prices), `floorsheet/`, `movers/tracked/`, `movers/tracked/list/?side=gainer&page=1` |
| `floorsheet/` | floorsheet list (filters: symbol, company_id, date_from, date_to) |
| `stocks/` | `<symbol>/intraday/?interval=5m&date=` |
| `analysis/` | `daily/`, `cross-company/`, `dashboard-summary/`, `brokers/`, `brokers/<id>/`, `companies/<id>/behaviorsummary/`, `companies/<id>/brokers/`, `companies/<id>/news-pricecorrelation/`, `companies/<id>/categorized-news/` |
| `market-intelligence/` | `breadth/`, `heatmap/`, `rankings/`, `sectors/rotation/`, `relative-strength/`, `companies/<id>/technicals/`, `indicators/registry/`, `companies/<id>/indicators/` |
| `news/` | `` (list, filters), `<id>/`, `<id>/recategorize/`, `<id>/trigger-categorize/`, `corrections/`, `stats/`, `public/latest/` (public) |
| `crawler-runs/` (= `admin/crawl-runs/`) | `` (list / POST trigger), `<id>/`, `<id>/cancel/`, `<id>/retry/` |
| `dashboard/` (= `reports/`) | `summary/`, `admin/`, `analyst/`, `viewer/`, `export/companies|news|trading|brokers|floorsheet|report/` |
| `admin/users/` | duplicate admin user endpoints |

Example `GET /api/market/movers/?period=1D` response shape:
```json
{
  "scope": "tracked_companies", "as_of": "2026-10-09", "period": "1D", "base_date": "2026-10-08",
  "gainers": [{"symbol": "CHCL", "name": "...", "sector": "...", "logo_url": "...", "close": 333.0,
               "prev_close": 325.0, "change": 8.0, "change_pct": 2.46, "change_basis": "source",
               "adjusted": false, "unadjusted": false, "volume": 0, "turnover": 0, "sparkline": [...]}],
  "losers": [...], "unchanged": [...], "excluded": [...],
  "tracked_count": 20, "gainers_count": 18, "losers_count": 2, "unchanged_count": 0,
  "excluded_counts": {"missing_price": 0, "not_traded": 0, "missing_previous_session": 0,
                      "prev_close_zero": 0, "possible_corporate_action": 0},
  "warning": "only present when some tracked companies have no price row",
  "provenance": {"table": "market_data_dailyprice", "price_source": "crawled", "...": "..."}
}
```

---

## 7. Frontend (`frontend/`)

- `vite.config.ts` (plain React plugin), `tailwind.config.js` (custom colours e.g. `up` #26a69a, `down` #ef5350, `bg-*`, `text-*`, `accent`), `index.css` (theme variables; `.landing` palette), `nginx.conf` + `Dockerfile` (production build), `.oxlintrc.json`.
- Env: `VITE_API_BASE_URL` (default `http://localhost:8000/api`).
- Scripts: `npm run dev`, `npm run build` (`tsc -b && vite build`), `npm run lint`.

### 7.1 `src/` structure
- `main.tsx`, `App.tsx` — router; `AuthContext` + `PermissionRoute` guards (rules in `config/routePermissions.ts`).
- `api/` — one module per backend area, all on `client.ts` (axios instance, attaches `access_token` from localStorage, auto-refreshes on 401 with a shared refresh promise): `auth`, `users`, `roles`, `admin`, `companyAccess`, `companies`, `market` (tracked dashboard types: `TrackedRow`, `MoversResponse`, `TrackedSummary`, `ExclusionReason`…), `marketIntelligence`, `analysis`, `stocks` (intraday), `trading`, `news`, `crawler`, `dashboard`, `exports`.
- `contexts/AuthContext.tsx` — login/logout, current user, permissions, company access.
- `hooks/` — `usePermissions`, `useDashboardData`, `useLiveRefresh`, `useTheme` (light/dark).
- `types/` — shared TS types (`index.ts`, `company.ts`, `crawl.ts`).
- `components/`
  - `layout/` — `Layout`, `Sidebar` (permission-filtered nav), `Header`, `MarketTicker`.
  - `charts/` — `KlinePriceChart.tsx` & `TradingChart.tsx` (klinecharts candlesticks + volume + indicators), `IndicatorPicker`, `registryIndicators.ts` (maps backend indicator registry to the chart), `customIndicators.ts`, `RangeBar`, `chartRanges.ts`.
  - `dashboard/` — role dashboard cards (`RoleDashboard`, `dashboardConfig.ts`, `TopStocks`, `LatestNews`, `MarketOverviewChart`, …).
  - `market/` — `BasketChart`, `format.ts` (`formatPrice`, `formatPct`, `formatNprCompact` (Lakh/Crore), `changeTone`, `formatTradeDate`).
  - `market-intelligence/` — `MarketBreadthWidget`, `MarketHeatmap`, `MarketRankings`.
  - `analysis/` — `NewsMarketReaction`, `NewsSentimentScatter`, `VolumeAnomalyChart`.
  - `landing/` — `HeroIllustration`, `ParticleWave`, `LandingNews`.
  - `common/` — `Badge`, `EmptyState`, `LoadingSkeleton`, `PageHeader`, `PermissionGate`, `Sparkline`, `NewsImage`; `companies/CompanyLogo`; `brokers/BrokerAvatar|BrokerBadge`; `UserCompanyAccess.tsx`; `ThemeToggle`.
- `pages/` (route → file):
  | Route | Page | Notes |
  |---|---|---|
  | `/` | `LandingPage.tsx` | public marketing page; features, latest news, how it works, access levels, FAQ |
  | `/login`, `/register` | `LoginPage.tsx`, `RegistrationPage.tsx` | |
  | `/dashboard` | `Dashboard.tsx` → role dashboard | |
  | `/market` | `Market.tsx` | market intelligence widgets |
  | `/tracked` | `TrackedCompanies.tsx` | tracked summary tiles, **gainers/losers tables** (period tabs 1/5/20 sessions, "Top Gainers"-style cards), top turnover/volume/transactions, basket index, dividends, company drawer (signals, brokers, news), watchlist stars |
  | `/companies` | `admin/CompaniesPage.tsx` | company CRUD + track toggle |
  | `/companies/:symbol` | `StockDetail.tsx` | candlestick chart, indicators, intraday, floorsheet, news |
  | `/company-analysis` | `CompanyAnalysisDashboard.tsx` | VWAP, pressure, anomalies, news reaction |
  | `/broker-analysis`, `/broker-analysis/:brokerId` | `BrokerAnalysisPage.tsx` | |
  | `/watchlist`, `/watchlist-comparison` | `WatchlistPage.tsx`, `WatchlistComparison.tsx` | |
  | `/news`, `/news/:id` | `News.tsx`, `NewsDetail.tsx` | tags, confidence, manual correction |
  | `/crawl` | `CrawlerStatus.tsx` | crawl runs, trigger/retry/cancel |
  | `/reports` | `ExportPage.tsx` | CSV/XLSX/PDF exports |
  | `/users` | `admin/UserManagementPage.tsx` (largest file, ~3,100 lines) | users, roles, company access |
  | `/roles-permissions` | `admin/RolesPermissionPage.tsx` | permission matrix |
  | `/admin/*`, `/analyst/*` | redirects to the routes above | |
  - Not routed yet (WIP): `TrackedMoverCards.tsx`, `TrackedMoversPage.tsx` (use `/api/market-data/movers/tracked/…`). `AnalystDashboard.tsx`/`ViewerDashboard.tsx` are 3-line stubs; `ReportsComingSoon.tsx`, `ForbiddenPage.tsx`, `NotFound.tsx`.

---

## 8. Running locally

```powershell
# Backend (from Backend/)
python -m venv venv; venv\Scripts\pip install -r requirements.txt
copy ..\.env.example ..\.env      # set DB_*, SECRET_KEY
venv\Scripts\python manage.py migrate
venv\Scripts\python manage.py seed_companies
venv\Scripts\python manage.py seed_admin
venv\Scripts\python manage.py runserver

# Celery (needs Redis)
venv\Scripts\celery -A config worker --pool=solo --queues=crawling -l info
venv\Scripts\celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler

# Frontend (from frontend/)
npm install; npm run dev

# Tests (from Backend/)
venv\Scripts\python -m pytest apps/market_data/test_movers.py -q
venv\Scripts\python manage.py check
# Frontend type-check
npx tsc -b --noEmit
```
Or everything with Docker: `docker compose up --build`.

---

## 9. Conventions to follow when changing code

- Only `source="crawled"` prices in any calculation; label everything "tracked companies", not "NEPSE market".
- Never fill gaps with fake values; show empty/“—”/warning states and say where data comes from (provenance).
- Session change / gainers / losers come **only** from `apps/market_data/services/movers.py` — reuse it, don't re-implement.
- Trading days: use `trading_calendar` / `trading_days` services, never hardcode weekdays.
- Permissions: check with `HasAppPermission` + `company_access` helpers on the backend; `PermissionGate` / `usePermissions` on the frontend.
- Manual news tags (`is_manual=True`) are never overwritten by automatic categorisation; every manual change writes a `CategorizationCorrection`.
- Frontend styling: Tailwind with the project tokens (`text-up`, `text-down`, `bg-bg-elevated`, `text-text-muted`, `card` class); numbers in `font-mono`; amounts formatted with `components/market/format.ts`.
- Code style: match surrounding code; short comments explaining *why*.

---

## 10. Known issues / work in progress (as of 2026-10-12)

1. **Partial crawls**: a `trading_data` run limited with `-a symbols=` can leave a date with only some companies. The movers API now returns a `warning` and buckets those companies as `missing_price`; fix by re-crawling the missing symbols (`update_or_create` makes it safe). 9 Oct 2026 was fixed this way.
2. **Crawl reliability**: of 635 `CrawlRun` rows, 314 success, 274 failed, 28 cancelled (recent runs mostly succeed). A standalone `scrapy crawl ...` is recorded by `CrawlRunPipeline` with the default `crawl_type="news"` even for price crawls, so filter by `source`/spider name rather than `crawl_type` when auditing.
3. **WIP live prices**: `Company.ltp/previous_close/prices_updated_at` (uncommitted migration `companies/0007…`) and `apps/companies/update_prices.py` (needs `nepse_data_api`, must move to `management/commands/` and import `apps.companies.models`).
4. **Unrouted pages**: `TrackedMoverCards.tsx`, `TrackedMoversPage.tsx` and their endpoints exist but are not linked in `App.tsx`.
5. **Test drift**: `test_movers.py::MultiSessionTests::test_twenty_sessions` expects label "20 sessions" but `PERIODS` now labels it "1 month".
6. Legacy/duplicate code: `crawlers/utils/` vs `crawlers/crawlers/utils/`; empty placeholder services in `apps/news/services/`; some duplicate URL aliases in `companies/urls.py`; legacy `companies/top-gainers` uses `Company.ltp` rather than `movers.py`.
7. Floorsheet `trade_time` exists only for days loaded from ShareHub; ShareSansar floorsheets have no times, so intraday candles exist only for ShareHub-synced days.
