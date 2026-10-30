# StockScope

A personal research app for the Nepal Stock Exchange (NEPSE). Scrapy spiders and a few direct API clients collect prices, floorsheets (every trade with buyer and seller broker), dividends, quarterly reports, IPO issues, indices and news from Nepali sites. Django analyses and serves the data; a React dashboard shows it with role-based access.

* It covers only the **tracked companies** (about 20, chosen in the Companies page), not the whole market. The exceptions are the index, dividend, IPO and market-wide broker pages.
* It shows only **real crawled data**. Missing data appears as missing, never filled in.
* It is a personal tool, **not deployed** publicly. Its sources are unofficial; check their terms before running it for anyone else. Nothing here is financial advice.

## What it does

| Area | Pages |
|---|---|
| Market | Tracked-company movers, turnover / volume / transaction leaders, heatmap, "Tracked Basket" index, NEPSE and 13 sub-indices with live intraday ticks |
| Calendar | BS month calendar with index moves, holidays, dividend and IPO events; weekday summary; NEPSE day-by-day and month-by-month |
| Stock page | Candlestick chart with about 110 indicators, intraday candles, floorsheet, support / resistance, broker accumulation, news and news-vs-price reaction |
| Brokers | Broker list and activity, top brokers per stock, market-wide accumulation / distribution, one broker's running position in a stock |
| Fundamentals | Dividends (whole market), latest quarterly report per sector with PE / PB / DPPS yields |
| News | Crawled hourly from five sites, tagged to companies automatically, with analyst corrections and an audit trail |
| Admin | Users, roles and permissions, per-user company access, crawl runs, CSV / XLSX / PDF exports |

## Stack

Django 5.1 · DRF · SimpleJWT · PostgreSQL 16 · Celery 5.4 + Redis 7 (beat with `DatabaseScheduler`) · Scrapy · sentence-transformers · React 19 · TypeScript · Vite · Tailwind · TanStack Query · klinecharts + recharts.

## Setup

Prerequisites: Python 3.12+ (the Docker image uses 3.12), Node 20+, PostgreSQL 16, Redis 7. Or just Docker.

1. Copy the env file and set at least `SECRET_KEY` and `DB_PASSWORD`:
   ```powershell
   copy .env.example .env
   ```
   Every variable is described in [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md#environment-variables).

### Option A: Docker

```powershell
docker compose up --build        # db, redis, backend (runs migrate), worker, beat, frontend
docker compose exec backend python manage.py seed_companies
docker compose exec backend python manage.py seed_admin
```

Frontend: http://localhost:3000 · API: http://localhost:8000/api

### Option B: Native (Windows)

```powershell
cd Backend
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python manage.py migrate
venv\Scripts\python manage.py seed_companies
venv\Scripts\python manage.py seed_admin
venv\Scripts\python manage.py runserver

cd ..\frontend
npm install
npm run dev                      # http://localhost:5173
```

The rest of the reference data (indices, sectors, brokers, price and floorsheet history) is loaded once with the commands in [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md#first-time-setup).

> **`seed_admin` creates the admin user `admin1` / `Admin@123`** (hardcoded in `apps/companies/management/commands/seed_admin.py`; you log in with the username). Change the password after the first login, and note that running `seed_admin` again resets it to `Admin@123`. See [docs/SECURITY.md](docs/SECURITY.md).

## Run

Crawls and analysis run on a schedule, so the worker and beat must be running (Docker starts them; natively, use two more terminals from `Backend/`):

```powershell
venv\Scripts\celery -A config worker --pool=solo --queues=crawling -l info
venv\Scripts\celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

What runs when (all Asia/Kathmandu): live prices and index ticks during the 11:00–15:00 session, prices / floorsheet / analysis from 18:00 on trading days, news hourly. Full schedule: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md#celery-beat-schedule).

To crawl by hand, from `Backend/crawlers/`:

```powershell
..\venv\Scripts\python -m scrapy crawl trading_data -a symbols=NABIL,ADBL -a window_days=10
..\venv\Scripts\python -m scrapy crawl floorsheet
```

or use the **Crawl** page (`/crawl`) or `manage.py run_crawl --type news|prices|floorsheet|all`.

## Usage

1. Log in (with your username) as the admin, or register: self-registration always creates a **Viewer**.
2. As admin, open **Companies** to choose which companies are tracked, and **Users** / **Roles & Permissions** to give people a role (Admin, Analyst, Viewer or a custom role) and, optionally, limit them to some companies.
3. The sidebar shows only the pages your permissions allow. Everything per-company is narrowed to your allowed companies.
4. Data appears after the first crawls. If a page is empty, check **Crawl** for failed runs and [docs/status.md](docs/status.md) for known gaps.

## Tests

```powershell
cd Backend
venv\Scripts\python -m pytest -q                 # in-memory SQLite (config/settings_test.py)
cd ..\frontend
npx tsc --noEmit -p tsconfig.app.json            # type-check only; there are no frontend tests
```

There is no CI. On 2026-10-30: 1017 tests, 5 failing (listed in [docs/status.md](docs/status.md)). Details: [docs/TESTING.md](docs/TESTING.md).

## Documentation

| Doc | For |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Components, data flow diagram, page → API → backend map, design decisions |
| [CLAUDE.md](CLAUDE.md) | Commands, conventions and hard rules (read by AI agents, useful for humans) |
| [docs/DATABASE.md](docs/DATABASE.md) | Tables, keys, relationships, data rules |
| [docs/API.md](docs/API.md) | Endpoints, permissions, examples |
| [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) | Where each dataset comes from, rate limits, fallbacks, backfills |
| [docs/SECURITY.md](docs/SECURITY.md) | Auth, permissions, secrets |
| [docs/TESTING.md](docs/TESTING.md) | Running tests, coverage, known failures |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Running it: Docker, env vars, setup, beat schedule |
| [docs/GLOSSARY.md](docs/GLOSSARY.md) | NEPSE and project terms |
| [docs/status.md](docs/status.md) | Known issues and unfinished work |
| [docs/project-log.md](docs/project-log.md) | Feature history, newest first |
| [docs/features/](docs/features/) | Broker accumulation, quarterly report, news categorization |
