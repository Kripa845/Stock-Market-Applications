# Project log

A step-by-step record of how StockScope was built: what each feature added, where it lives, and what was left open. **Newest first.** Add an entry whenever a feature is added or changed in a way someone would want to find later. Bug-only fixes go in `docs/status.md` instead.

## How to add an entry

Copy this block to the top of **Log** and fill it in. Leave out lines that don't apply.

```markdown
### YYYY-MM-DD: <Feature name>  `<commit hash, or "uncommitted">`

**What:** one or two sentences, from the user's point of view.
**Backend:** services / models / migrations touched (`apps/<app>/services/<file>.py`).
**API:** `GET /api/...` (permission key `...`).
**Frontend:** route `/...`, page `pages/<Page>.tsx`, sidebar entry.
**Data:** which tables / crawls it reads; any backfill needed.
**Tests:** `apps/<app>/tests/test_<feature>.py`.
**Open:** what's unfinished or worth revisiting (also add it to `docs/status.md`).
```

Rules: keep each entry short, link to `docs/features/<feature>.md` for anything long, and once work marked `uncommitted` is committed, replace that marker with the commit hash.

## Log

### 2026-10-30: Broker Position, NEPSE Day-by-Day, Weekday summary rework  `uncommitted`

**What:** Broker Position shows one broker's running net (bought − sold) in one stock over 1D–1Y, plus a multi-stock view of one broker's activity. Day-by-Day shows one row per month (BS or AD) with one tile per session, coloured by the NEPSE index change.
**Backend:** `apps/analysis/services/broker_position.py`, `apps/market_calendar/services/month_summary.py`; changes to `calendar.py` and `weekday_summary.py`.
**API:** `GET /api/analysis/broker-position/?symbol=&broker=&range=`, `GET /api/analysis/broker-activity/?symbols=&broker=&range=` (up to 8 symbols), `GET /api/market-calendar/months/`.
**Frontend:** routes `/broker-position` (`pages/BrokerPositionPage.tsx`, `components/brokers/position/`) and `/market/day-by-day` (`pages/DayByDayPage.tsx`); `WeekdaySummaryPage` and `WeekToDateCard` updated.
**Data:** ranges count floorsheet sessions, so 1D/2D need ShareHub-loaded trade times. Day-by-Day needs NEPSE index history, which starts 2025-10-12.
**Tests:** `analysis/tests/test_broker_position.py`, `market_calendar/tests/test_month_summary.py`, `test_weekday_summary.py`.

### 2026-10-28 → 10-29: Market calendar, IPO issues, floorsheet summary, weekday summary  `14fd903` `45c62e2` `470d7f9` `6cc7719`

**What:** A market calendar page (traded / holiday / no-session days, per-day detail), public-issue (IPO) listings, a floorsheet summary, and a weekday-by-weekday performance page.
**Backend:** `apps/market_calendar/` (`services/calendar.py`, `weekday_summary.py`), `ipo_issues` crawl.
**Open:** `TradingHoliday` is empty, so holidays show as "No session"; issues without units are skipped (see `docs/status.md`).

### 2026-10-28: Docs reorganised, CLAUDE.md added  `a548650` `cd9bc88`

**What:** Added CLAUDE.md and split the docs into `status.md`, `data-model.md`, `api.md`, `operations.md` and `features/`. Outdated context files removed.

### 2026-10-26 → 10-28: Broker Accumulation / Distribution, quarterly reports, backend restructure  `e0c2f74` `6555da7` `7ca19b5` `7e00b98` `d83f1fd` `ed7a3b3`

**What:** Acc/Dist page ranking brokers by net buying per stock over session windows; quarterly reports (WIP); heatmap and admin dashboard changes. Mock data replaced with real endpoints. The per-stock Broker Distribution page was removed in favour of Acc/Dist (`/brokers-distribution` redirects).
**Backend:** new `floorsheet` and `reports` apps split out of the old layout.
**More:** `docs/features/broker-accumulation.md`, `docs/features/quarterly-report.md`.

### 2026-10-12 → 10-16: Index pages, dividends, technical chart and broker page fixes  `3fd3edd` `211d69e` `ac18168` `2ab998e`

**What:** NEPSE index and sub-index pages, a dividend page, technical chart UI fixes, Top Broker Stock page. Some news sources removed (merolagani / nepalipaisa no longer scheduled).

### 2026-10-01 → 10-09: Brokers crawler, logos, landing page, tracked companies  `5964e6b` `fc13148` `41a4b65` `6334c88` `992abef`

**What:** Broker directory crawler, company logos, public landing page, and the `TrackedCompany` model: the app covers only tracked companies from here on. News date fixes; repo cleanup.

### 2026-09-21 → 09-30: Behaviour analysis, reports, company access, KLineCharts  `82f2c7a` `192aab0` `ec423b4` `e2b7cdc` `593585a` `a135090`

**What:** Behaviour analysis and analyst dashboard, report/export features, per-user company access (`apps/users/company_access.py`). Candle charts moved from Recharts to klinecharts; Market Overview features.

### 2026-09-15 → 09-18: Admin, dynamic roles and permissions, dashboard, light theme  `3ccd78e` `e471eed` `3ddc72f` `efd12a5` `df15f56`

**What:** Admin page, registration with roles, dynamic roles/permissions (`HasAppPermission`, `routePermissions.ts`), first dashboard, Celery beat schedule changes, light theme.

### 2026-08-31 → 09-01: Crawling foundation and frontend  `fc93dfc` `0c12e48` `3d8a989` `622ea8f`

**What:** Scrapy crawlers for prices and floorsheets, first pass at news categorization, React frontend added.
