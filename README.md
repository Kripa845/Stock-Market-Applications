# Stock Market Application & AI News Auto-Categorization System

An enterprise-grade stock market data crawling and analysis platform for the Nepal Stock Exchange (NEPSE), built with Django REST Framework, PostgreSQL, Celery + Redis, Scrapy, and React + Vite.

---

## 🚀 Key Features

* **Multi-Source Scrapy Crawlers**: Automated extraction of company financials, stock prices, floorsheet transactions, and market news from leading financial portals (Sharesansar, Merolagani, Bizmandu, Arthakhabar, FiscalNepal, NepseAlpha).
* **AI/ML News Auto-Categorization**: Hybrid architecture combining sentence embeddings (`SentenceTransformers`), cosine similarity, deterministic entity/alias matching, and independent multi-label confidence scoring.
* **Celery Background Processing**: Heavy ML inference and crawling run asynchronously without blocking synchronous REST API calls or Scrapy spider parsing loops.
* **Analyst Manual Review & Audit Trail**: Full capability for market analysts to correct, add, or update company tags, preserving manual precedence and persisting an unalterable audit log.
* **Strict Role-Based Access Control (RBAC)**: Enforced server-side permissions for `ADMIN`, `ANALYST`, and `VIEWER` roles.
* **Modern React Dashboard**: Real-time ticker feeds, interactive charts, news review queues, confidence gauges, and categorization correction controls.

---

## 🧠 Automatic News Categorization Architecture

### 1. Why Semantic Categorization?
Financial news articles often discuss companies using descriptive phrases, partial names, or indirect contextual references (e.g., "The leading commercial bank in Durbar Marg posted 35% profit surge"). A purely keyword-based system misses synonym variations and contextual nuances. Semantic embeddings capture the dense semantic meaning of both the news article and company profiles.

### 2. Why Multi-Label Classification?
A single financial news article frequently concerns multiple companies simultaneously. For example:
> *"Nabil Bank and NIC Asia report higher quarterly earnings following joint ATM integration."*

Single-label classification (`max(scores)`) would arbitrarily discard one company. Our system evaluates **every company in the watchlist independently**, allowing an article to receive tags for all companies exceeding the confidence threshold.

### 3. Why Embeddings Were Chosen
We utilize `SentenceTransformers` (`all-MiniLM-L6-v2`), a lightweight (384-dimensional dense vectors, ~80MB) open-source transformer model. It produces rich contextual representations of articles and company profiles quickly on standard CPU infrastructure without costly external API dependencies.

### 4. Why Keyword / Entity Matching is Also Used
Embeddings can sometimes generate false positives for companies in the same sector (e.g., confusing one commercial bank with another). Deterministic entity matching evaluates exact ticker symbols (`NABIL`), canonical names (`Nabil Bank Limited`), and configured aliases (`Nabil Bank`, `Nabil`) using regex word boundaries (`(?<!\w)term(?!\w)`). This provides a hard deterministic signal.

### 5. Why a Hybrid Approach Was Selected
The hybrid approach balances strengths and eliminates weaknesses:
* **Lexical matching** provides high precision and explainability when names/symbols are present.
* **Semantic embeddings** capture context, sector semantics, and thematic relevance.
* **Combined heuristic score**:
$$\text{Confidence Score} = w_{\text{embedding}} \times \text{CosineSimilarity} + w_{\text{lexical}} \times \text{LexicalScore}$$
* Default weights: `EMBEDDING_WEIGHT = 0.60`, `KEYWORD_WEIGHT = 0.40` (configurable in Django settings).

### 6. Cosine Similarity Comparison
Cosine similarity measures the angular similarity between the normalized article embedding $\vec{u}$ and company profile embedding $\vec{v}$:
$$\text{CosineSimilarity}(\vec{u}, \vec{v}) = \frac{\vec{u} \cdot \vec{v}}{\|\vec{u}\| \|\vec{v}\|}$$
Clipped to $[0.0, 1.0]$.

### 7. Confidence Score Interpretation
> **Important Note on Confidence**: The confidence score is a normalized heuristic classification score derived from lexical and semantic evidence. It is used for ranking and thresholding, not as a statistically calibrated probability.

### 8. Configurable Threshold
The multi-label threshold is configurable:
* `CATEGORIZATION_THRESHOLD = 0.65` (default)
* Evaluated per company:
  * $\text{NABIL} = 0.95 \ge 0.65 \implies \text{TAGGED}$
  * $\text{NICA} = 0.91 \ge 0.65 \implies \text{TAGGED}$
  * $\text{NLIC} = 0.28 < 0.65 \implies \text{EXCLUDED}$
