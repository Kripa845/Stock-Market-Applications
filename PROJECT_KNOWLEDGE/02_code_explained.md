# StockScope: Project Knowledge (2/3): Important Code & Setup

See 01 for structure and terms, 03 for status and rules. Paths are relative to the repo root.

---

## 5. IMPORTANT CODE/LOGIC

### 5.1 Real-data filter: `Backend/apps/market_data/services/price_source.py`
```python
def with_crawled_price(queryset):
    return queryset.filter(Exists(DailyPrice.objects.filter(
        company=OuterRef("company"), date=OuterRef("date"), source="crawled")))
```
- Keeps only analysis rows whose day has a **real crawled price**. Old synthetic rows (`unverified`/`seeded`) are filtered out of reads, not deleted.
- **Why:** early development seeded random-walk prices. They must never reach charts, indicators or exports.

### 5.2 Movers (gainers/losers): `Backend/apps/market_data/services/movers.py`
```python
PERIODS = {"1D": {"sessions": 1, "label": "Today"}, "5S": {...}, "20S": {"sessions": 20, "label": "1 month"}, ... "240S": ...}
PERIOD_ALIASES = {"1W": "5S", "1M": "20S", "1Y": "240S", ...}
CORPORATE_ACTION_PCT = Decimal("10")          # NEPSE daily circuit
def corporate_action_threshold(sessions):     # multi-session: compounded 10%/session
    if sessions <= 1: return CORPORATE_ACTION_PCT
    return ((Decimal("1.1") ** sessions - 1) * 100).quantize(Decimal("0.01"))
```
- Main entry: `tracked_movers(period, requested_date, company_ids, limit)`.
- Periods count **sessions with crawled data**, not calendar days.
- Change % = ShareSansar's adjusted `source_change_pct` when present, else close-to-close.
- A move above the threshold with no source % is flagged `possible_corporate_action` and excluded.
- Percentages are computed as float and cast back to numeric, because SQLite integer-divides whole-number decimals.
- **Rule:** every gainers/losers/session-change figure in the app must come from this file.

### 5.3 Trading calendar: `Backend/config/settings.py`
```python
NEPSE_TRADING_WEEKS = (
    ("1900-01-01", (6, 0, 1, 2, 3)),  # Sunday-Thursday (Python weekday: Mon=0)
    ("2026-04-06", (0, 1, 2, 3, 4)),  # Monday-Friday
)
NEPSE_CLOSING_PRICE_RULES = (("1900-01-01","last_trade"), ("2025-03-20","closing_vwap"), ("2025-09-22","last_trade"))
TRADING_DAYS_CRONTAB = ",".join(str((day + 1) % 7) for day in NEPSE_TRADING_WEEKDAYS)  # Celery: Sun=0
```
- Date-based week rules, so history before and after the switch is both correct.
- Helpers: `market_data/services/trading_days.py` (`is_market_day`, `is_market_open`, `market_closed_reason`) and `trading_calendar.py` (`trading_dates`, `latest_trading_date`, `previous_trading_sessions`). All of these default to `source="crawled"`.

### 5.4 Permissions: `Backend/apps/users/permissions.py` + `company_access.py`
```python
class HasAppPermission(BasePermission):
    def has_permission(self, request, view):
        key = getattr(view, "permission_key", None)
        if not key: return False            # fail closed: no key = nobody
        return request.user.has_app_permission(key)
```
- Layer 1: the view sets `permission_key = "view_analysis"`. Keys are listed in `users/api/serializers.py::ROLE_PERMISSIONS`. Admin gets all keys; otherwise the custom role's keys; otherwise the built-in role's `RolePermissionConfig`.
- Layer 2: `get_accessible_company_ids(user)` returns `None` (admin, unrestricted) or a list (`[]` = nothing). Per-company views use `filter_company_queryset()` / `require_company_access()`.
- Not narrowed by company: news reading, dividends, quarterly report, indices, IPO events.
- **Every new per-company endpoint needs both layers**, plus a frontend rule in `routePermissions.ts`.

### 5.5 Frontend auth: `frontend/src/api/client.ts`
```ts
let refreshPromise: Promise<string> | null = null;  // one shared refresh for all 401s
// on 401 (not an auth URL, not already retried): await refresh, save new tokens, retry once
// on 403: window.dispatchEvent(new CustomEvent('auth:forbidden'))  -> AuthContext re-fetches permissions
```
- Tokens live in `localStorage`. The shared promise stops 10 parallel 401s from making 10 refresh calls; with rotation, all but one would fail.
- `config/routePermissions.ts`: `'/broker-position': { permissions: ['view_analysis'], mode: 'all' }`. This only hides UI; the backend enforces.

