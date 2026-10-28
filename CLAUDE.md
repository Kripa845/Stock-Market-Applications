# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

StockScope: a personal research app for the Nepal Stock Exchange (NEPSE). Scrapy spiders crawl prices, floorsheets (every trade with buyer/seller broker), dividends, indices and news from Nepali sites; Django/DRF analyses and serves them; a React + TypeScript dashboard shows them with role-based access. It covers only the **tracked companies** (`TrackedCompany`), never the whole market.

Deeper references:
- `docs/status.md`: known issues and WIP. **Read it before touching movers, crawls or routing.**
- `docs/data-model.md`: tables, unique keys, data rules, NEPSE glossary.
- `docs/api.md`: endpoints, permission keys, company-access scope.
- `docs/operations.md`: beat schedule, setup, backfills.
- `docs/features/`: broker accumulation, quarterly report, news categorization.
- `Backend/docs/architecture.md`: app ownership, frontend route → API → backend file.

## Commands

Windows dev machine; the backend venv lives at `Backend/venv`. Run backend commands from `Backend/`.

```powershell
# Backend
venv\Scripts\python manage.py migrate
venv\Scripts\python manage.py runserver
venv\Scripts\python manage.py check

# Celery (needs Redis)
venv\Scripts\celery -A config worker --pool=solo --queues=crawling -l info
venv\Scripts\celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler

# Tests (pytest.ini sets config.settings_test: in-memory SQLite, throttling off)
venv\Scripts\python -m pytest -q
venv\Scripts\python -m pytest apps/analysis/tests/test_broker_accumulation.py
venv\Scripts\python -m pytest apps/market_data/tests/test_movers.py -k test_name

# Manual crawls (from Backend/crawlers/)
..\venv\Scripts\python -m scrapy crawl trading_data -a symbols=NABIL,ADBL -a window_days=10
..\venv\Scripts\python -m scrapy crawl floorsheet

# Frontend (from frontend/)
npm run dev
npm run build
npx tsc --noEmit -p tsconfig.app.json   # NOT `-p .`: the root tsconfig has files: [] and checks nothing
```

Everything at once: `docker compose up --build` (Postgres, Redis, backend, worker, beat, nginx frontend).

Local environment quirks: Windows Smart App Control blocks some native binaries, so `npm run lint` (oxlint) can't run locally, and tests must stub the sentence-transformers model (see `FakeEmbeddingModel` in `apps/news/tests/test_news_api.py`) rather than load it.

There is no CI: run pytest and the `tsc` check yourself before committing.

## Architecture

- **`Backend/apps/<app>/`** share one layout (`models.py`, `api/`, `services/`, `tasks.py`, `management/commands/`, `tests/test_<feature>.py`). Put logic in `services/`, keep views thin.
- **Dependency direction:** `users`, `companies` → `market_data`, `floorsheet`, `reports`, `market_indices` → `analysis`, `market_intelligence`, `dashboard`, `market_calendar`. Don't import upward.
- **`Backend/config/`**: `settings.py` holds `CELERY_BEAT_SCHEDULE`, `CELERY_TASK_ROUTES`, `NEPSE_TRADING_WEEKS` and feature thresholds; `urls.py` wires every app's routes under `/api/`. `TIME_ZONE` = `CELERY_TIMEZONE` = Asia/Kathmandu.
- **`Backend/crawlers/`** is a separate Scrapy project. `crawlers/pipelines.py` bootstraps Django and writes models; pipelines upsert (`update_or_create` / unique keys with ignore-conflicts), so re-running a crawl is safe. `runner.py` launches spiders as subprocesses; Celery tasks in `apps/crawler_runs` trigger them and record `CrawlRun`.
- **News tags:** manual tags (`is_manual=True`) are never overwritten by automatic categorization, and every manual change writes a `CategorizationCorrection`.
- **Auth/RBAC:** SimpleJWT; backend checks via `HasAppPermission` (`permission_key` on the view) plus the helpers in `apps/users/company_access.py`. Every new endpoint that returns per-company data needs both; reading news is the main exception (see `docs/api.md`). Frontend mirrors this with `config/routePermissions.ts`, `PermissionRoute`, `PermissionGate`, `usePermissions`; the sidebar is permission-filtered. A new page needs a route in `App.tsx`, a rule in `routePermissions.ts` and a `Sidebar.tsx` entry.
- **Frontend (`frontend/src/`)**: `api/` has one module per backend area on top of `api/client.ts` (axios, JWT from localStorage, shared-promise refresh on 401); `hooks/` wraps them with TanStack Query; charts use klinecharts (candles) and recharts.

## Rules that aren't obvious from the code

- **Real data only.** Only `DailyPrice.source = "crawled"` is real; `"unverified"` rows are synthetic seed data and must never feed charts, indicators or analysis. Never mock, simulate or back-fill numbers: show missing data as missing ("—", empty state, warning) and label figures "tracked companies".
- **Trading calendar:** NEPSE traded Sun–Thu until 2026-04-05 and Mon–Fri from 2026-04-06. Use `apps/market_data/services/trading_days.py` / `trading_calendar.py` and the `TradingHoliday` table; never hardcode weekdays. "Previous session" comes from crawled price dates.
- **Movers:** session change / gainers / losers come only from `apps/market_data/services/movers.py`; reuse it.
- **NEPSE index feed:** today's row reads close 0 / −100% until the close; never store it.
- Sources (NEPSE, ShareSansar, ShareHub, news sites) are unofficial; fine for this personal-use app.
- **Frontend styling:** Tailwind with project tokens (`text-up`, `text-down`, `bg-bg-elevated`, `text-text-muted`, `card`), numbers in `font-mono`, formatting via `components/market/format.ts`.
- Keep comments short and about *why*; match surrounding code.