* If no company meets the threshold, the article remains untagged (`needs_review=True`).

### 9. Why FAISS / Vector Database Was NOT Used
The project tracks a focused watchlist of 5–10 companies. Performing exact cosine similarity against 5–10 cached NumPy vectors takes **< 0.1 milliseconds** in Python. Introducing FAISS, Pinecone, or Milvus would add unnecessary infrastructure complexity without measurable benefit.

### 10. Manual Correction & Precedence
Market Analysts and Admins can override, add, or remove tags through the REST API (`POST /api/news/:id/recategorize/`) or the frontend interface.
* **Manual Precedence Rule**: Manual corrections (`is_manual=True`) have 100% precedence and are **NEVER overwritten or removed** by subsequent automatic background categorization tasks.

### 11. Correction Audit Trail
Every manual action creates an unalterable record in `CategorizationCorrection`:
* `article_id`
* `company_id`
* `action` (`add`, `remove`, `update`)
* `previous_confidence` / `new_confidence`
* `previous_method` / `new_method`
* `reason` (mandatory explanation from the analyst)
* `corrected_by` (authenticated user)
* `corrected_at` (timestamp)

---

## ⚖️ Trade-offs & Limitations

| Approach | Advantages | Limitations |
| :--- | :--- | :--- |
| **Keyword Matching** | Fast, deterministic, explainable, exact. | Misses synonyms, insensitive to context, alias dependent. |
| **Embeddings** | Understands semantics, handles rephrasings, robust to variations. | Can generate sector false positives, requires threshold tuning. |
| **Hybrid System** | Best balance of precision and recall, explainable confidence breakdown. | Heuristic weights require tuning for specific domains. |

---

## 🛠️ Technology Stack

* **Backend**: Django 5.1, Django REST Framework, SimpleJWT
* **Database**: PostgreSQL
* **Task Queue**: Celery 5.4 + Redis
* **Scraping**: Scrapy 2.12 + Twisted
* **AI/ML**: `sentence-transformers`, `torch`, `scikit-learn`, `numpy`
* **Frontend**: React 18, Vite, TypeScript, TailwindCSS, Lucide Icons

Backend layout (which app owns what, and which page calls which file): [`Backend/docs/architecture.md`](Backend/docs/architecture.md).

---

## 🧪 Running Automated Tests

Run the full categorization test suite:
```powershell
Backend\venv\Scripts\python.exe Backend\manage.py test apps.news
```

Run Django system check:
```powershell
Backend\venv\Scripts\python.exe Backend\manage.py check
```

---

## 📦 API Endpoints