### 5.6 Crawl runner: `Backend/crawlers/runner.py`
- `run_spider(name, timeout=1800)` → `subprocess.Popen(["python","-m","scrapy","crawl",name,...])`; kills it (the whole process group on Linux) on timeout.
- Spider lists: `NEWS_SPIDERS`, `MARKET_DATA_SPIDERS`, `FLOORSHEET_SPIDERS`, `BROKER_SPIDERS`, `DIVIDEND_SPIDERS`, `IPO_SPIDERS`. **A spider not in a list never runs on schedule.**
- **Why a subprocess:** a hung crawl can be killed; Scrapy's Twisted reactor can't restart inside a long-lived worker (UNSURE: the second reason is inferred, not documented).

### 5.7 Pipelines upsert: `Backend/crawlers/crawlers/pipelines.py`
```python
DailyPrice.objects.update_or_create(company=..., date=..., defaults={..., "source": "crawled"})
FloorsheetTransaction.objects.update_or_create(company=..., date=..., transaction_id=..., defaults=...)
```
- Natural unique keys mean re-running any crawl or backfill never duplicates rows.
- Numbers are parsed to `Decimal` with `parse_decimal` (`market_wide_pipeline.py`).

### 5.8 ShareHub time bug fix: `Backend/apps/floorsheet/services/sharehub_time.py`
```python
def parse_sharehub_time(raw):  # "2026-10-11T14:59:59Z" -> 14:59:59+05:45
    text = str(raw).strip().rstrip("Zz")
    ...
    return naive.replace(tzinfo=NPT)   # attach NPT; do NOT convert from UTC
```
- ShareHub labels Nepal-time values with `Z` (UTC). Trusting the `Z` shifted trades by +5:45. `fix_sharehub_trade_times` repaired the old rows.

### 5.9 Floorsheet read filters: `Backend/apps/floorsheet/services/trade_filters.py` (uncommitted)
```python
ODD_LOT_THRESHOLD = 10
def board_lots(trades): return trades.filter(quantity__gte=ODD_LOT_THRESHOLD)
def pre_open(trades): return trades.filter(trade_time__isnull=False, trade_time__time__lt=SESSION_OPEN)
def continuous_session(trades): return trades.filter(trade_time__isnull=False, trade_time__time__gte=SESSION_OPEN)
```
- Excluding odd lots makes floorsheet high/low match DailyPrice on **99.7%** of company-days (48.8% with them). Odd lots are 1.4% of trades and 0.02% of volume.
- These filters only read; they never delete.

### 5.10 Footprint (order flow): `Backend/apps/floorsheet/services/footprint.py` (uncommitted)
- `footprint(company, day, interval="5m", row_size=...)`: per bar and price row, buy/sell volume by the **tick rule**.
- Board lots only, in contract-number order; pre-open fills form a separate group and are never classified.
- Bar close = the last continuous trade in the bar, not the official close (they differ on ~27.5% of days).
- Untimed days produce one daily bar with `untimed=True`; times are never invented. Nothing is stored; there is no API or UI yet.

### 5.11 Broker accumulation signal: `Backend/apps/analysis/services/broker_accumulation.py`
```
ratio = top-5 net buying ÷ |top-5 net selling|
ratio > 1.2 -> Accumulation;  < 0.8 -> Distribution;  else Neutral;  nobody sold -> Accumulation, ratio None
```
- Windows `1d/1w/1m/3m` = the last 1/5/21/63 **floorsheet sessions** held for that stock.
- Why top-5: all brokers together always net to zero, so concentration shows direction.
- Checks bought qty = sold qty per session. Cached 1 h; the cache key includes the newest floorsheet row.

### 5.12 Broker position: `Backend/apps/analysis/services/broker_position.py`
- Running net (bought − sold) of one broker in one stock, starting at 0 at the range start. **Not holdings.**
- 1D = per minute, 2D = per 5 min (needs trade times); 1W–1Y = per session. `broker-activity` handles up to 8 symbols (8 distinct colour-blind-safe colours).

### 5.13 News tagging: `Backend/apps/news/services/categorization.py`
```
confidence = 0.60 × embedding cosine + 0.40 × lexical score
tag if ≥ 0.65; semantic-only (no keyword) needs ≥ 0.75; 0.60–0.75 semantic-only -> needs review
floors: symbol 0.95, name 0.93, alias 0.85, body 0.70, semantic 0.65
```
- Keyword regex: `(?<!\w)term(?!\w)` (word boundary). With ~20 companies, a plain NumPy comparison is enough; no vector DB.
- Manual tags (`is_manual=True`) are never overwritten, and every change writes a `CategorizationCorrection`.

