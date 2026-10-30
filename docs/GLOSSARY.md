# Glossary

NEPSE and project terms as they are used in the code. Where a term maps to a model, field or file, it's named.

## Market

| Term | Meaning |
|---|---|
| **NEPSE** | Nepal Stock Exchange. Also the name of its main index (`MarketIndex.code = "NEPSE"`). |
| **Session** | One trading day, 11:00–15:00 Asia/Kathmandu. Sun–Thu until 2026-04-05, Mon–Fri from 2026-04-06 (`settings.NEPSE_TRADING_WEEKDAYS`), minus `TradingHoliday` dates. "N sessions" (`5S`, `20S`) counts days with crawled data, not calendar days. |
| **NPT** | Nepal Time, UTC+05:45 (`ZoneInfo("Asia/Kathmandu")`). |
| **Floorsheet** | NEPSE's list of every trade in a session: transaction id, buyer broker, seller broker, quantity, rate, amount (`FloorsheetTransaction`). |
| **Broker** | A NEPSE trading member, identified by number (e.g. `58`). Net buying by a broker can be many clients (`Broker`). |
| **LTP** | Last traded price during the session (`Company.ltp`). Not the crawled close. |
| **Close / previous close** | From crawled `DailyPrice`. Previous close is derived from the previous crawled session, never stored. NEPSE's official close is not always the last trade: odd lots never count, and from 2025-03-20 to 2025-09-21 it was the VWAP of trades from 14:45 (`settings.NEPSE_CLOSING_PRICE_RULES`; checked by `validate_floorsheet_grid`). |
| **Odd lot** | A trade under 10 shares. Excluded from the official close. |
| **Adjusted change** | ShareSansar's published % change (`DailyPrice.source_change_pct`), using NEPSE's previous close adjusted for bonus / right shares. Differs from close-to-close on book-closure days. |
| **Turnover** | Traded value in NPR (quantity × rate summed). |
| **Transactions** | Number of trades in a session (`DailyPrice.transactions`, from the floorsheet). |
| **VWAP** | Volume-weighted average price (`DailyAnalysis`). |
| **Market cap** | Price × listed shares (`Company.listed_shares`, `CompanyDaily`). |
| **Sub-index / sector code** | NEPSE's 13 sector indices: `BANKING DEVBANK FINANCE HOTELS HYDROPOWER INVESTMENT LIFEINSU MANUFACTURE MICROFINANCE MUTUAL NONLIFEINSU OTHERS TRADING`. Free-text sectors map to them via `SECTOR_MAP` in `apps/market_indices/sectors.py`. |
| **Index replication / K** | Reproducing a published index as market cap × a calibration constant K (`IndexCalibration`, `IndexCheck`, `services/index_replication.py`). |

## Corporate actions and fundamentals

| Term | Meaning |
|---|---|
| **Fiscal year** | Nepali (BS) year, stored as `2082/2083`, starting mid-July. Quarters 1–4 are cumulative for the year. |
| **EPS / BV / DPPS** | Earnings per share (annualised), book value per share, distributable profit per share (`QuarterlyReport`, `YearlyDPPS`). |
| **PE / PB** | Price / EPS and price / BV, computed per request in the quarterly report. |
| **Book closure** | Date after which a new buyer no longer qualifies for a dividend or right share. Prices gap that day. |
| **Bonus / cash dividend** | Stock dividend / cash payout (`DividendAnnouncement`). Status moves proposed → AGM → SEBON → distributed. |
| **AGM / SEBON** | Annual general meeting; Securities Board of Nepal (the regulator that approves issues and bonus shares). |
| **IPO / FPO / right share** | Initial / further public offering; new shares offered to existing holders (`IpoIssue`, with mutual funds and debentures). |
| **Corporate action** | Bonus, right or split that moves the price without trading. `possible_corporate_action` flags a >10 % move with no source % change; such rows are excluded from movers. |

## Project terms

| Term | Meaning |
|---|---|
| **Tracked company** | A `Company` with `TrackedCompany.is_tracked` (about 20). The app crawls, analyses and labels only these; responses say `"scope": "tracked_companies"`. |
| **Whole market** | Tables keyed by `symbol` that hold every listed stock: `MarketStockDaily`, `CompanyDaily`, `StockSector`, `DividendAnnouncement`, `IpoIssue`. |
| **Crawled / unverified / seeded / manual** | `DailyPrice.source` values. Only `crawled` is real data. |
| **Data provenance** | `NewsArticle.data_provenance`: separates real articles from synthetic ones. |
| **Movers / buckets** | Session change per tracked company from `movers.py`: `gainer`, `loser`, `unchanged`, or excluded as `missing_price`, `not_traded`, `missing_previous_session`, `prev_close_zero`, `possible_corporate_action`. |
| **Tracked Basket** | The app's own index of tracked companies, turnover-weighted plus equal-weight (`ProxyIndexSnapshot`). Not a NEPSE index. |
| **Accumulation / distribution (Acc/Dist)** | A broker's net buying (accumulation) or net selling (distribution) of a stock over N sessions, from the floorsheet ([broker-accumulation](features/broker-accumulation.md)). Signal ratios: `BROKER_SIGNAL_ACCUMULATION_RATIO` 1.2 / `DISTRIBUTION_RATIO` 0.8. |
| **Broker position** | One broker's running net (bought − sold) in one stock within a range, starting at 0. Not holdings: the floorsheet can't show those (`analysis/services/broker_position.py`). |
| **Self-trade** | Buyer and seller broker are the same. Excluded from broker figures when `BROKER_EXCLUDE_SELF_TRADES` is on. |
| **Pressure** | Buy / sell pressure score per company per day (`DailyAnalysis.pressure`). |
| **Volume anomaly / RVOL** | Volume against its rolling mean (z-score, `VolumeAnomaly`); relative volume (`market_data/services/rvol.py`). |
| **Breadth** | Advancers vs decliners among tracked companies (`MarketBreadthSnapshot`). |
| **Sector rotation** | Sector ranking over time (`SectorRotationSnapshot`). |
| **Support / resistance** | Price levels with touch counts and strength (`SupportResistanceSet` / `Level`). |
| **Floorsheet grid** | The Floor Sheet Summary page: trades bucketed by 1–45 minutes, with validation checks (`analysis/services/floorsheet_grid.py`). |
| **WACC** | A user's weighted average cost per share for a watchlist holding (`WatchlistItem.wacc`). |
| **Permission key** | A string such as `view_market_data` checked by `HasAppPermission` (`ROLE_PERMISSIONS`). |
| **Company access** | Which companies a non-admin user may see (`UserCompanyAccess`). |
| **CrawlRun** | One recorded spider run with status, counters and logs. |
| **Circuit breaker** | The app's pause on NEPSE calls after 3 failed runs (30 min, held in Redis). Not NEPSE's own price limits. |
| **BS / AD** | Bikram Sambat (Nepali calendar) / Gregorian. Dates are stored in AD; BS conversion only through `nepali_datetime` (valid BS 1975–2100). Some news sites publish BS dates (`crawlers/crawlers/utils/dates.py`). |
