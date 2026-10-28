# Broker Accumulation / Distribution

For any stock and range, shows which brokers are net buying (accumulating) and which are net selling (distributing), from the floorsheet trades the app already stores.

Where it appears:
* Stock page (`/companies/:symbol` → **Behavior** tab), via `components/brokers/accumulation/BrokerAccumulationPanel.tsx`.
* Market-wide page **Broker Accumulation & Distribution** (`/broker-acc-dist`, `pages/AccDistPage.tsx`). The old per-stock `/brokers-distribution` route redirects here.

## How it is calculated
Code: `Backend/apps/analysis/services/broker_accumulation.py` (database aggregation only, no loops over raw trades).

* **Per broker:** buy / sell / net quantity, buy / sell amount, average buy and sell price, and net as a % of all shares traded in the range.
* **Signal:** `ratio = top-5 net buying ÷ |top-5 net selling|`. Above `BROKER_SIGNAL_ACCUMULATION_RATIO` (1.2) → Accumulation, below `BROKER_SIGNAL_DISTRIBUTION_RATIO` (0.8) → Distribution, otherwise Neutral. If nobody net sold, the signal is Accumulation with no ratio.
* **Top brokers:** each one's average price compared with the latest crawled close, and its streak (consecutive sessions net buying or net selling, up to 63 back).
* **Windows:** `1d` / `1w` / `1m` / `3m` = the last 1 / 5 / 21 / 63 floorsheet sessions held for the stock, so holidays and missing days don't shorten a window. A custom `start_date`–`end_date` range is also accepted.
* **Daily flow:** each session's top-5 net buying plus top-5 net selling (all brokers together always net to zero, so the top-5 concentration is what shows direction).
* **Self-trades:** trades where buyer == seller are counted unless `BROKER_EXCLUDE_SELF_TRADES=True` or the request passes `exclude_self=1`.
* **Validation:** each session's bought quantity must equal its sold quantity. A gap (rows with a missing broker code) is logged as a warning and shown under the charts.

## API
All take `symbol` plus either `window=1d|1w|1m|3m` (default `1w`) or `start_date=YYYY-MM-DD[&end_date=…]`, and optional `exclude_self=1|0`. Permission: `view_analysis`.

| Method | Endpoint | Returns |
| :--- | :--- | :--- |
| `GET` | `/api/analysis/broker-signal/` | Signal, ratio, thresholds, top-5 accumulators / distributors with P/L vs close and streaks, totals |
| `GET` | `/api/analysis/broker-summary/` | Every broker's row for the range, with totals |
| `GET` | `/api/analysis/broker-flow/` | One point per session: close, top-5 buy / sell net, net flow, ratio, volume; plus bought ≠ sold warnings |
| `GET` | `/api/analysis/acc-dist/?period=1D` | Market-wide (stock, broker) net buyers / sellers over `1D`…`3Y` sessions, ranked by net amount, with float % (public shares, else listed) |
| `GET` | `/api/analysis/brokers/<broker>/` | One broker's activity across stocks, `start_date` / `end_date` |

Responses are cached for `BROKER_ACCUMULATION_CACHE_SECONDS` (1 hour). The cache key includes the stock's newest floorsheet row, so a crawl that adds trades is picked up straight away.

## Settings / environment variables
| Variable | Default | Meaning |
| :--- | :--- | :--- |
| `BROKER_SIGNAL_ACCUMULATION_RATIO` | `1.2` | Ratio above which the signal is Accumulation |
| `BROKER_SIGNAL_DISTRIBUTION_RATIO` | `0.8` | Ratio below which the signal is Distribution |
| `BROKER_EXCLUDE_SELF_TRADES` | `False` | Drop buyer == seller trades by default |
| `BROKER_ACCUMULATION_CACHE_SECONDS` | `3600` | API cache lifetime |

## Data collection
No separate fetcher: it reads `floorsheet.FloorsheetTransaction`, which the existing crawls fill.
* **Daily:** Celery beat runs `crawl_floorsheet` at 18:15 Asia/Kathmandu on trading days and skips `TradingHoliday` dates. Run it by hand from the admin crawler page if a day was missed. ShareSansar serves only the current session, so a missed day has to come from ShareHub (see [operations](../operations.md#backfills)).
* **Backfill:** ShareHub's floorsheet history goes back to October 2023. Backfill it in chunks (roughly 1 GB in total) with `backfill_sharehub_floorsheet`.
* Re-running a crawl never duplicates trades: `(company, date, transaction_id)` is unique and inserts ignore conflicts.

## Limitations
* Sources (ShareSansar, ShareHub, NEPSE's site) are unofficial for this use and fine for personal use. Check their terms of use before running the app publicly.
* A range only covers sessions whose floorsheet was crawled. Check the session count shown next to the signal.
* Broker numbers are trading members, not end investors: one broker's net buying can be many clients.
* Broker data is informational, not financial advice.

## Tests
```powershell
cd Backend
venv\Scripts\python.exe -m pytest apps/analysis/tests/test_broker_accumulation.py
```
