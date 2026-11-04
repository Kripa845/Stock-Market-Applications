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

### 2026-11-04: Stock details page and light-theme styling  `c143aab` + uncommitted styling

**What:** Added `/stocks/:symbol` with tracked-company selection, a crawled price chart, quote tiles, MASTER technical score, historical performance and quarterly valuation. The latest styling pass aligns the panels, labels and gauge with the shared light / dark theme colors. Details and calculation limits: [stock detail](features/stock-detail.md).
**Backend:** Quote, performance and beta services under `companies/` and `market_data/`; quarterly valuation from `reports/`; MASTER score from `analysis/services/master_score.py`; `Shareholding` and `MasterScore` models.
**API:** `/api/companies/<symbol>/quote/`, `/api/companies/<id>/performance/`, `/valuation/`, `/master-score/` (permissions in [API.md](API.md)).
**Frontend:** route `/stocks/:symbol`, `stock-detail/StockDetailsPage.tsx`, `Pricechart.tsx`, `Mastergauge.tsx`, `ui.tsx`, theme rules in `index.css`.
**Open:** historical metrics use unadjusted closes; stock-detail endpoint tests are not in place (see [status](status.md) and [testing](TESTING.md)).

### 2026-11-01: News provenance and de-duplication  `uncommitted`

**What:** Every article now records its source (`NewsSource`), exact source URL, the crawl run that inserted it and when a crawl last saw it. Re-running a collector never adds a row: articles are identified per source by `external_id` or normalised URL, edits update the row in place, and the same story on another portal is kept but linked (`duplicate_of`).
**Backend:** `news/services/ingest.py` (`ingest_article`, the only write path, used by `crawlers/pipelines.py::NewsPipeline`), `services/normalize.py`, `services/dedupe.py` + `manage.py dedupe_news`; models `NewsSource`, `ArticleLike`, `ArticleComment`; migrations `news/0009`–`0011` (0010 creates the 6 portals, maps spelling variants such as "FiscalNepal", recomputes hashes), `crawler_runs/0013` (`articles_duplicate`). `RawArticle.crawl_run` changed CASCADE → PROTECT.
**Data:** all 1,366 existing articles backfilled; no duplicates found. Checks in `apps/news/sql/verify_news_integrity.sql`. How to add a source: `apps/news/README.md`.
**Tests:** `news/tests/test_ingest.py`; fixtures use `news/tests/factories.py`.
**Open:** "also reported by" in the API/UI, likes/comments API, `external_id` in spiders (see `docs/status.md`).

### 2026-11-01: Stock Comparison page  `a3b5df3`

**What:** Pick 2–5 tracked companies (kept in `?symbols=`) and see summary cards, a 3-month trend chart (% from the first close), a metric table with the best P/E, P/B, ROE, EPS and yield highlighted, top buy / sell brokers and data notes. A missing figure shows "—" with the backend's reason.
**Frontend:** route `/compare` (`pages/StockComparisonPage.tsx`, rule `view_analysis`), `api/compare.ts`, `hooks/useCompare.ts`. The sidebar "Comparison" entry is now a group: Stock Comparison, Watchlist Comparison.
**Open:** on phone widths the app's sidebar stays open and leaves little room for the page (true of every page).

### 2026-11-01: Stock comparison backend + RSI / MACD on snapshots  `eb87a3a`

**What:** Compare 2–5 tracked companies side by side (price, size, valuation, dividend, technicals, top brokers). Every missing figure is `null` with a reason code, and there is a coverage report for all tracked companies. See [features/stock-comparison.md](features/stock-comparison.md).
**Backend:** new app `apps/comparison/` (`services/compare.py`, `services/coverage.py`); `market_intelligence/services/momentum.py` (Wilder RSI 14, MACD 12/26/9), filled at the end of `compute_company_technical_snapshots`; `market_data/services/price_adjustments.py` (sessions where prices are not adjusted for a bonus / right issue); migration `market_intelligence/0006_snapshot_rsi_macd`.
**API:** `GET /api/compare/?symbols=`, `compare/companies/?sector=`, `compare/coverage/` (`view_analysis` + company access).
**Data:** run `backfill_momentum_indicators` once (13,226 rows filled on 2026-11-01; a re-run writes 0). `comparison_coverage` prints the report.
**Tests:** `comparison/tests/test_compare.py` (20-company universe, ADBL reference at LTP 347), `market_intelligence/tests/test_momentum.py` (Wilder reference values).
**Open:** TTM EPS, YoY growth and PEG need quarterly history; prices are unadjusted (see `docs/status.md`).

