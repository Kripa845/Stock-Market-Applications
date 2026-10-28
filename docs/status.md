# Status

Known problems and unfinished work. Last checked against the code on **2026-10-28**. Remove an entry when it is fixed, and add new ones with the date.

## Failing tests (5 of 888, `pytest -q` on 2026-10-28)

| Test | Failure | Likely cause |
|---|---|---|
| `market_data/tests/test_movers.py::MultiSessionTests::test_twenty_sessions` | `'1 month' != '20 sessions'` | Test is stale: `PERIODS` now labels `20S` "1 month". |
| `analysis/tests/test_broker_api.py::…test_broker_list_includes_directory_and_unlisted_brokers_with_window_totals` | `'22000' != '22000.0000'` | Decimal formatting changed in the broker list response. Decide which format the frontend expects, then fix the test or the serializer. |
| `analysis/tests/test_broker_api.py::…test_broker_list_window_counts_back_from_latest_session` | `'1000' != '1000.0000'` | Same as above. |
| `market_data/tests/test_market_stats.py::PublicSnapshotRemovedTests::test_no_unauthenticated_price_endpoint` | `200 != 404` | The test says crawled prices must not be served to anonymous visitors, but `/api/market/public/snapshot/` still exists with `AllowAny`: it serves the landing page's ranked movers / turnover for the latest session (`public/chart/`, the NEPSE index chart, is public too). **Decide whether the public endpoints stay**, then remove either them or the test. |
| `market_indices/tests/test_sharesansar_indices.py::ResyncFallbackTests::test_resync_falls_back_to_sharesansar_when_nepse_fails` | `IndexDaily.DoesNotExist` | The ShareSansar fallback didn't write a row in the test. Not investigated. |

## Data gaps to watch

* **Partial-symbol price crawls.** `scrapy crawl trading_data -a symbols=…` can leave a date with only some companies. The movers API warns and buckets the rest as `missing_price`. Fix by re-crawling the missing symbols.
* **Floorsheet history.** ShareSansar serves only the current session. Past days come only from ShareHub (`backfill_sharehub_floorsheet`), back to Oct 2023. Broker Explorer / Acc-Dist totals cover only the sessions loaded.
* **Trade times.** `FloorsheetTransaction.trade_time` and intraday candles exist only for ShareHub-loaded days.
* **Index feed mid-session.** Today's NEPSE index row reads close 0 / −100% until the close. Never store it.
* **`TradingHoliday` is empty** (2026-10-28). Holidays are not crawled; enter them in the admin. Until then the market calendar shows closed weekdays (e.g. Dashain/Tihar, 2026-10-19 → 10-23) as "No session".
* **NEPSE index history** starts 2025-10-12, so earlier calendar months show no index figures. `sync_market_indices --since …` can backfill.
* **Public issues without units** (e.g. NRB Citizens Savings Bonds) can't be keyed and are skipped by `ipo_issues` (logged).

## Known quirks

* Standalone `scrapy crawl …` runs create a `CrawlRun` with the default `crawl_type="news"` whatever the spider is (`crawlers/crawlers/pipelines.py`, `CrawlRunPipeline`). Filter by `source` when auditing crawl history.
* `seed_admin` creates a user with hardcoded credentials and the invalid email `admin@.com`. Change them after first login, or make the command read them from env.
* `requirements.txt` pins `Scrapy==2.12.0`, but the local venv has 2.18.0 (2026-10-28). On ≥ 2.13 a spider must define `async def start()` (spiders without it send no requests), and pipelines log deprecation warnings for `open_spider(spider)` / returned Deferreds. Align the pin with what is installed.
* `BROKER_*` and `NEPSE_CLIENT_REUSE_SECONDS` settings are read from the environment but are missing from `.env.example`.
* `Backend/crawlers/floorsheet.json` and `trading_data.json` are tracked in git and change whenever a crawl writes a feed file. They should probably be gitignored.

## Unfinished / unused code

* `merolagani` and `nepalipaisa` spiders exist but are not in `runner.py` → `NEWS_SPIDERS`, so they never run on schedule (probably intentional, after commit `2ab998e` "Removing some sources").
* `apps/news/services/embedding_classifier.py`, `llm_classifier.py`, `ner_classifier.py`: empty placeholders.
* `Backend/crawlers/utils/` and `Backend/crawlers/base/client.py`: older copies. Spiders import `crawlers.utils` (the inner `crawlers/crawlers/utils/`), and nothing imports these. Likely safe to delete.
* `backfill_floorsheet` re-crawls ShareSansar for a date range, but ShareSansar serves only the current session, so it probably can't fill past days. Use `backfill_sharehub_floorsheet`. Not verified against the live site.
* Frontend: `pages/AnalystDashboard.tsx` and `ViewerDashboard.tsx` are 3-line stubs and not routed. `pages/ReportsComingSoon.tsx` is not imported anywhere. `pages/test.txt` is a stray file.
* URL aliases kept for old links: `/api/admin/crawl-runs/` = `/api/crawler-runs/`, `/api/reports/` = `/api/dashboard/`, `/api/admin/users/` duplicates `/api/users/admin/users/`.

## Resolved since the 2026-10-12 snapshot

* Live prices (`Company.ltp` etc.) are implemented: `market_data/services/live_prices.py`, `update_live_prices` every 2 min in session.
* Legacy `companies/top-gainers` / `top-losers` now use `movers.py`.
* `TrackedMoverCards` / `TrackedMoversPage` were replaced by `TopMoversPage` (`/market/gainers`, `/market/losers`).
* Per-stock Broker Distribution page removed. `/brokers-distribution` redirects to `/broker-acc-dist`.
