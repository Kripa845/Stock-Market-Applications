# Data model

The tables that matter, which app owns them, their natural keys, and the rules that aren't visible from the field list. For exact fields read the `models.py`. All upserts use the unique keys below, so re-running a crawl or import never duplicates rows.

## Glossary

| Term | Meaning |
|---|---|
| **Tracked company** | A `Company` with `TrackedCompany.is_tracked`. The app crawls, analyses and labels only these (about 20), never "the market". |
| **Session** | One NEPSE trading day, 11:00–15:00 Asia/Kathmandu. Sun–Thu until 2026-04-05, Mon–Fri from 2026-04-06, minus `TradingHoliday` dates. "N sessions" counts days with crawled data, not calendar days. |
| **Floorsheet** | NEPSE's list of every trade in a session: transaction id, buyer broker, seller broker, quantity, rate, amount. |
| **Broker** | A NEPSE trading member, identified by number (e.g. `58`). Net buying by a broker can be many clients. |
| **LTP** | Last traded price (live, intraday). Not the same as the crawled close. |
| **Close / previous close** | From crawled `DailyPrice`. Previous close is derived from the previous crawled session, never stored. NEPSE's official close is **not** always the last trade: odd lots (<10 shares) never count, and from 2025-03-20 to 2025-09-21 it was the VWAP of trades from 14:45 (the last trade before and after) (`settings.NEPSE_CLOSING_PRICE_RULES`; checked by `manage.py validate_floorsheet_grid`). |
| **Adjusted change** | ShareSansar's published % change, which uses NEPSE's previous close adjusted for bonus / right shares. Differs from close-to-close on book-closure days. |
| **Fiscal year** | Nepali (Bikram Sambat) year, stored as `2082/2083`. Starts mid-July. Quarters 1–4 are cumulative for the year. |
| **EPS / BV / DPPS** | Earnings per share (annualized), book value per share, distributable profit per share. |
| **Book closure** | Date after which a new buyer no longer qualifies for a dividend or right share. Prices gap on that day. |
| **WACC** | A user's weighted average cost per share in a watchlist holding. |
| **Sub-index / sector code** | NEPSE's 13 sector indices: `BANKING DEVBANK FINANCE HOTELS HYDROPOWER INVESTMENT LIFEINSU MANUFACTURE MICROFINANCE MUTUAL NONLIFEINSU OTHERS TRADING`. Free-text sector labels map to them through `SECTOR_MAP` in `apps/market_indices/sectors.py`. |
| **BS dates** | Bikram Sambat dates. Some news sites publish them, and `crawlers/crawlers/utils/dates.py` converts them. `repair_news_dates` fixes BS dates that were parsed as Gregorian. All BS conversion (month lengths, Nepali month names and numerals) goes through the `nepali_datetime` library, valid for BS 1975–2100; never hand-write month tables. The market calendar (`market_calendar`) converts on the backend, so the frontend has no BS library. Dates are always stored in AD. |

## Tracked companies vs. whole market

Most tables hang off `Company` (tracked scope). Since the `market_indices` app was added, a few tables hold **every listed stock** keyed by `symbol` instead: `MarketStockDaily`, `CompanyDaily`, `StockSector`, `DividendAnnouncement`, `IpoIssue`. Use these for market-wide pages (indices, Acc/Dist float %, dividends). Everything labelled "tracked companies" must still come from the `Company`-scoped tables.

## companies
| Model | Key | Notes |
|---|---|---|
| `Company` | `symbol` unique | `sector` (free text), `aliases` (JSON list, used for news matching), `is_active`. Live fields `ltp`, `previous_close`, `prices_updated_at`, `session_volume`, `session_turnover` are written by `market_data.services.live_prices` during the session. `listed_shares` comes from the admin or `sync_listed_shares`. |
| `TrackedCompany` | one-to-one `company` (`related_name="tracking"`) | `is_tracked`. Read via `companies/services/selection.py` → `tracked_active_companies()`. |

## market_data
| Model | Key | Notes |
|---|---|---|
| `DailyPrice` | (`company`, `date`) | OHLC, volume, turnover. **`source`**: only `"crawled"` is real. `"unverified"` (the default) and `"seeded"` are synthetic and must never feed charts or analysis. `transactions` is NULL until that day's floorsheet is crawled. `source_change_pct` = ShareSansar's adjusted % change. There is no previous-close column. |
| `TradingHoliday` | `date` unique | Admin-editable. Read through `services/trading_days.py`. |
| *(derived)* session change | — | `services/movers.py` is the only definition. Each tracked company falls into `gainer` / `loser` / `unchanged`, or is excluded as `missing_price`, `not_traded`, `missing_previous_session`, `prev_close_zero` or `possible_corporate_action` (>10% move with no source %). Change % = `source_change_pct` when present, else close-to-close. |
| `LiveFeedStatus` | single row | Last successful live-feed save. Kept in the DB because worker and web server don't share Django's per-process cache. |

## floorsheet (tables keep `market_data_*` names)
| Model | Key | Notes |
|---|---|---|
| `FloorsheetTransaction` | (`company`, `date`, `transaction_id`) | `buyer_broker` / `seller_broker` are broker numbers as strings. `trade_time` is set only for days loaded from ShareHub. ShareSansar floorsheets have no times. |
| `IntradayCandle` | (`company`, `interval`, `bucket_start`) | 1m–1h candles built from floorsheet trades with `trade_time`, so they exist only for ShareHub-synced days. |
| `Broker` | `broker_code` unique, `broker_no` | Directory from NEPSE members plus ShareHub (`sync_broker_directory`). |

