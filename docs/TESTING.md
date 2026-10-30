# Testing

## Running

Backend, from `Backend/`:

```powershell
venv\Scripts\python -m pytest -q                                          # everything, ~3 min
venv\Scripts\python -m pytest apps/analysis/tests/test_broker_accumulation.py
venv\Scripts\python -m pytest apps/market_data/tests/test_movers.py -k test_name
```

* `Backend/pytest.ini` sets `DJANGO_SETTINGS_MODULE = config.settings_test` and collects `tests.py` and `test_*.py`.
* `config/settings_test.py` imports the normal settings, then switches to **in-memory SQLite**, raises the `auth` / `public` throttles to 10000/min (throttling has its own test) and sets `NEPSE_CLIENT_REUSE_SECONDS = 0` so a cached NEPSE client can't leak mocks between tests. Postgres and Redis are **not** needed.
* No network: tests that touch NEPSE, ShareHub or sites use mocks / fixture HTML.

Frontend, from `frontend/`: there are **no frontend tests**. The only check is the type-check:

```powershell
npx tsc --noEmit -p tsconfig.app.json   # not `-p .`: the root tsconfig has files: [] and checks nothing
```

`npm run lint` (oxlint) exists but is blocked on the dev machine by Windows Smart App Control.

**There is no CI.** Run pytest and the type-check before committing.

## Current state (2026-10-30)

**1017 tests: 1012 pass, 5 fail.** The failures predate the current work; details and the decision each one needs are in [status.md](status.md):

| Test | Cause |
|---|---|
| `analysis/tests/test_broker_api.py::…window_totals` and `…counts_back_from_latest_session` | Decimal formatting (`'22000'` vs `'22000.0000'`). Decide the response number format ([API.md](API.md#conventions)). |
| `market_data/tests/test_market_stats.py::PublicSnapshotRemovedTests::test_no_unauthenticated_price_endpoint` | Public market endpoints still exist. Decide whether they stay. |
| `market_data/tests/test_movers.py::MultiSessionTests::test_twenty_sessions` | Stale label: `20S` is now "1 month". |
| `market_indices/tests/test_sharesansar_indices.py::ResyncFallbackTests::…` | ShareSansar fallback wrote no `IndexDaily` row in the test. Not investigated. |

## What's covered

Tests per app (collected with `pytest --collect-only`):

| App | Tests | Main files |
|---|---|---|
| `analysis` | 189 | broker accumulation, broker position, Acc/Dist, broker API, floorsheet grid, VWAP, pressure, volume baseline |
| `market_intelligence` | 168 | `test_indicator_library.py` (123), technicals, snapshots, support / resistance, API |
| `market_data` | 153 | movers (32), trading calendar, live prices, feed resilience, heatmap, market stats, watchlists, price source |
| `news` | 118 | sentiment, categorization, API, BS dates, article images, `test_no_synthetic_data.py` |
| `market_calendar` | 79 | calendar, day view, weekday summary, month summary, monthly returns |
| `users` | 78 | permission dependencies (39), RBAC matrix, users / auth / throttling |
| `reports` | 72 | quarterly reports, dividends (+ spider parsing), IPO issues (+ spider), nepsetrading |
| `market_indices` | 70 | NEPSE indices, ShareSansar fallback, index replication / verification, technicals |
| `crawler_runs` | 39 | `test_crawler_runs.py` (crawl runs, triggering, spider lists) |
| `floorsheet` | 39 | intraday candles, intraday, broker directory, broker import |
| `companies` | 12 | companies API, tracked selection |
| `dashboard` | 0 | none |

Crawler code tested directly from `apps/*/tests`: `TradingDataSpider` and `TradingDataPipeline`, `BrokersSpider` and `BrokerPipeline`, the `dividends` and `ipo_issues` spiders' parsers, `market_wide_pipeline`, and `crawlers/crawlers/utils/dates.py`.

## Gaps

* **No frontend tests** at all (components, hooks, permission routing).
* **`dashboard` app**: no tests.
* **Spiders without tests**: `floorsheet`, the news spiders (`sharesansar`, `bizmandu`, `nepsealpha`, `arthakhabar`, `fiscalnepal`), `market_stocks`. Their parsers break silently when a site changes.
* **No coverage measurement**: `pytest-cov` is not installed; the table above counts tests, not lines.
* **SQLite vs Postgres**: tests run on SQLite, production-like runs on Postgres. Postgres-only behaviour (e.g. `Ln` / float casts in `movers.py` SQL, `bulk_create` conflict handling) is not exercised against Postgres.

## Conventions

* Django `TestCase` classes (114 of them); one file per feature: `apps/<app>/tests/test_<feature>.py`.
* External calls are patched with `unittest.mock` (`@patch`, `MagicMock`).
* **Never load the sentence-transformers model in tests**: stub it like `FakeEmbeddingModel` in `apps/news/tests/test_news_api.py` (the dev machine blocks the native binaries, and it is slow).
* Build fixtures with real-looking rows marked `source="crawled"`; tests such as `test_no_synthetic_data.py` and `test_price_source.py` check that synthetic rows never reach outputs.
* When fixing behaviour that a stale test encodes, fix the test in the same change and say why.
