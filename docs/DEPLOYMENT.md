# Deployment

**StockScope is not deployed.** It runs on one machine: natively on the Windows dev machine, or with `docker compose`. There is no CI, no production host and no infrastructure-as-code in the repo. `Backend/Dockerfile` comments mention three "Render" services (web / worker / beat), but there is no Render config; treat that as an unused plan.

This page covers how to run it, first-time data loading, environment variables and the beat schedule. Data repair and backfills: [DATA_SOURCES.md](DATA_SOURCES.md#backfills).

## Processes

| Process | Command | Notes |
|---|---|---|
| PostgreSQL 16 | n/a | One database for everything. |
| Redis 7 | n/a | Celery broker (`/0`) and result backend (`/1`); also holds the live-feed circuit breakers. |
| Web | `manage.py runserver` (dev and compose) / `gunicorn config.wsgi:application --workers 2 --timeout 120` (Dockerfile default `CMD`) | Serves `/api/` and the Django admin. |
| Worker | `celery -A config worker --pool=solo --queues=crawling` | Must listen on `crawling`: it is `CELERY_TASK_DEFAULT_QUEUE`, and crawler / news tasks route there. Runs spiders as subprocesses. |
| Beat | `celery -A config beat --scheduler django_celery_beat.schedulers:DatabaseScheduler` | Exactly one beat process. |
| Frontend | `npm run dev` (Vite, :5173) / nginx serving `dist/` (compose, :3000) | `VITE_API_BASE_URL` is baked in at build time. |

## Docker Compose

`docker-compose.yml` defines `db`, `redis`, `backend`, `worker`, `beat`, `frontend`.

```powershell
copy .env.example .env           # set SECRET_KEY, DB_PASSWORD
docker compose up --build
```

* `backend` runs `migrate --noinput` and then **`runserver 0.0.0.0:8000`**, with `./Backend` mounted into `/app` for live reload. Worker and beat mount it too. This is a development setup.
* `db` and `redis` have health checks; backend / worker / beat wait for them. Data lives in the `postgres_data` and `redis_data` volumes.
* Compose overrides `DB_HOST=db` and the Redis URLs to the `redis` service.
* `frontend` is a two-stage build (`node:20-alpine` → `nginx:1.27-alpine`, `frontend/nginx.conf`): SPA fallback to `index.html`, gzip, 1-year cache on `/assets/`. nginx does **not** proxy `/api`; the browser calls the backend port directly.
* Backend image: `python:3.12-slim`, runs `collectstatic` at build time with a placeholder `SECRET_KEY`.

If it were ever run beyond localhost (TODO: confirm if planned), at least: drop the source mounts, use gunicorn instead of `runserver`, set `DEBUG=False`, a real `SECRET_KEY` and `ALLOWED_HOSTS`, put TLS in front, and see [SECURITY.md](SECURITY.md).

## Native (Windows)

From `Backend/`, with Postgres and Redis running locally:

```powershell
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python manage.py migrate
venv\Scripts\python manage.py runserver
venv\Scripts\celery -A config worker --pool=solo --queues=crawling -l info
venv\Scripts\celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

Frontend from `frontend/`: `npm install`, `npm run dev`.

Note: `requirements.txt` pins `Scrapy==2.12.0` but the local venv has 2.18.0 (see [status.md](status.md)).

## First-time setup

Run once after `migrate` (inside the backend container with `docker compose exec backend python manage.py …`, or `venv\Scripts\python manage.py …`). Each command is idempotent.

1. `seed_companies`: creates the tracked companies.
2. `seed_admin`: creates admin `admin1` / `Admin@123`. **Change the password**; re-running resets it.
3. `seed_market_indices`: NEPSE plus 13 sub-indices.
4. `import_stock_sectors data/stock_sectors.csv`: symbol → sector for every listed stock.
5. `import_brokers data/brokers.csv`, then `sync_broker_directory`.
6. `sync_listed_shares`: listed shares for market cap.
7. Price history (from `Backend/crawlers/`): `..\venv\Scripts\python -m scrapy crawl trading_data -a window_days=300`.
8. Floorsheet history: `backfill_sharehub_floorsheet --from YYYY-MM-DD` in chunks ([DATA_SOURCES.md](DATA_SOURCES.md#backfills)).
9. Derived data: `backfill_price_fields`, `backfill_market_analysis`, `backfill_market_intelligence`, `sync_market_indices --since YYYY-MM-DD`.
10. Trading holidays: Django admin → Trading holidays (not crawled).

## Environment variables

Read in `Backend/config/settings.py` with `os.getenv`; template in `.env.example` (repo root). Defaults are what `settings.py` uses when the variable is unset.

| Variable | Default in settings.py | Notes |
|---|---|---|
| `SECRET_KEY` | `django-insecure-change-me-in-production` | Always set it. The app starts with the insecure default. |
| `DEBUG` | `False` | `.env.example` sets `True` for development. |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,testserver` | Comma-separated. |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | `stockmarket`, `postgres`, empty, `localhost`, `5432` | `.env.example` uses `DB_NAME=stockscope`. |
| `DB_CONN_MAX_AGE` | `60` | Seconds. |
| `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | `redis://localhost:6379/0`, `/0`, `/1` | |
| `FRONTEND_URL` | `http://localhost:5173` | Added to `CORS_ALLOWED_ORIGINS` (with localhost :5173, :5174, :3000). |
| `CORS_ALLOW_ALL_ORIGINS` | `False` | |
| `AUTH_THROTTLE_RATE`, `PUBLIC_THROTTLE_RATE` | `10/min`, `60/min` | Login / register, and public endpoints. |
| `VITE_API_BASE_URL` | `http://localhost:8000/api` (build arg) | Frontend; `api/client.ts` falls back to `http://127.0.0.1:8000/api`. |
| `BACKEND_PORT`, `FRONTEND_PORT` | `8000`, `3000` | Compose only. |
| `CATEGORIZATION_*`, `SENTIMENT_METHOD` | see `.env.example` | [news-categorization](features/news-categorization.md). |
| `BROKER_SIGNAL_ACCUMULATION_RATIO`, `BROKER_SIGNAL_DISTRIBUTION_RATIO`, `BROKER_EXCLUDE_SELF_TRADES`, `BROKER_ACCUMULATION_CACHE_SECONDS` | `1.2`, `0.8`, `False`, `3600` | Not in `.env.example`. [broker-accumulation](features/broker-accumulation.md). |
| `NEPSE_CLIENT_REUSE_SECONDS` | `900` | How long a logged-in NEPSE client is reused. Not in `.env.example`. |

## Celery beat schedule

Source of truth: `CELERY_BEAT_SCHEDULE` in `config/settings.py`. Times are Asia/Kathmandu (`CELERY_TIMEZONE`). "Trading days" = `TRADING_DAYS_CRONTAB`, built from `NEPSE_TRADING_WEEKDAYS` (Mon–Fri since 2026-04-06). Tasks also skip `TradingHoliday` dates themselves.

| When | Task | What |
|---|---|---|
| 08:30 daily | `crawler_runs.tasks.crawl_ipo_issues` | `ipo_issues` spider → `IpoIssue` |
| Every 2 min 11:00–14:58, plus 15:00/05/10 (trading days) | `market_data.tasks.update_live_prices` | NEPSE → `Company.ltp` etc. |
| Every 5 min 11:00–14:55, plus 15:00/05 (trading days) | `floorsheet.tasks.build_intraday_candles_live` | ShareHub trades → `IntradayCandle` |
| Every 5 min 11:00–14:55, plus 15:00–15:15 (trading days) | `market_indices.tasks.snapshot_live_index` | `IndexIntradayPoint` |
| 15:15, 15:45, 18:30 (trading days) | `market_indices.tasks.sync_indices_from_nepse` | `IndexDaily` (evening run picks up late corrections) |
| 15:30 (trading days) | `floorsheet.tasks.finalize_intraday_candles` | Final candle rebuild |
| 16:00 (trading days) | `market_indices.tasks.verify_index_replication` | `IndexCheck` |
| 18:00 (trading days) | `crawler_runs.tasks.crawl_daily_prices` | `trading_data` → `DailyPrice`, then chain: price fields → analysis → support / resistance |
| 18:10 (trading days) | `market_indices.tasks.crawl_market_wide` | `market_stocks` spider → `MarketStockDaily` |
| 18:15 (trading days) | `crawler_runs.tasks.crawl_floorsheet` | ShareSansar floorsheet, latest session only |
| 18:45 (trading days) | `analysis.tasks.rebuild_all_analysis` | Again, after the floorsheet |
| 19:00 daily | `market_intelligence.tasks.build_daily_market_intelligence` | Breadth, basket index, technicals, sector rotation |
| 19:15 (trading days) | `market_intelligence.tasks.compute_support_resistance_task` | Fallback if the 18:00 chain failed |
| 19:30 daily | `crawler_runs.tasks.crawl_dividends` | Dividends, whole market |
| 19:45 daily | `reports.tasks.crawl_quarterly_reports` | nepsetrading.com |
| Hourly :00 | `crawler_runs.tasks.crawl_all_news` | `NEWS_SPIDERS` |
| Every 10 min | `news.tasks.categorize_unprocessed_news_task` | Tag new articles |
| Every 2 h at :30 | `crawler_runs.tasks.recover_stale_crawls` | Mark runs stuck > 90 min as failed |
| Saturday 20:00 | `crawler_runs.tasks.crawl_brokers` | Broker list |

Tasks serialise as JSON only, `CELERY_TASK_ACKS_LATE = True` (a crashed worker's task is re-queued) and `CELERY_WORKER_PREFETCH_MULTIPLIER = 1`.

## Health checks

* **Crawl** page (`/crawl`) or `GET /api/crawler-runs/`: recent runs and failures.
* `manage.py check_index_feed`: whether worker, beat and live index ticks are alive.
* `LiveFeedStatus`: last successful live-price save.
* Logs: worker and beat stdout. `Backend/crawlers/crawl_log.txt` is an old Scrapy log tracked in git, not a live log.

## Manual crawls

* UI: **Crawl** page triggers, retries and cancels runs (recorded as `CrawlRun`).
* CLI: `manage.py run_crawl --type news|prices|floorsheet|all` or `run_crawl --spider <name>`.
* Scrapy directly from `Backend/crawlers/`: `..\venv\Scripts\python -m scrapy crawl <spider> [-a key=value]`. These runs record `crawl_type="news"` whatever the spider; filter `CrawlRun` by `source`.
