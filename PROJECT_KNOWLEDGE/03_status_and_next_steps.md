# StockScope: Project Knowledge (3/3): Decisions, Mistakes, Status, Next Steps, Learning

See 01 for structure and terms, 02 for code and setup. Snapshot **2026-10-30**.

---

## 7. DECISIONS MADE

| Chose | Rejected / instead of | Why |
|---|---|---|
| ~20 **tracked companies** only | Whole-market terminal | Focused research set; each extra company lengthens crawls (UNSURE: no other reason documented) |
| **Real crawled data only**; missing shown as "—"/warning | Mock, seeded, interpolated data | Owner's explicit rule; synthetic seed rows once polluted charts |
| Delete non-crawled prices rather than relabel them | Keeping them as "unverified" | They are random-walk fakes |
| **Unofficial sources** (NEPSE via nepse-data-api, ShareHub, ShareSansar, news sites) | Paid/official API (none exists) | Personal use; revisit only for a public launch. Don't suggest removing them |
| Polite crawling: robots.txt, 1 req/domain, 2 s delay; ShareHub 1 s pause | Faster crawling | The same IP feeds live data; a block would break it |
| Each spider in its **own subprocess** | Running Scrapy inside the worker | Killable on timeout |
| Worker `--pool=solo`, one queue `crawling` | Concurrent workers | Required on Windows; crawls never overlap |
| **Upsert** on natural keys | Plain inserts | Re-running is always safe |
| `Decimal` for money, float only for statistics | FloatField for prices | Exactness |
| Store AD dates, convert to BS on the backend only (`nepali_datetime`) | BS library in the frontend | One conversion path |
| TZ Asia/Kathmandu, `USE_TZ=True` | Naive datetimes | Beat times and "today" must match NEPSE |
| One movers definition (`movers.py`) | Per-page calculations | All pages agree |
| Indicators computed on request | Storing ~110 indicators | Avoid a huge derived table; `None` during warm-up, never 0 |
| Live-feed state in DB, circuit breaker in Redis | Django cache | Processes don't share LocMemCache |
| Floorsheet/reports models moved to new apps but keep `market_data_*` table names | Data migration | No data copy |
| Per-stock Broker Distribution page removed → Acc/Dist (`/brokers-distribution` redirects) | Two overlapping pages | Duplication |
| Candles switched from Recharts to **klinecharts** | Recharts candles | Better financial charts |
| News tagging: embeddings + keywords, NumPy, no vector DB; manual tags win | LLM/NER classifiers (empty placeholders) | ~20 companies is tiny; runs on CPU |
| Footprint: tick-rule estimate, odd lots and pre-open excluded, untimed days = 1 bar | Inventing trade times; using the official close as the bar close | Floorsheet has no aggressor flag; honesty about data |
| Broker position = running net from 0 | Calling it "holdings" | The floorsheet can't show holdings |
| Broker-activity max 8 stocks | Unlimited | Distinct colour-blind-safe colours |
| Docker nginx doesn't proxy `/api` | Proxying | Browser calls :8000 directly (simple local setup) |

---

## 8. MISTAKES & FIXES (and what NOT to do)

