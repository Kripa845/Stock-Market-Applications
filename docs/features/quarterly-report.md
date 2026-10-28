# Latest Quarterly Report

Per sector, the latest quarterly filing of every tracked company with valuation and dividend ratios: **Market → Quarterly Report** (`/market/quarterly-report/:sector`, e.g. `/market/quarterly-report/banking`). Clicking a company opens its stock page.

## How it is calculated
Only the figures as filed are stored (`reports.QuarterlyReport`, `reports.YearlyDPPS`). Every ratio is calculated per request in `Backend/apps/reports/services/quarterly_metrics.py` (pure functions), so it follows the price. A null value means *not meaningful* and is shown as **n/m**.

* **LTP:** latest **crawled** close (`MarketStockDaily` or `DailyPrice`, whichever is newer; live and unverified prices are never used).
* **EPS:** the annualized EPS as filed. If it is blank: net profit ÷ share count × 4 ÷ quarter (filings are cumulative for the fiscal year).
* **BV:** as filed, else net worth ÷ share count. **DPPS:** as filed, else distributable profit ÷ share count (can be negative).
* **PE** = LTP ÷ EPS, **PB** = LTP ÷ BV; n/m when EPS or BV ≤ 0.
* **DPPS yield** = DPPS ÷ LTP × 100.
* **3Y avg** = mean of the yearly DPPS for the 3 fiscal years ending at the company's newest year on file, divided by the years present (at least 2, otherwise n/m). Negative years are kept. "(2y)" marks a shorter history. **3Y avg yield** = 3Y avg ÷ LTP × 100. nepsetrading's own `dpps_avg5` is stored but covers 5 years, so it is used only if the window is set to 5 (`SOURCE_AVG_WINDOW_YEARS`).
* **YoY** = (EPS − EPS of the same quarter last year) ÷ |last year| × 100; n/m when last year is missing, zero or negative.
* The window (3) and the minimum (2) are `AVG_WINDOW_YEARS` / `AVG_MIN_YEARS` in `quarterly_metrics.py`. The API sends them and the column labels follow.

## API
Permission: `view_market_data`. Not narrowed to the caller's companies (like the dividends list).

| Method | Endpoint | Returns |
| :--- | :--- | :--- |
| `GET` | `/api/market/quarterly-report/?sector=BANKING&fiscal_year=2082/83&quarter=4` | `meta` (sector, fiscal year, quarter, reported / total companies, average window) and `results` (one row per company). No `fiscal_year` / `quarter` = latest filed. |
| `GET` | `/api/market/quarterly-report/periods/?sector=BANKING` | Fiscal years and quarters filed in the sector, newest first |

`sector` is a sub-index code: `BANKING DEVBANK FINANCE HOTELS HYDROPOWER INVESTMENT LIFEINSU MANUFACTURE MICROFINANCE MUTUAL NONLIFEINSU OTHERS TRADING`. Bad parameters return 400 with a `detail` message.

The filed figures for one (sector, fiscal year, quarter) are cached for 10 minutes. Prices are read on every request (one query), so PE / PB / yields are never stale. An import clears the cache.

## Getting the data in

There are two ways in, and both upsert on (company, fiscal year, quarter):

1. **Daily crawl.** Celery beat runs `apps.reports.tasks.crawl_quarterly_reports` at 19:45 every day (companies file throughout the reporting season). It fetches the tracked companies' latest reports from nepsetrading.com (`reports/services/nepsetrading.py`). By hand: `manage.py crawl_quarterly_reports`.
2. **CSV import**, for history or corrections (below).

### CSV import
Prepare a CSV, one row per company and quarter. Only `symbol`, `fiscal_year` and `quarter` are required, and any other cell may be blank. `Backend/data/quarterly_reports_template.csv` lists every tracked symbol, grouped by sector, with the cells empty. Rows you leave without a fiscal year and quarter are skipped, so an unfinished template never imports empty reports. The trailing `sector` / `name` columns are for reference only.

```csv
symbol,fiscal_year,quarter,reported_on,net_profit,net_worth,distributable_profit,share_count,eps,book_value,dpps,price_on_report_date
NABIL,2082/83,4,2026-08-10,"5,12,34,000",,,,30.12,212.40,8.82,
NABIL,2081/82,4,,,,,,24.00,198.10,5.00,
```

```powershell
cd Backend
venv\Scripts\python.exe manage.py import_quarterly_reports --file reports.csv --dry-run   # validate only
venv\Scripts\python.exe manage.py import_quarterly_reports --file reports.csv [--sector BANKING]
venv\Scripts\python.exe manage.py fill_yearly_dpps [--fiscal-year 2082/83]                 # optional, see below
```

* Fiscal year is `2082/83` or `2082/2083` (stored as `2082/2083`, like the rest of the app). Quarter is 1–4, `reported_on` is `YYYY-MM-DD`, and numbers may use thousands separators.
* Only active tracked companies are imported. Invalid rows are skipped and listed with the reason. The rest of the file still imports.
* **Filed figures are often unaudited at first and revised later.** Re-importing is safe: the file overwrites every column, blanks included. Re-import the revised row whenever a company publishes audited figures.
* **Yearly DPPS** (for the 3Y average) is filled from Q4 rows during the import, and `fill_yearly_dpps` re-runs that step on its own. For past years with no full report, add a Q4 row with just the `dpps` column.

### More companies per sector
The table covers tracked companies only. To add one, create or track it in **Admin → Companies**, using a sector label the app recognises (see `SECTOR_MAP` in `apps/market_indices/sectors.py`). It then appears in its sector tab with no code change. Then regenerate the template. `--force` overwrites the file, so pass `--output` to keep a template you've already filled in. The command also lists any tracked company whose sector label isn't recognised:

```powershell
venv\Scripts\python.exe manage.py quarterly_reports_template [--sector HYDROPOWER] [--output new.csv] [--force]
```

Tracking a company also adds it to the price, floorsheet and dividend crawls, and to news matching, so each one you add makes those crawls a little longer.

## Tests
```powershell
cd Backend
venv\Scripts\python.exe -m pytest apps/reports/tests/test_quarterly_reports.py
```
