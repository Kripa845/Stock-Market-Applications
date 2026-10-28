# Operations

How to set the app up, what runs on its own, and how to repair missing data. Commands run from `Backend/` with `venv\Scripts\python manage.py …` unless noted.

## First-time setup

1. `copy .env.example .env` (repo root) and set `SECRET_KEY`, `DB_*`. The other defaults work locally. `docker-compose` overrides `DB_HOST` to `db`.
2. `migrate`
3. Reference data. Each command is idempotent:
   * `seed_companies`: creates the tracked companies.
   * `seed_admin`: creates the admin user with hardcoded default credentials (see the command). **Change the password after first login.**
   * `seed_market_indices`: NEPSE plus the 13 sub-indices.
   * `import_stock_sectors data/stock_sectors.csv`: symbol → sector for every listed stock.
   * `import_brokers data/brokers.csv`, then `sync_broker_directory` for websites, branches and so on.
   * `sync_listed_shares`: listed shares for market cap.
4. Price history: from `Backend/crawlers/`, `..\venv\Scripts\python -m scrapy crawl trading_data -a window_days=300`.
5. Floorsheet history: see [Backfills](#backfills).
6. Derived data: `backfill_price_fields`, `backfill_market_analysis`, `backfill_market_intelligence`, `sync_market_indices --since YYYY-MM-DD`.
7. Start the worker and beat (commands in `CLAUDE.md`). The worker must listen on the `crawling` queue: it is the default queue and some tasks route there explicitly.

Docker: `docker compose up --build` runs Postgres 16, Redis 7, backend (runs `migrate` on start), worker, beat and the nginx frontend. Steps 3–6 still have to be run once inside the backend container.

## Environment variables

All are in `.env.example`, with comments. Groups:

| Group | Variables |
|---|---|
| Django | `SECRET_KEY`, `DEBUG` (default False), `ALLOWED_HOSTS` |
| Database | `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_CONN_MAX_AGE` |
| Redis / Celery | `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` |
| Frontend / CORS | `VITE_API_BASE_URL` (default `http://localhost:8000/api`), `FRONTEND_URL`, `CORS_ALLOW_ALL_ORIGINS` |
| Throttling | `AUTH_THROTTLE_RATE` (10/min), `PUBLIC_THROTTLE_RATE` (60/min) |
| Docker ports | `BACKEND_PORT`, `FRONTEND_PORT` |
| News ML | `CATEGORIZATION_*`, `SENTIMENT_METHOD` (see [news-categorization](features/news-categorization.md)) |
| Broker signal | `BROKER_*` (see [broker-accumulation](features/broker-accumulation.md)), not in `.env.example` |
| NEPSE live feed | `NEPSE_CLIENT_REUSE_SECONDS` (default 900), not in `.env.example` |

## Celery beat schedule

Source of truth: `CELERY_BEAT_SCHEDULE` in `config/settings.py`. Times are Asia/Kathmandu. "Trading days" = the current NEPSE week (Mon–Fri, `TRADING_DAYS_CRONTAB`). Tasks also skip `TradingHoliday` dates themselves.

| When | Task | What |
|---|---|---|
| Every 2 min, 11:00–14:58, plus 15:00/05/10 (trading days) | `market_data.tasks.update_live_prices` | NEPSE live feed → `Company.ltp` etc. |
| Every 5 min, 11:00–14:55, plus 15:00/05 (trading days) | `floorsheet.tasks.build_intraday_candles_live` | ShareHub floorsheet with times → `IntradayCandle` |
| Every 5 min, 11:00–14:55, plus 15:00–15:15 (trading days) | `market_indices.tasks.snapshot_live_index` | `IndexIntradayPoint` ticks |
| 15:15, 15:45, 18:30 (trading days) | `market_indices.tasks.sync_indices_from_nepse` | `IndexDaily`. The evening re-sync picks up NEPSE's late turnover corrections. |
| 15:30 (trading days) | `floorsheet.tasks.finalize_intraday_candles` | Final candle rebuild |
| 16:00 (trading days) | `market_indices.tasks.verify_index_replication` | Reproduced vs. published index (`IndexCheck`) |
| 18:00 (trading days) | `crawler_runs.tasks.crawl_daily_prices` | `trading_data` spider → `DailyPrice` |
| 18:10 (trading days) | `market_indices.tasks.crawl_market_wide` | Whole-market daily rows |
| 18:15 (trading days) | `crawler_runs.tasks.crawl_floorsheet` | ShareSansar floorsheet, **latest session only** |
| 18:45 (trading days) | `analysis.tasks.rebuild_all_analysis` | `DailyAnalysis`, VWAP, anomalies |
| 19:00 daily | `market_intelligence.tasks.build_daily_market_intelligence` | Breadth, basket index, technicals, sector rotation |
| 19:15 (trading days) | `market_intelligence.tasks.compute_support_resistance_task` | Fallback in case the 18:00 chain failed |
| 19:30 daily | `crawler_runs.tasks.crawl_dividends` | Proposed dividends, whole market |
| 19:45 daily | `reports.tasks.crawl_quarterly_reports` | Latest quarterly reports (nepsetrading.com) |
| Hourly :00 | `crawler_runs.tasks.crawl_all_news` | All news spiders |
| Every 10 min | `news.tasks.categorize_unprocessed_news_task` | Tag new articles |
| Every 2 h :30 | `crawler_runs.tasks.recover_stale_crawls` | Mark runs stuck > 90 min as failed |
| Saturday 20:00 | `crawler_runs.tasks.crawl_brokers` | Broker list |

Beat uses `DatabaseScheduler`. Check that the worker, beat and live index ticks are alive with `check_index_feed`.

## Manual crawls

* From the UI: **Crawl** page (`/crawl`) triggers, retries and cancels runs, and records them as `CrawlRun`.
* From the CLI: `run_crawl --type news|prices|floorsheet|all` or `run_crawl --spider <name>`.
* Scrapy directly (from `Backend/crawlers/`): `..\venv\Scripts\python -m scrapy crawl trading_data -a symbols=NABIL,ADBL -a window_days=10`. These runs are recorded with `crawl_type="news"` whatever the spider is, so filter `CrawlRun` by `source`.

All pipelines upsert, so re-running is always safe.

## Backfills

| Data | Command | Notes |
|---|---|---|
| Prices | `scrapy crawl trading_data -a window_days=N [-a symbols=…]` | A run limited with `symbols=` can leave a date with only some companies. The movers API then warns and buckets the rest as `missing_price`. Re-crawl the missing symbols. |
| Floorsheet history | `backfill_sharehub_floorsheet --from YYYY-MM-DD [--to …] [--symbols …]` | ShareHub goes back to Oct 2023, with trade times. It skips company-days that already have trades, so it can be stopped and re-run. About 1 GB in total, so do it in chunks. |
| Floorsheet, missed day | Same command for that date | ShareSansar serves only the current session, so `crawl_floorsheet` can't recover a past day. |
| Trade times | `fix_sharehub_trade_times [--dry-run]`, then `rebuild_intraday_candles` | Fixes rows stored 5h45m late (ShareHub's `Z` timestamps are really NPT). Writes a JSON backup first, and `--undo` restores it. |
| `DailyPrice.transactions` | `backfill_price_fields` | Counts from floorsheet |
| Analysis / intelligence | `backfill_market_analysis`, `backfill_market_intelligence [--dry-run]` | Idempotent |
| Indices | `sync_market_indices --since YYYY-MM-DD [--source sharesansar]` | `sharesansar` fills only the sessions NEPSE lacks |
| Index replication | `replicate_index <snapshot / calibrate / verify / compute> --date D` | Index = market cap × K. Run `calibrate` when `IndexCheck.needs_recalibration` is set. |
| News dates | `repair_news_dates` | BS dates stored as Gregorian |
| Quarterly reports | `crawl_quarterly_reports`, `import_quarterly_reports --file …` | See [quarterly-report](features/quarterly-report.md) |

## Data rules for operators

* Never insert or keep made-up prices. `DailyPrice` rows not marked `source="crawled"` are ignored by analysis, but delete them rather than relabel them.
* Don't store today's `IndexDaily` row before the close (the feed reads close 0 / −100% mid-session).
* Backups / old dumps live in `Backend/data/backups/`. Nothing reads them at runtime.