**Bugs hit and fixed**
- **Synthetic prices in charts:** pre-existing `DailyPrice` rows were given `source="unverified"` by migration 0004; they were seed random walks. Fix: `with_crawled_price`, crawled-only services, `test_no_synthetic_data.py`.
- **Index shows close 0 / −100%:** a mid-session NEPSE re-sync (2026-10-16) stored today's placeholder row. Fix: `close <= 0` = unfinished, in `_closing_index` and the ShareSansar `parse_row`.
- **Trade times 5 h 45 m late:** ShareHub labels NPT as `Z`. Fix: `sharehub_time.parse_sharehub_time`, repaired by `fix_sharehub_trade_times`.
- **Dividends spider returned 0 rows:** the full DataTables URL was > 2083 chars and Scrapy's `URLLENGTH_LIMIT` silently dropped it. Also `length > 50` returns an empty 202, and missing `columns[i][data]` causes HTTP 500. Fix: page by 50 and send only `columns[i][data]`.
- **Merolagani EPS placeholders** (`0.00 (FY:083-084, Q:5)`, `0.00 (FY:, Q:0)`, blank): treat them as no EPS.
- **ShareSansar dividend `status` (-1/0/1)** is book-closure timing, not SEBON approval.
- **Untimed floorsheet days (2026-10-08/09):** ShareHub's run stopped part-way and ShareSansar filled the rest without times. Fix: `fill_floorsheet_trade_times` (7,916 rows filled; backup in `Backend/backups/`).
- **Missing floorsheet day 2025-07-16** for 10 symbols: loaded (6,678 trades).
- **"Clean" frontend type-check that checked nothing:** `tsc -p .` uses the root tsconfig with `files: []`. Use `-p tsconfig.app.json`.
- **Windows Smart App Control** blocks the `regex` DLL (loaded by sentence-transformers) and oxlint's binary. Not fixable by reinstalling: stub the model in tests (`FakeEmbeddingModel`) and skip `npm run lint` locally.
- **SQLite integer division** in movers percentages: compute in float, cast back to numeric.

**Pitfalls still open:** see section 9.

**DO NOT (rules for a new AI)**
- Don't use `DailyPrice` rows unless `source="crawled"`. Don't mock, simulate, interpolate or back-fill numbers.
- Don't compute gainers/losers/session change anywhere except `movers.py`.
- Don't hardcode weekdays (the trading week changed on 2026-04-06); use `trading_days.py` / `trading_calendar.py`.
- Don't store today's NEPSE index row before the close.
- Don't use naive `datetime.now()` / `date.today()`; use `timezone.now()` / `timezone.localdate()`.
- Don't parse ShareHub times as UTC.
- Don't add `FloatField` for money; parse crawled numbers to `Decimal`.
- Don't add a per-company endpoint without `permission_key` + a company-access helper + a frontend `routePermissions.ts` rule (+ an `App.tsx` route and a `Sidebar.tsx` entry for a new page).
- Don't import "upward": `users, companies` → `market_data, floorsheet, reports, market_indices` → `analysis, market_intelligence, dashboard, market_calendar`.
- Don't put logic in views; use `services/`.
- Don't pass non-JSON arguments to Celery tasks.
- Don't lower crawl politeness (ShareHub 1 s pause, Scrapy 2 s delay, robots.txt).
- Don't overwrite manual news tags (`is_manual=True`).
- Don't load the real ML model in tests.
- Don't hardcode/log secrets; don't commit `.env` or DB dumps with users.
- Don't "fix" the 5 known failing tests without the owner's decision (section 9).
- Don't use `print` outside management commands; use `logging.getLogger(__name__)`.
- Don't look for spiders by file name: `spiders/merolagani.py` holds `market_stocks`, and `market_stocks.py` is empty.
- Don't use `backfill_floorsheet` for past days (ShareSansar serves only today); use `backfill_sharehub_floorsheet`.
- Don't forget: add a `docs/project-log.md` entry for every feature, and add unfinished items to `docs/status.md`.

---

## 9. CURRENT STATUS

**Done (committed):** crawling for prices, floorsheet, live prices, indices, dividends, IPOs, quarterly reports, brokers and news · RBAC with roles, custom roles and company access · market pages (movers, top activity, heatmap, Tracked Basket, indices + live ticks) · stock page (klinecharts + ~110 indicators, intraday, S/R, broker accumulation, news) · broker pages (list, top brokers, Acc/Dist) · dividends, quarterly report · news tagging + corrections · market calendar, weekday summary · exports (CSV/XLSX/PDF) · crawl admin page · docs.

**Also committed** (in `9664d90` / `e7a7ccf`, though `project-log.md` still says "uncommitted"): Broker Position / Activity (`/broker-position`), NEPSE Day-by-Day (`/market/day-by-day`), Month-by-Month (`/market/month-by-month`).