## reports (tables keep `market_data_*` names)
| Model | Key | Notes |
|---|---|---|
| `DividendAnnouncement` | (`symbol`, `fiscal_year`), else (`source`, `source_id`) | **Whole market**, keyed by symbol. `company` is linked only when the symbol is ours. `status` only moves forward (proposed → AGM → SEBON → distributed). |
| `CompanyEarnings` | (`symbol`, `fiscal_year`, `quarter`) | EPS per quarter (Merolagani). |
| `QuarterlyReport` | (`company`, `fiscal_year`, `quarter`) | Figures as filed. All ratios are computed per request, see [quarterly-report](features/quarterly-report.md). |
| `YearlyDPPS` | (`company`, `fiscal_year`) | Filled from Q4 rows. Feeds the 3-year DPPS average. |
| `IpoIssue` | (`source`, `source_id`) | **Whole market.** IPO / FPO / right share / mutual fund / debenture issues from ShareSansar "Existing Issues" (spider `ipo_issues`). ShareSansar has no issue id: `source_id` = `<type>-<ShareSansar company id>-<units>`, and a second issue under the same key gets `-<open date>` (or `-pending`) appended (`reports/services/ipo_issues.py`). `close_date` is the earliest closing date, `final_date` the latest. `company` is linked only when the symbol is ours. |

## market_indices (whole market)
| Model | Key | Notes |
|---|---|---|
| `MarketIndex` | `code` unique | NEPSE plus 13 sub-indices (`seed_market_indices`). |
| `IndexDaily` | (`index`, `date`) | Published index OHLC / turnover. **Never store today's row before the close**: the feed reads close 0 / −100% mid-session. |
| `IndexIntradayPoint` | (`index`, `recorded_at`) | Live ticks every 5 min during the session. |
| `MarketStockDaily` | (`symbol`, `date`) | Daily row per listed stock (close, prev close, volume, turnover). |
| `CompanyDaily` | (`date`, `symbol`) | Close plus listed / public shares and share class, used to reproduce index values (`services/index_replication.py`). A stock that didn't trade keeps its last close (`traded=False`). |
| `StockSector` | `symbol` unique | Symbol → sub-index sector for every listed stock. |
| `IndexCalibration`, `IndexCheck` | (`index`, `effective_date`), (`index`, `date`) | Replication constant K and the daily computed-vs-published comparison. |

## analysis
| Model | Key | Notes |
|---|---|---|
| `DailyAnalysis` | (`company`, `date`) | VWAP, return, volume ratio and anomaly flag, buy/sell `pressure` + score + method, `news_count`, `has_sufficient_history`. Rebuilt nightly. |
| `VolumeAnomaly` | (`company`, `date`) | Rolling mean / std / z-score. |
| `NewsPriceCorrelation` | one-to-one `company` | JSON results blob. |

## market_intelligence
| Model | Key | Notes |
|---|---|---|
| `MarketBreadthSnapshot`, `ProxyIndexSnapshot` | `date` unique | Breadth and the "Tracked Basket" index (turnover-weighted plus equal-weight), tracked companies only. |
| `CompanyTechnicalSnapshot` | (`company`, `date`) | Patterns, signal, `sufficient_history`, `possible_corporate_action`. |
| `SectorRotationSnapshot` | (`sector`, `date`) | Sector ranks. |
| `SupportResistanceSet` / `SupportResistanceLevel` | one-to-one `company` / FK `set` | Levels with touches and strength, recomputed after the evening price crawl. |

Indicators themselves are not stored: `market_intelligence/indicators/` computes them on request (`registry.py` lists about 110). They return `None` during warm-up, never 0.

## news
| Model | Key | Notes |
|---|---|---|
| `RawArticle` | (`source`, `url`) | Raw HTML per fetch. |
| `NewsArticle` | `url` unique, `content_hash` | Headline, body, `published_at`, sentiment fields, `is_processed`. `data_provenance` separates real articles from synthetic ones. Read through `news/selectors.py` (`real_articles()`, `real_tags()`). |
| `ArticleCompanyTag` | (`article`, `company`) | `confidence`, `method`, `evidence`, `is_manual`. See [news-categorization](features/news-categorization.md). |
| `CategorizationCorrection` | — | Append-only audit of manual tag changes. |

## crawler_runs
| Model | Key | Notes |
|---|---|---|
| `CrawlRun` | — | One row per spider run: `crawl_type`, `source`, `status`, counters, `errors`, `logs`, `task_id`, `process_id`. A standalone `scrapy crawl` gets `crawl_type="news"` by default even for price crawls, so filter by `source` when auditing. |

## users
| Model | Key | Notes |
|---|---|---|
| `User` | `email` (login) | `role` = admin / analyst / viewer, optional `custom_role`. `get_app_permissions()`: admin gets all keys, otherwise the custom role's list, otherwise the role's `RolePermissionConfig`. |
| `RolePermissionConfig`, `CustomRole` | `role_key`, — | Editable permission lists (keys in `users/api/serializers.py` → `ROLE_PERMISSIONS`). |
| `UserCompanyAccess` | (`user`, `company`) | Per-user allowed companies, on top of role permissions. |
| `Watchlist` / `WatchlistItem` | (`user`, `name`) / (`watchlist`, `company`) | Named lists, one `is_default`. Items hold `units` and `wacc`. |
