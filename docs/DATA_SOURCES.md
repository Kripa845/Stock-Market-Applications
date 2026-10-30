# Data sources

Where every dataset comes from, how often, how politely, and what happens when a source fails. None of the sources is an official or paid API: they are public websites and the unofficial NEPSE client. That is fine for this personal app; check each site's terms before using it for anyone else. There are **no API keys** for any source.

## Overview

| Dataset | Source | Collector | Writes | When |
|---|---|---|---|---|
| Daily prices (tracked) | ShareSansar company price history | spider `trading_data` | `DailyPrice` (`source="crawled"`) | 18:00 trading days |
| Whole-market daily rows | ShareSansar "today share price" | spider `market_stocks` (file `spiders/merolagani.py`) → `market_wide_pipeline.py` | `MarketStockDaily` | 18:10 trading days |
| Floorsheet, latest session | ShareSansar | spider `floorsheet` | `FloorsheetTransaction` (no trade times) | 18:15 trading days |
| Floorsheet with trade times, history | ShareHub (`sharehubnepal.com`) JSON | `floorsheet/services/sharehub_floorsheet.py` | `FloorsheetTransaction`, `IntradayCandle` | every 5 min in session; backfills by hand |
| Live prices | NEPSE, via the `nepse-data-api` package | `market_data/services/live_prices.py` | `Company.ltp`, `session_*`, `LiveFeedStatus` | every 2 min in session |
| Index history and live index | NEPSE via `nepse-data-api`; **fallback** ShareSansar | `market_indices/services/nepse_indices.py`, `sharesansar_indices.py` | `IndexDaily`, `IndexIntradayPoint` | 15:15 / 15:45 / 18:30; every 5 min in session |
| Listed shares, index replication inputs | NEPSE via `nepse-data-api` (`NepseSource`) | `market_indices/services/index_replication.py`, `sync_listed_shares` | `CompanyDaily`, `Company.listed_shares` | by command / 16:00 verify |
| Dividends | ShareSansar; EPS from Merolagani | spider `dividends` → `dividend_pipeline.py` | `DividendAnnouncement`, `CompanyEarnings` | 19:30 daily |
| IPO / FPO / right / MF / debenture issues | ShareSansar "Existing Issues" | spider `ipo_issues` → `ipo_pipeline.py` | `IpoIssue` | 08:30 daily |
| Quarterly reports | nepsetrading.com | `reports/services/nepsetrading.py` | `QuarterlyReport`, `YearlyDPPS` | 19:45 daily |
| Broker list | nepseportfoliotracker.app | spider `brokers` | `Broker` | Saturday 20:00 |
| Broker directory details | ShareHub | `floorsheet/services/broker_directory.py` (`sync_broker_directory`) | `Broker` | by command |
| News | ShareSansar, Bizmandu, NepseAlpha, Arthakhabar, Fiscal Nepal | `NEWS_SPIDERS` in `crawlers/runner.py` (base: `spiders/base_news.py`) | `RawArticle`, `NewsArticle` | hourly |
| News images | `content.sharesansar.com` | `news/services/article_images.py` | `NewsArticle` | with news / `backfill_news_images` |
| Seed files | repo | management commands | sectors, brokers, logos | once |

Not scheduled (exist but not in any `runner.py` list): `nepalipaisa` (news) and `moneymitra_brokers`. Spiders are found by `name`, not file name: there is no `merolagani` spider, and `spiders/market_stocks.py` is an empty file.

## Politeness and rate limits

No source publishes a rate limit we know of (TODO: confirm). The app limits itself:

* **Scrapy** (`crawlers/crawlers/settings.py`): `ROBOTSTXT_OBEY = True`, `CONCURRENT_REQUESTS_PER_DOMAIN = 1`, `DOWNLOAD_DELAY = 2` (randomised), AutoThrottle (start 2 s, max 15 s, target concurrency 0.5), `RETRY_TIMES = 2`, `DOWNLOAD_TIMEOUT = 30`, a fixed `USER_AGENT`. The price, floorsheet and news spiders repeat these in `custom_settings` with AutoThrottle max 10 s and `CONCURRENT_REQUESTS = 1`.
* **One task at a time**: the Celery worker runs `--pool=solo --concurrency=1`, so two crawls never overlap.
* **ShareHub**: `request_floorsheet` is the only code that calls it. 30 s timeout, up to 4 attempts on network errors / other HTTP errors (sleeping 2, 4, 6, 8 s), **1 s pause between requests ("Do not lower it")**. HTTP 400 / 401 / 403 / 429 and non-JSON replies raise `ShareHubError` at once and stop the run instead of retrying in a loop.
* **NEPSE live**: 15 s timeout per call; one logged-in client reused for `NEPSE_CLIENT_REUSE_SECONDS` (900). Live index fetch retries 429 / 403 / 401 / 5xx / timeouts at most 2 times with exponential back-off (5 s × 2ⁿ + jitter).
* **nepsetrading.com**: 30 s timeout. **ShareSansar index fallback**: 20 s timeout.