### 5.14 Quarterly ratios: `Backend/apps/reports/services/quarterly_metrics.py`
- Stores filed figures only; ratios are computed per request. PE = LTP/EPS, PB = LTP/BV (n/m if ≤ 0). EPS fallback = net profit ÷ shares × 4 ÷ quarter. 3Y average DPPS needs at least 2 years. YoY is n/m when last year is ≤ 0.

### 5.15 Index feed guard: `market_indices/services/nepse_indices.py::_closing_index`
- A close ≤ 0 means "session unfinished", so the row is skipped. During the session NEPSE's feed shows today as close 0 / −100%.

---

## 6. SETUP & RUN

**Versions:** Python 3.12 (Docker; locally 3.12+) · Django 5.1.5 · DRF 3.15.2 · SimpleJWT 5.4.0 · Celery 5.4.0 · django-celery-beat 2.9.0 · redis-py 5.2.1 · psycopg 3.2.3 · Scrapy **2.12.0 pinned, but 2.18.0 installed locally** · nepse-data-api 1.0.0.4 · nepali_datetime 1.0.8.5 · pandas 2.2.3 · numpy 2.2.1 · sentence-transformers ≥3 + torch ≥2.2 · openpyxl, reportlab · pytest 8.3.4 + pytest-django 4.9.0.
Frontend: Node 20 · React 19.2 · TypeScript ~6.0 · Vite 8 · Tailwind 3.4 · TanStack Query 5 · axios 1.x · react-router 7 · klinecharts 10 · recharts 3 · oxlint.
Services: PostgreSQL 16, Redis 7.

**Env (`.env` at repo root, from `.env.example`):** `SECRET_KEY`, `DEBUG=True`, `ALLOWED_HOSTS`, `DB_NAME=stockscope`, `DB_USER`, `DB_PASSWORD`, `DB_HOST=localhost`, `DB_PORT=5432`, `REDIS_URL`, `CELERY_BROKER_URL` (/0), `CELERY_RESULT_BACKEND` (/1), `VITE_API_BASE_URL=http://localhost:8000/api`, `FRONTEND_URL`, `AUTH_THROTTLE_RATE`, `CATEGORIZATION_*`, `SENTIMENT_METHOD=lexicon`. Not in the template, but read: `BROKER_SIGNAL_ACCUMULATION_RATIO` (1.2), `BROKER_SIGNAL_DISTRIBUTION_RATIO` (0.8), `BROKER_EXCLUDE_SELF_TRADES` (False), `BROKER_ACCUMULATION_CACHE_SECONDS` (3600), `NEPSE_CLIENT_REUSE_SECONDS` (900), `PUBLIC_THROTTLE_RATE` (60/min).

**Option A: Docker**
```powershell
copy .env.example .env      # set SECRET_KEY, DB_PASSWORD
docker compose up --build   # frontend :3000, API :8000/api
docker compose exec backend python manage.py seed_companies
docker compose exec backend python manage.py seed_admin   # admin1 / Admin@123 (change it!)
```

**Option B: Native Windows (PowerShell, from `Backend/`)**
```powershell
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python manage.py migrate
venv\Scripts\python manage.py seed_companies
venv\Scripts\python manage.py seed_admin
venv\Scripts\python manage.py runserver
venv\Scripts\celery -A config worker --pool=solo --queues=crawling -l info
venv\Scripts\celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
# frontend/
npm install; npm run dev     # http://localhost:5173
```

**First-time data (once, idempotent):** `seed_market_indices` → `import_stock_sectors data/stock_sectors.csv` → `import_brokers data/brokers.csv` → `sync_broker_directory` → `sync_listed_shares` → prices (from `Backend/crawlers/`: `..\venv\Scripts\python -m scrapy crawl trading_data -a window_days=300`) → `backfill_sharehub_floorsheet --from YYYY-MM-DD` in chunks → `backfill_price_fields`, `backfill_market_analysis`, `backfill_market_intelligence`, `sync_market_indices --since 1997-07-01 --source sharesansar` → add holidays in Django admin.

**Manual crawls:** `manage.py run_crawl --type news|prices|floorsheet|all`, or the `/crawl` page, or `scrapy crawl <spider>` from `Backend/crawlers/`.

**Checks before committing (there is no CI):**
```powershell
cd Backend; venv\Scripts\python -m pytest -q          # ~3 min, SQLite in memory; 5 known failures
cd ..\frontend; npx tsc --noEmit -p tsconfig.app.json # NOT -p . (checks nothing)
```

**Useful repair commands:** `floorsheet_quality_report [--from --to --symbols --candles]` (read-only), `fill_floorsheet_trade_times [--apply]` (dry run by default; `--undo FILE --apply` restores), `rebuild_intraday_candles --from --to`, `fix_sharehub_trade_times`, `repair_news_dates`, `backfill_news_images`, `replicate_index calibrate --date D`, `check_index_feed`.
