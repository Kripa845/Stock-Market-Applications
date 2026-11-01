# Stock comparison

Side-by-side profile of 2 to 5 tracked companies, built only from stored data (`apps/comparison/`). Every tracked company goes through the same code path. A figure that can't be computed is `null` and listed in `data_quality.null_fields` with a reason code: it is never 0 and never estimated. If one company's profile raises an error, that company comes back as `{"error": "computation_failed"}` and the others are unaffected.

Page: `/compare?symbols=ADBL,CHCL` (`frontend/src/pages/StockComparisonPage.tsx`, sidebar Comparison → Stock Comparison).

## Endpoints (all `view_analysis`, narrowed by company access)

| Endpoint | Returns |
|---|---|
| `GET /api/compare/?symbols=ADBL,CHCL,SCB[&date=YYYY-MM-DD]` | One object per symbol, in the order given. `date` picks the broker session (default: the company's latest floorsheet day). |
| `GET /api/compare/companies/[?sector=Hydropower]` | `results` (symbol, name, sector) for the picker and `sectors`. `sector` matches case-insensitively. |
| `GET /api/compare/coverage/` | The coverage report: per-company counts, `problems`, failed sanity checks, null fields, plus `assumptions` (CompanyEarnings rows, empty QuarterlyReport columns, live price against the last floorsheet trade). |

Errors: `400` with `code` set to `symbols_required`, `symbol_count` (not 2–5), `duplicate_symbols`, `unknown_symbols` (unknown, or not tracked; `invalid_symbols` lists them) or `invalid_date`. `403` with `code` `company_access_denied` and `denied_symbols` when the user lacks access to any requested company.

The same report on the command line (read-only): `manage.py comparison_coverage [--json] [--sample ADBL,CHCL] [--output file.json]`.

## Fields and sources

| Field | Formula / source |
|---|---|
| `ltp`, `previous_close`, `change_pct` | Latest crawled `DailyPrice.close`. Previous close and change come from `movers.company_rows`, which uses the exchange's adjusted previous close on a book-closure day. `Company.ltp` (live feed) is used only when the company has no DailyPrice at all, with `ltp_source = company_live_feed`. |
| `price_trend_3m`, `volume_trend` | Closes for the last 90 days; volumes for the last 10 sessions. |
| `week52_low` / `week52_high` | min(low) / max(high) over the 365 days ending at the latest close. `insufficient_history` when prices start later than that. |
| `market_cap` | ltp × `Company.listed_shares` |
| `face_value` | Latest `DividendAnnouncement.face_value`, otherwise 100 (`face_value_source = default_100`). All 18 companies with dividend rows have 100. |
| `paid_up_capital`, `reserve_surplus` | listed_shares × face value; book value × listed_shares − paid-up. `QuarterlyReport.share_count` / `net_worth` are empty, so `Company.listed_shares` is used. |
| `eps_ttm` | Latest `QuarterlyReport.eps` at Q4. Filed EPS is annualized and cumulative, so at Q1–Q3 TTM = eps·n/4 + last year's Q4 − last year's Qn eps·n/4, which needs both last-year rows; otherwise `needs_more_quarterly_data`. `CompanyEarnings` is not used. |
| `eps_reported` | The latest filed EPS; flagged `same_as_ttm_until_quarterly_history_backfilled`. |
| `top_buy_brokers` / `top_sell_brokers` | `FloorsheetTransaction` for one company and session, grouped by broker, top 5 by quantity, `pct_of_day_volume` against that day's total. `TX-` synthetic rows are excluded. Uses the existing `(company_id, date)` index. |
| `pe`, `pb`, `roe` | ltp / eps_ttm (`negative_eps` when ≤ 0); ltp / book value; eps_ttm / book value × 100. |
| `dividend`, `dividend_yield` | Latest `DividendAnnouncement` by `fiscal_year` (by company, then by symbol); yield = (cash + bonus) × face value / 100 / ltp × 100 (`dividend_yield_basis` says so). |
| `yoy_profit_growth`, `earning_trend_5q`, `peg` | `null`, `needs_more_quarterly_data` (one report per company). |
| `ps`, `roa`, `debt_equity` | `null`, `no_source_column` (no revenue / assets / liabilities columns). For banks, finance companies and insurers the entry also notes that D/E and ROA are not comparable with other sectors. |
| `rsi`, `macd*`, `macd_label` | Latest `CompanyTechnicalSnapshot.rsi_14` / `macd` / `macd_signal` / `macd_hist`; Bullish when MACD > signal. |
| `sma50`, `sma200` | `dma_50` / `dma_200` with `above = ltp > value`. |

## RSI and MACD

Computed by `market_intelligence/services/momentum.py` from the crawled closes on the snapshot's session dates. RSI(14) uses Wilder's smoothing. It is 100 when the average loss is 0, and `null` when there was no movement at all (rather than reading "overbought"). EMAs are seeded with the SMA of their first N values. Every value is `null` before 35 sessions. They are filled at the end of `compute_company_technical_snapshots` (the nightly build). The full history is filled with `manage.py backfill_momentum_indicators [--symbols ADBL,CHCL] [--dry-run]`, which writes only rows whose values change, so re-running it is safe. Checked against StockCharts' Wilder example and an independent pandas computation over ADBL's 696 sessions (max difference < 0.00005).

## Unadjusted prices

`DailyPrice` keeps raw closes and is **not** adjusted for bonus or right shares. `market_data/services/price_adjustments.py` flags sessions where ShareSansar's `source_change_pct` (measured against the adjusted previous close) differs from our close-to-close change by more than 1 percentage point. The profile adds an `unadjusted_price_adjustment` warning listing which fields' lookback (RSI / MACD 50 sessions, SMA50, SMA200, 52 weeks) spans such a session. No data is changed.

## `data_quality`

`price_as_of`, `expected_latest_session` (today after 18:30 NPT on a market day, else the previous market day; holidays come from `TradingHoliday`), `snapshot_as_of`, `report_period`, `brokers_as_of`, `null_fields` (`field`, `reason`, optional `note`), `warnings` (`stale_price`, `brokers_date_differs`, `snapshot_behind_price`, `previous_close_adjusted`, `eps_reported_annualized`, `face_value_assumed`, `ltp_from_live_feed`, `unadjusted_price_adjustment`) and `price_adjustment_sessions`.
