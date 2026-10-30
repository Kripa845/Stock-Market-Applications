# market_data

Daily prices, the live NEPSE feed, the market overview pages and watchlists.

| Where | What |
|---|---|
| `models.py` | DailyPrice, TradingHoliday, LiveFeedStatus |
| `api/market_views.py` | /api/market/ — summary, overview, movers, heatmap, top lists, broker activity, signals |
| `api/watchlists.py` | /api/market/watchlist(s)/ |
| `api/views.py` | /api/market-data/ — raw price list |
| `services/` | live_prices, movers, top_movers, market_stats, market_overview, heatmap, rvol, price_fields; trading_calendar and trading_days (sessions and holidays) |
| `tasks.py` | update_live_prices, derive_price_fields_task |
| `management/commands/` | update_live_prices, update_prices, backfill_price_fields |

Tests: `tests/`. Layout and the page map: `ARCHITECTURE.md` (repo root).