### 2026-11-01: News source filter  `uncommitted`

**What:** The News Feed has a source panel (All News, ShareSansar, MeroLagani, Fiscal Nepal, Bizmandu, Arthakhabar, NepseAlpha) to the right of the cards; below 1024px it becomes a scrollable chip row above them. One source at a time, kept in `?source=<id>` so the view can be shared.
**API:** existing `GET /api/news/?source=` (`view_news`), so the filter covers every page, not just the loaded one.
**Frontend:** `components/news/SourceFilter.tsx`, list in `config/newsSources.ts`, wired into `pages/News.tsx`; Mulish font added (`font-mulish`).
**Open:** logos are the sites' `/favicon.ico` (the initial letter shows if one fails to load); brand colours are approximate.

### 2026-10-30: Sidebar "Summary" group  `uncommitted`

**What:** NEPSE Day by Day, NEPSE Month by Month, Weekday Summary and Floorsheet Summary moved into one "Summary" dropdown in the sidebar. Routes are unchanged.
**Frontend:** `components/layout/Sidebar.tsx`.

### 2026-10-30: Indicator library on index charts  `uncommitted`

**What:** Technical Charts (and the Company Analysis index chart) now draw the indicator library on indices such as NEPSE, the page's default view. Before, the picker listed EMA / Bollinger / RSI / MACD as "on the chart" but nothing was fetched or drawn for an index. 103 of 110 indicators work on indices; the 6 benchmark indicators and tick-rule volume need a stock and show why in the picker.
**Backend:** spec parsing and the compute loop moved from the company view into `apps/market_intelligence/services/indicator_series.py` (shared); `market_indices/services/index_technicals.py::indicator_series` feeds it `IndexDaily` bars. Index volume exists only for recent sessions (NEPSE from 2025-10), so volume indicators start at the first published volume instead of counting missing volume as 0.
**API:** `GET /api/market-indices/indicators/?code=NEPSE&specs=[...]` (`view_analysis`).
**Frontend:** `KlinePriceChart` takes `indexCode`; `IndicatorPicker`'s `dailyOnly` became a `notice` text (also explains a chart with no company or index).
**Tests:** `market_indices/tests/test_index_technicals.py`. All 110 indicators were also driven through the picker in a headless browser on a company and an index chart.

### 2026-10-30: Floorsheet prepared for order-flow (footprint) charts  `uncommitted`

**What:** Read-side filters and a footprint aggregation over the floorsheet, plus repairs of missing trade times and one missing day.
**Backend:** `apps/floorsheet/services/trade_filters.py` (odd lots < 10 shares, pre-open auction, untimed days), `footprint.py` (per bar and price row, buy / sell by the tick rule; bar close = last continuous trade), `floorsheet_quality.py`, `trade_time_backfill.py`; commands `fill_floorsheet_trade_times`, `floorsheet_quality_report`. `intraday_candles.py` unchanged.
**Data:** 2025-07-16 floorsheet loaded for NICA, NLG, NLIC, NTC, SANIMA, SCB, SHIVM, STC, TRH, UPPER (6,678 trades); 7,916 trade times filled on 2026-10-08/09 (backup in `Backend/backups/`). Volume equals DailyPrice on all 8,318 company-days; board-lot high/low on 99.72%.
**Tests:** `floorsheet/tests/test_footprint.py`.
**Open:** whether candles should use the same filters; candles for 2026-10-08/09 not yet rebuilt; no footprint API / UI yet (see `docs/status.md`).

### 2026-10-30: NEPSE Month-by-Month  `uncommitted`

**What:** Sibling of Day-by-Day: one row per BS year, one tile per BS month coloured by that month's index return (±12% scale), each year's compounded return as a bar, a pinned AVG row, and best / worst year, strongest month and months-closed-up cards. A Day / Month switch keeps the selected index (`?index=`).
**Backend:** `apps/market_calendar/services/monthly_returns.py` (no new table; derived from `IndexDaily`, cached); ShareSansar index fetch now pages through long ranges (`market_indices/services/sharesansar_indices.py`).
**API:** `GET /api/market-calendar/monthly/?index=` (`view_market_data`).
**Frontend:** route `/market/month-by-month` (`pages/MonthByMonthPage.tsx`), sidebar entry; shared grid pieces moved to `components/market/heatGrid.tsx`; `heatClass` takes a scale.
**Data:** needs long index history: `sync_market_indices --since 1997-07-01 --source sharesansar`.
**Tests:** `market_calendar/tests/test_monthly_returns.py`, `market_indices/tests/test_sharesansar_indices.py`.

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