**Done but uncommitted (2026-10-30):**
- Floorsheet order-flow prep: `trade_filters.py`, `footprint.py`, `floorsheet_quality.py`, `trade_time_backfill.py`, commands `fill_floorsheet_trade_times`, `floorsheet_quality_report`, `tests/test_footprint.py` (untracked), plus edits to `docs/status.md`, `project-log.md`, `DATA_SOURCES.md`, `.gitignore`.

**Half-done**
- Footprint: the service exists, but there is **no API and no UI**.
- Candles: still include odd lots and pre-open fills (affects 12,964 of 262,773 1m candles). Whether to apply `trade_filters` is undecided.
- Candles for 2026-10-08/09 not rebuilt after trade-time repair.
- Quarterly reports: marked WIP in the log.
- Floorsheet history: only partly backfilled from ShareHub (available back to Oct 2023, ~1 GB). Owner doesn't know how far it's loaded; check with `floorsheet_quality_report` or the earliest `FloorsheetTransaction.date`.
- NEPSE index history starts 2025-10-12: the long backfill (`sync_market_indices --since 1997-07-01 --source sharesansar`) has **not** been run, so Month-by-Month shows only ~1 year.
- `TradingHoliday` is empty, so holidays show as "No session".

**Broken / failing (5 of ~1017–1032 tests)**
1. `test_movers.py::test_twenty_sessions`: stale label ('1 month' vs '20 sessions').
2–3. `test_broker_api.py` (two tests): `'22000'` vs `'22000.0000'`. The API number format is mixed (dict views send JSON numbers, serializers send strings). **Owner's tentative choice (2026-10-30): JSON numbers.** Confirm with the owner before changing serializers.
4. `test_market_stats.py::test_no_unauthenticated_price_endpoint`: public `/api/market/public/snapshot/` and `chart/` still exist. **Owner is undecided**, so leave both the endpoints and the test as they are.
5. `test_sharesansar_indices.py::test_resync_falls_back_to_sharesansar_when_nepse_fails`: not investigated.

**Known quirks / tech debt**
- Security: `seed_admin` hardcodes `admin1`/`Admin@123` and resets it on every run (email `admin@.com`). `Backend/data/backups/data.json` holds an old superuser hash (commit `7ca19b5`). Insecure `SECRET_KEY` fallback. JWT in localStorage; no server logout.
- Scrapy pin 2.12.0 vs installed 2.18.0 (≥2.13 needs `async def start()` in spiders; pipeline deprecation warnings).
- Standalone `scrapy crawl` records `CrawlRun.crawl_type="news"` for every spider.
- No `CACHES` setting, so gunicorn workers don't share cache.
- Naive `datetime.now()` in `reports/exports/{news,report,trading}.py`.
- `crawlers/floorsheet.json`, `trading_data.json`, `crawl_log.txt` are tracked in git.
- Dead code: `crawlers/utils/`, `crawlers/base/client.py`, empty `embedding_classifier.py`/`llm_classifier.py`/`ner_classifier.py`, frontend `AnalystDashboard.tsx`, `ViewerDashboard.tsx`, `ReportsComingSoon.tsx`, `pages/test.txt`.
- Unscheduled spiders: `nepalipaisa`, `moneymitra_brokers`.
- Partial-symbol price crawls leave dates with only some companies (movers warns).
- Public issues without units (e.g. NRB bonds) are skipped.
- No frontend tests; no tests for `dashboard`, the floorsheet/news/`market_stocks` spiders; tests run on SQLite, not Postgres.

---

## 10. NEXT STEPS (prioritised)

