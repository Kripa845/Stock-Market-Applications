# StockScope

A personal research app for the Nepal Stock Exchange (NEPSE). Scrapy spiders crawl prices, floorsheets (every trade with buyer and seller broker), dividends, quarterly reports, indices and news from Nepali sites. Django analyses and serves the data, and a React dashboard shows it with role-based access.

It covers only the **tracked companies** (about 20, set in Admin → Companies), never the whole market, except for the index, dividend and market-wide broker pages. It shows only real crawled data: anything missing appears as missing, never filled in.

## What it does

* **Market:** tracked-company movers, turnover / volume / transaction leaders, heatmap, a "Tracked Basket" index, NEPSE and sub-indices with live intraday ticks.
* **Stock page:** candlestick chart with about 110 indicators, intraday candles, floorsheet, support / resistance, broker accumulation / distribution, news and news-vs-price reaction.
* **Brokers:** broker activity, top brokers per stock, and market-wide accumulation / distribution ([spec](docs/features/broker-accumulation.md)).
* **Fundamentals:** dividends (whole market) and the latest quarterly report per sector with PE / PB / DPPS yields ([spec](docs/features/quarterly-report.md)).
* **News:** crawled hourly from five sites, tagged to companies automatically (embeddings plus keyword matching), with analyst corrections and an audit trail ([spec](docs/features/news-categorization.md)).
* **Access:** Admin / Analyst / Viewer plus custom roles, fine-grained permissions, and per-user company access.
* **Exports:** CSV / XLSX / PDF.

## Stack

Django 5.1 + DRF + SimpleJWT · PostgreSQL 16 · Celery 5.4 + Redis 7 (beat with `DatabaseScheduler`) · Scrapy 2.12 · sentence-transformers · React 19 + TypeScript + Vite + Tailwind + TanStack Query, with klinecharts and recharts for charts.

## Quick start

With Docker:

```powershell
copy .env.example .env      # set SECRET_KEY and DB_PASSWORD
docker compose up --build   # db, redis, backend, worker, beat, frontend (nginx)
```

Local (Windows, from `Backend/`):

```powershell
python -m venv venv; venv\Scripts\pip install -r requirements.txt
copy ..\.env.example ..\.env
venv\Scripts\python manage.py migrate
venv\Scripts\python manage.py seed_companies
venv\Scripts\python manage.py seed_admin        # change its password after first login
venv\Scripts\python manage.py runserver

# separate terminals, needs Redis
venv\Scripts\celery -A config worker --pool=solo --queues=crawling -l info
venv\Scripts\celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler

# frontend (from frontend/)
npm install; npm run dev
```

The remaining reference data (indices, sectors, brokers, history backfills) is covered in [docs/operations.md](docs/operations.md#first-time-setup).

## Tests

```powershell
cd Backend
venv\Scripts\python -m pytest -q                           # in-memory SQLite, see pytest.ini
cd ..\frontend
npx tsc --noEmit -p tsconfig.app.json                     # type-check
```

There is no CI. Run both before committing.

## Docs

| Doc | For |
|---|---|
| [CLAUDE.md](CLAUDE.md) | Commands, architecture and data rules, short (read by AI agents) |
| [Backend/docs/architecture.md](Backend/docs/architecture.md) | Which app owns what; frontend page → API → backend file |
| [docs/data-model.md](docs/data-model.md) | Tables, keys, data rules, glossary of NEPSE terms |
| [docs/api.md](docs/api.md) | Every endpoint and its permission; how access is checked |
| [docs/operations.md](docs/operations.md) | Setup, env vars, beat schedule, manual crawls, backfills |
| [docs/status.md](docs/status.md) | Known issues and unfinished work |
| [docs/features/](docs/features/) | Broker accumulation, quarterly report, news categorization |
| `Backend/apps/<app>/README.md` | What each app contains |

## Data sources

NEPSE, ShareSansar, ShareHub, nepsetrading.com, Merolagani and several news sites. All are unofficial for this use, which is fine for a personal app. Check their terms before running it publicly. Nothing here is financial advice.