## Failure handling and fallbacks

| Failure | What happens | Where |
|---|---|---|
| NEPSE live prices or index fail 3 runs in a row | **Circuit breaker** opens: NEPSE is not called for 30 min. State in Redis, shared by all workers. | `market_data/tasks.py`, `market_indices/tasks.py`, `market_data/services/circuit_breaker.py` |
| NEPSE index history fails | Falls back to ShareSansar; if that fails too the task returns `skipped` with both errors. | `market_indices/tasks.py::sync_indices_from_nepse` |
| NEPSE index row for today, mid-session | Close reads 0 / −100%; never stored. | `nepse_indices.py` |
| Session change % | ShareSansar's adjusted `source_change_pct` when present, else close-to-close. | `market_data/services/movers.py` |
| Spider hangs | Subprocess killed after its timeout (process group on Linux); `recover_stale_crawls` marks runs stuck > 90 min as failed. | `crawlers/runner.py`, `crawler_runs/tasks.py` |
| A page's layout changes | Spiders match tables and dates exactly (e.g. `market_stocks` by header text) and log an error instead of reading the wrong cells. | spider docstrings |
| Missing data | Shown as missing with `reason` / `action` / `warning`; never filled with estimates. | services, see [API.md](API.md#conventions) |

Celery retries: only the news categorization tasks retry, on `DatabaseError`, 3 times 10 s apart (`apps/news/tasks.py`). Crawl and analysis tasks don't retry; the next scheduled run tries again, or use **Retry** on the Crawl page.

## Caching

* **Django cache**: no `CACHES` setting, so each process has its own in-memory `LocMemCache`. API responses are cached 60 s (market, indices, dividends / quarterly report views), index verification 5 min, quarterly report figures 10 min, broker accumulation 1 h (`BROKER_ACCUMULATION_CACHE_SECONDS`), the month-by-month grid 1 h or until a new close. Keys include the user's company scope.
* **Redis**: Celery broker / results and the circuit-breaker counters only.
* **Database as cache**: nightly `DailyAnalysis`, `VolumeAnomaly` and market-intelligence snapshots are precomputed so pages don't recompute them.

## Time zones in source data

* Everything is converted to aware datetimes in Asia/Kathmandu (`NPT = ZoneInfo("Asia/Kathmandu")` in `live_prices.py`, `intraday_candles.py`, `sharehub_time.py`; `NEPAL_TZ` in `crawlers/crawlers/pipelines.py`).
* **ShareHub labels NPT times with `Z` (UTC).** Parse them with `floorsheet/services/sharehub_time.py`. Rows stored before that fix were 5 h 45 m late; `fix_sharehub_trade_times` repairs them.
* Some news sites publish Bikram Sambat dates; `crawlers/crawlers/utils/dates.py` converts them, `repair_news_dates` fixes old rows.

## Backfills

Commands from `Backend/` (`venv\Scripts\python manage.py …`) unless noted. All are idempotent.

| Data | Command | Notes |
|---|---|---|
| Prices | from `Backend/crawlers/`: `scrapy crawl trading_data -a window_days=N [-a symbols=…]` | A run with `symbols=` can leave a date with only some companies; movers then warns and buckets the rest as `missing_price`. Re-crawl the missing symbols. |
| Floorsheet history | `backfill_sharehub_floorsheet --from YYYY-MM-DD [--to …] [--symbols …]` | Back to Oct 2023, with trade times. Skips company-days that already have trades. About 1 GB total, so do it in chunks. |
| Floorsheet, missed day | same command for that date | ShareSansar serves only the current session. `backfill_floorsheet` re-crawls ShareSansar and probably can't fill past days. |
| Trade times | `fix_sharehub_trade_times [--dry-run]`, then `rebuild_intraday_candles` | Writes a JSON backup first; `--undo` restores it. |
| `DailyPrice.transactions` | `backfill_price_fields` | Counts from floorsheet. |
| Analysis / intelligence | `backfill_market_analysis`, `backfill_market_intelligence [--dry-run]` | |
| Indices | `sync_market_indices --since YYYY-MM-DD [--source sharesansar]` | `sharesansar` fills only sessions NEPSE lacks and pages through the whole range, so `--since 1997-07-01` backfills NEPSE's full history (from 1997-07-20; sub-indices start later). |
| Index replication | `replicate_index <snapshot / calibrate / verify / compute> --date D` | Run `calibrate` when `IndexCheck.needs_recalibration` is set. |
| News dates / images | `repair_news_dates`, `backfill_news_images` | |
| Quarterly reports | `crawl_quarterly_reports`, `import_quarterly_reports --file …` | [quarterly-report](features/quarterly-report.md) |
| Public issues | from `Backend/crawlers/`: `scrapy crawl ipo_issues -a pages=all` | Daily run reads the latest 2 pages (100 issues) per type; `pages=all` reads ~1,000 rows. |
| Trading holidays | Django admin → Trading holidays | Not crawled. |