| Method | Endpoint | Description | Role |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/news/` | List news with company, sentiment, search, and needs_review filters | All |
| `GET` | `/api/news/:id/` | Retrieve article details and multi-label tags | All |
| `POST` | `/api/news/:id/recategorize/` | Manually add/update/remove company tags with audit reason | Analyst, Admin |
| `POST` | `/api/news/:id/trigger-categorize/` | Trigger asynchronous Celery categorization for an article | Analyst, Admin |
| `GET` | `/api/news/corrections/` | Audit log of categorization corrections | All |
| `GET` | `/api/news/stats/` | News categorization distribution metrics | All |

---

## 🏦 Broker Accumulation / Distribution

For any stock and range, shows which brokers are net buying (accumulating) and which are net selling (distributing), from the floorsheet trades the app already stores. It appears on the stock page (`/companies/:symbol` → **Behavior** tab).

### How it is calculated
Code: `Backend/apps/analysis/services/broker_accumulation.py` (database aggregation only, no loops over raw trades).

* **Per broker:** buy / sell / net quantity, buy / sell amount, average buy and sell price, and net as a % of all shares traded in the range.
* **Signal:** `ratio = top-5 net buying ÷ |top-5 net selling|`. Above `BROKER_SIGNAL_ACCUMULATION_RATIO` (1.2) → Accumulation, below `BROKER_SIGNAL_DISTRIBUTION_RATIO` (0.8) → Distribution, otherwise Neutral. If nobody net sold, the signal is Accumulation with no ratio.
* **Top brokers:** each one's average price compared with the latest crawled close, and its streak (consecutive sessions net buying or net selling, up to 63 back).
* **Windows:** `1d` / `1w` / `1m` / `3m` = the last 1 / 5 / 21 / 63 floorsheet sessions held for the stock, so holidays and missing days don't shorten a window. A custom `start_date`–`end_date` range is also accepted.
* **Daily flow:** each session's top-5 net buying plus top-5 net selling (all brokers together always net to zero, so the top-5 concentration is what shows direction).
* **Self-trades:** trades where buyer == seller are counted unless `BROKER_EXCLUDE_SELF_TRADES=True` or the request passes `exclude_self=1`.
* **Validation:** each session's bought quantity must equal its sold quantity. A gap (rows with a missing broker code) is logged as a warning and shown under the charts.

### API
All take `symbol` plus either `window=1d|1w|1m|3m` (default `1w`) or `start_date=YYYY-MM-DD[&end_date=…]`, and optional `exclude_self=1|0`. Permission: `view_analysis`.

| Method | Endpoint | Returns |
| :--- | :--- | :--- |
| `GET` | `/api/analysis/broker-signal/` | Signal, ratio, thresholds, top-5 accumulators / distributors with P/L vs close and streaks, totals |
| `GET` | `/api/analysis/broker-summary/` | Every broker's row for the range, with totals |
| `GET` | `/api/analysis/broker-flow/` | One point per session: close, top-5 buy / sell net, net flow, ratio, volume; plus bought ≠ sold warnings |
| `GET` | `/api/analysis/acc-dist/?period=1D` | Market-wide (stock, broker) net buyers / sellers over `1D`…`3Y` sessions, ranked by net amount, with float % (public shares, else listed) |
| `GET` | `/api/analysis/brokers/<broker>/` | (existing) One broker's activity across stocks, `start_date` / `end_date` |

Responses are cached for `BROKER_ACCUMULATION_CACHE_SECONDS` (1 hour). The cache key includes the stock's newest floorsheet row, so a crawl that adds trades is picked up straight away.

### Settings / environment variables
| Variable | Default | Meaning |
| :--- | :--- | :--- |
| `BROKER_SIGNAL_ACCUMULATION_RATIO` | `1.2` | Ratio above which the signal is Accumulation |
| `BROKER_SIGNAL_DISTRIBUTION_RATIO` | `0.8` | Ratio below which the signal is Distribution |
| `BROKER_EXCLUDE_SELF_TRADES` | `False` | Drop buyer == seller trades by default |
| `BROKER_ACCUMULATION_CACHE_SECONDS` | `3600` | API cache lifetime |

### Data collection
No new fetcher: it reads `floorsheet.FloorsheetTransaction`, which the existing crawls fill.
* **Daily:** Celery beat runs `crawl_floorsheet` at 18:15 Asia/Kathmandu on trading days and skips weekends and `TradingHoliday` dates. Run it by hand from the admin crawler page if a day was missed.
* **Backfill:** ShareHub's floorsheet history goes back to October 2023. Backfill it in chunks (roughly 1 GB in total).
* Re-running a crawl never duplicates trades: `(company, date, transaction_id)` is unique and inserts ignore conflicts.

### Limitations
* Sources (ShareSansar, ShareHub, NEPSE's site) are unofficial for this use and fine for personal use. Check their terms of use before running the app publicly.
* A range only covers sessions whose floorsheet was crawled. Check the session count shown next to the signal.
* Broker numbers are trading members, not end investors: one broker's net buying can be many clients.
* Broker data is informational, not financial advice.

### Tests
```powershell
cd Backend
venv\Scripts\python.exe -m pytest apps/analysis/tests/test_broker_accumulation.py
```

## 📑 Latest Quarterly Report

Per sector, the latest quarterly filing of every tracked company with valuation and dividend ratios: **Market → Quarterly Report** (`/market/quarterly-report/:sector`, e.g. `/market/quarterly-report/banking`). Clicking a company opens its stock page.

### How it is calculated
Only the figures as filed are stored (`reports.QuarterlyReport`, `reports.YearlyDPPS`). Every ratio is calculated per request in `Backend/apps/reports/services/quarterly_metrics.py` (pure functions), so it follows the price. A null value means *not meaningful* and is shown as **n/m**.

* **LTP:** latest **crawled** close (`MarketStockDaily` or `DailyPrice`, whichever is newer; live and unverified prices are never used).
* **EPS:** the annualized EPS as filed. If it is blank: net profit ÷ share count × 4 ÷ quarter (filings are cumulative for the fiscal year).
* **BV:** as filed, else net worth ÷ share count. **DPPS:** as filed, else distributable profit ÷ share count (can be negative).
* **PE** = LTP ÷ EPS, **PB** = LTP ÷ BV; n/m when EPS or BV ≤ 0.
* **DPPS yield** = DPPS ÷ LTP × 100.
* **3Y avg** = mean of the yearly DPPS for the 3 fiscal years ending at the company's newest year on file, divided by the years present (at least 2, otherwise n/m). Negative years are kept. "(2y)" marks a shorter history. **3Y avg yield** = 3Y avg ÷ LTP × 100.
* **YoY** = (EPS − EPS of the same quarter last year) ÷ |last year| × 100; n/m when last year is missing, zero or negative.
* The window (3) and the minimum (2) are `AVG_WINDOW_YEARS` / `AVG_MIN_YEARS` in `quarterly_metrics.py`. The API sends them and the column labels follow.

### API
Permission: `view_market_data`. Not narrowed to the caller's companies (like the dividends list).

| Method | Endpoint | Returns |
| :--- | :--- | :--- |
| `GET` | `/api/market/quarterly-report/?sector=BANKING&fiscal_year=2082/83&quarter=4` | `meta` (sector, fiscal year, quarter, reported / total companies, average window) and `results` (one row per company). No `fiscal_year` / `quarter` = latest filed. |
| `GET` | `/api/market/quarterly-report/periods/?sector=BANKING` | Fiscal years and quarters filed in the sector, newest first |

`sector` is a sub-index code: `BANKING DEVBANK FINANCE HOTELS HYDROPOWER INVESTMENT LIFEINSU MANUFACTURE MICROFINANCE MUTUAL NONLIFEINSU OTHERS TRADING`. Bad parameters return 400 with a `detail` message.

The filed figures for one (sector, fiscal year, quarter) are cached for 10 minutes. Prices are read on every request (one query), so PE / PB / yields are never stale. An import clears the cache.

### Importing data
Prepare a CSV, one row per company and quarter. Only `symbol`, `fiscal_year` and `quarter` are required, and any other cell may be blank. `Backend/data/quarterly_reports_template.csv` lists every tracked symbol, grouped by sector, with the cells empty. Rows you leave without a fiscal year and quarter are skipped, so an unfinished template never imports empty reports. The trailing `sector` / `name` columns are for reference only.

**More companies per sector.** The table covers tracked companies only. To add one, create or track it in **Admin → Companies**, using a sector label the app recognises (see `SECTOR_MAP` in `apps/market_indices/sectors.py`). It then appears in its sector tab with no code change. Then regenerate the template. `--force` overwrites the file, so pass `--output` to keep a template you've already filled in. The command also lists any tracked company whose sector label isn't recognised:

```powershell
venv\Scripts\python.exe manage.py quarterly_reports_template [--sector HYDROPOWER] [--output new.csv] [--force]
```

Tracking a company also adds it to the price, floorsheet and dividend crawls, and to news matching, so each one you add makes those crawls a little longer.

```csv
symbol,fiscal_year,quarter,reported_on,net_profit,net_worth,distributable_profit,share_count,eps,book_value,dpps,price_on_report_date
NABIL,2082/83,4,2026-08-10,"5,12,34,000",,,,30.12,212.40,8.82,
NABIL,2081/82,4,,,,,,24.00,198.10,5.00,
```

```powershell
cd Backend
venv\Scripts\python.exe manage.py migrate
venv\Scripts\python.exe manage.py import_quarterly_reports --file reports.csv --dry-run   # validate only
venv\Scripts\python.exe manage.py import_quarterly_reports --file reports.csv [--sector BANKING]
venv\Scripts\python.exe manage.py fill_yearly_dpps [--fiscal-year 2082/83]                 # optional, see below
```

* Fiscal year is `2082/83` or `2082/2083` (stored as `2082/2083`, like the rest of the app). Quarter is 1–4, `reported_on` is `YYYY-MM-DD`, and numbers may use thousands separators.
* Only active tracked companies are imported. Invalid rows are skipped and listed with the reason. The rest of the file still imports.
* **Filed figures are often unaudited at first and revised later.** Re-importing is safe: rows upsert on (company, fiscal year, quarter), and the file overwrites every column, blanks included. Re-import the revised row whenever a company publishes audited figures.
* **Yearly DPPS** (for the 3Y average) is filled from Q4 rows during the import, and `fill_yearly_dpps` re-runs that step on its own. For past years with no full report, add a Q4 row with just the `dpps` column.

### Tests
```powershell
cd Backend
venv\Scripts\python.exe -m pytest apps/reports/tests/test_quarterly_reports.py
```