1. **Save the work:** run pytest + `tsc -p tsconfig.app.json`, then commit the untracked floorsheet files and doc edits; replace the `uncommitted` markers in `project-log.md` with hashes (`9664d90` / `e7a7ccf` for Broker Position, Day-by-Day and Month-by-Month).
2. **Data repair:** `rebuild_intraday_candles --from 2026-10-08 --to 2026-10-09`; run `floorsheet_quality_report`.
3. **Fix the decidable tests:** update the stale `20S` label test; move the broker-list serializer to JSON numbers (owner's tentative choice; confirm first) and update the two `test_broker_api.py` tests; investigate the ShareSansar fallback test. Leave the public-endpoint test until the owner decides.
4. **Security cleanup** (lower urgency: the owner has **no plans to deploy**, but `data.json` is still in git history): delete `Backend/data/backups/data.json` (and change that password if reused); make `seed_admin` read credentials from env and stop resetting; fail at startup on the default `SECRET_KEY` when `DEBUG=False`.
5. **Enter trading holidays** in Django admin (e.g. Dashain/Tihar 2026-10-19 → 10-23).
6. **Align Scrapy:** pin what's installed (2.18) and add `async def start()` to spiders, or downgrade the venv.
7. **Candle filters decision**, then **footprint API + UI** (permission key, company access, route, sidebar, log entry).
8. **Backfills:** find how far the floorsheet goes, then continue the ShareHub backfill in chunks; run the long NEPSE index backfill (`sync_market_indices --since 1997-07-01 --source sharesansar`).
9. **Housekeeping:** delete `StockScope_project_context.zip`; rename `spiders/merolagani.py` → `market_stocks.py`; delete dead code/stubs; gitignore feed JSONs and `crawl_log.txt`; add missing env vars to `.env.example`; fix `crawl_type` for standalone crawls; timezone-aware export headers; consider a shared `CACHES` (Redis).
10. **Tests:** spider parser tests (floorsheet, news, market_stocks), `dashboard` tests, a frontend smoke test.

---

## 11. LEARNING PATH (in order)

1. **Python basics + virtualenv/pip.** Search: "Python venv pip tutorial", "Python decimal module", "Python zoneinfo timezone".
2. **Stock market basics + NEPSE.** "how stock exchange works OHLC volume", "NEPSE floorsheet explained", "broker accumulation distribution", "book closure bonus share Nepal", "Bikram Sambat calendar".
3. **SQL + PostgreSQL.** "SQL joins group by tutorial", "PostgreSQL unique constraint upsert".
4. **Django.** "Django official tutorial polls", "Django ORM queryset annotate Exists OuterRef", "Django migrations", "Django USE_TZ timezone".
5. **Django REST Framework + JWT.** "DRF tutorial APIView", "DRF permissions custom BasePermission", "djangorestframework-simplejwt rotate refresh tokens".
6. **RBAC.** "role based access control design".
7. **Web scraping with Scrapy.** "Scrapy tutorial spider item pipeline", "Scrapy settings DOWNLOAD_DELAY AUTOTHROTTLE robots.txt", "scraping JSON APIs DataTables".
8. **Celery + Redis.** "Celery first steps Django", "celery beat crontab", "django-celery-beat DatabaseScheduler", "celery chain".
9. **Python subprocess + timeouts.** "python subprocess Popen timeout kill process group".
10. **Data analysis.** "pandas basics", "VWAP calculation", "z-score anomaly detection", "technical indicators RSI MACD Bollinger", "support resistance detection", "tick rule trade classification", "footprint chart order flow".
11. **NLP for tagging.** "sentence-transformers all-MiniLM-L6-v2", "cosine similarity embeddings", "regex word boundary lookbehind".
12. **TypeScript + React.** "TypeScript handbook", "React official tutorial hooks", "React Router v7".
13. **Frontend data + styling.** "TanStack Query useQuery", "axios interceptors refresh token", "Tailwind CSS utility classes", "Vite getting started".
14. **Charts.** "klinecharts candlestick", "recharts line chart".
15. **Testing.** "pytest-django TestCase", "unittest.mock patch".
16. **Docker.** "docker compose tutorial", "multi-stage Dockerfile nginx SPA".
17. **Security basics.** "Django deployment checklist", "JWT localStorage XSS risk", "git remove file from history".
