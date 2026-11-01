# MEMORY

A running journal of every step taken on StockScope: what was done, what is in progress, and what comes next. **Newest first.** One line per step; details live in [docs/project-log.md](docs/project-log.md) (features) and [docs/status.md](docs/status.md) (bugs, gaps, open decisions).

## How to update

Whenever you (or Claude) add, change or remove something, in the same change:

1. Add a line at the top of **Timeline** under today's date: `- <what was done> (<where>) \`<commit hash or "uncommitted">\``.
2. Move the item out of **In progress** / **Next** if it is now done.
3. Add anything started but unfinished to **In progress**, and ideas or follow-ups to **Next**.
4. For a feature, also add the full entry to `docs/project-log.md`; for a bug or data gap, to `docs/status.md`.
5. Once `uncommitted` work is committed, replace the marker with the commit hash.

---

## In progress (as of 2026-11-01)

- **News source model + single ingest path**: `NewsSource`, `news_source` FK, URL / external-id identity, `ArticleLike`, `ArticleComment` (`apps/news/models.py`, `services/ingest.py`). Code and migrations are in `eb87a3a`; no project-log entry yet.
- **Stock Comparison page** on branch `feature/stock-comparison-page` (`a3b5df3`), not merged into `main`.

## Next

Open decisions and follow-ups (from `docs/status.md`):

- [ ] Crawl the missing 2026-10-30 prices (`run_crawl --type prices`), then `backfill_market_analysis` and `backfill_market_intelligence`.
- [ ] Decide whether to store a bonus / right-adjusted price series (RSI, MACD, DMAs and 52-week ranges span unadjusted book closures for 17 of 20 companies).
- [ ] Import quarterly history (at least 5 quarters with net profit) so TTM EPS, YoY growth and PEG can be computed.
- [ ] Make the sidebar collapse on phone widths (it leaves ~70px for every page at 390px).
- [ ] Add a project-log entry for news ingest.
- [ ] Decide whether the public endpoints (`/api/market/public/snapshot/`, `public/chart/`) stay; then fix the failing test or remove them.
- [ ] Decide the API number format (Decimal string vs number); fixes the 2 `test_broker_api.py` failures.
- [ ] Decide whether intraday candles use the footprint filters (odd lots, pre-open); rebuild candles for 2026-10-08/09.
- [ ] Footprint (order-flow) API and UI.
- [ ] Enter NEPSE holidays in `TradingHoliday`.
- [ ] Remove `Backend/data/backups/data.json` (contains a user password hash) from the repo.
- [ ] Align the `Scrapy` pin in `requirements.txt` with the installed 2.18.

---

## Timeline

### 2026-11-01
- Stock Comparison page `/compare` (`pages/StockComparisonPage.tsx`, `api/compare.ts`, `hooks/useCompare.ts`); sidebar "Comparison" is now a group. `a3b5df3`
- Stock comparison backend: `apps/comparison/`, `/api/compare/`, `compare/companies/`, `compare/coverage/`, command `comparison_coverage`. `eb87a3a`
- RSI(14) / MACD(12/26/9) on technical snapshots (`market_intelligence/services/momentum.py`, migration `0006`, `backfill_momentum_indicators`; 13,226 rows backfilled). `eb87a3a`
- Report of sessions where prices are not adjusted for bonus / right shares (`market_data/services/price_adjustments.py`; reports only). `eb87a3a`
- News source model, single ingest path, likes and comments, with migrations. `eb87a3a`
- Created this `MEMORY.md` journal and linked it from `CLAUDE.md`. `uncommitted`
- News Feed source filter panel / chip row, `?source=` in the URL (`components/news/SourceFilter.tsx`, `config/newsSources.ts`). `uncommitted`

### 2026-10-30
- Sidebar "Summary" group (Day by Day, Month by Month, Weekday, Floorsheet summary). `uncommitted`
- Indicator library on index charts (103 of 110 indicators on NEPSE etc.). `uncommitted`
- Floorsheet prepared for footprint charts; 2025-07-16 floorsheet loaded; 7,916 trade times filled. `uncommitted`
- NEPSE Month-by-Month page (`/market/month-by-month`). `uncommitted`
- Broker Position page, NEPSE Day-by-Day page, Weekday summary rework. `9664d90`
- Floorsheet data and various files committed. `e7a7ccf` `ffa6b21`

### 2026-10-29
- Floorsheet summary page. `470d7f9`
- Weekday-by-weekday summary UI redesign. `6cc7719`

### 2026-10-28
- Market calendar page and IPO issues. `14fd903` `45c62e2`
- Docs reorganised; `CLAUDE.md` added. `a548650` `cd9bc88`
- Per-stock Broker Distribution page removed in favour of Acc/Dist. `ed7a3b3`

### 2026-10-26 → 10-27
- Broker Accumulation / Distribution page, then fixes. `e0c2f74` `7e00b98`
- Heatmap and admin dashboard changes. `b4b9b07`
- Quarterly reports (WIP). `6555da7`
- Backend restructured into `floorsheet` and `reports` apps; branches merged. `7ca19b5` `66d3625`
- ShareSansar image URLs fixed. `1dea236`
- Mock data removed, real endpoints used. `d83f1fd`

### 2026-10-12 → 10-16
- Index and sub-index pages. `3fd3edd`
- Dashboard and Broker Analysis UI fixes. `7517ab9` `6da36f1`
- Some news sources removed from the schedule. `2ab998e`
- Dividend page, technical chart UI, Top Broker Stock page, index page fixes. `211d69e` `ac18168`

### 2026-10-01 → 10-09
- Brokers crawler. `5964e6b`
- Company logos. `fc13148`
- Landing page. `41a4b65` `a1b5d1d`
- Tracked companies (`TrackedCompany`); app covers only tracked companies from here on. `6334c88` `992abef`
- Repo cleanup (junk files, `node_modules` untracked). `537054c` `097adfa`

### 2026-09-21 → 09-30
- Behaviour analysis and analyst dashboard. `82f2c7a` `e6f0570` `a198358`
- Reports and export features. `192aab0` `ec423b4`
- Per-user company access. `89314a8` `ba75738` `e2b7cdc`
- Candle charts moved from Recharts to klinecharts. `593585a`
- Analysis and Market Overview features. `0fad72f` `a135090`

### 2026-09-15 → 09-18
- Admin page. `3ccd78e`
- Registration with roles; dynamic roles and permissions. `47a7205` `e471eed` `ab2b36a` `3ddc72f`
- Analyst page and Celery beat schedule changes. `5141689`
- First dashboard. `efd12a5`
- Light theme. `df15f56`

### 2026-08-31 → 09-01
- Data crawling fixed; floorsheet crawling done. `fc93dfc` `0c12e48`
- First pass at news categorization. `3d8a989`
- React frontend added. `622ea8f`
