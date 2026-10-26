# floorsheet

Floorsheet trades, the broker directory and intraday candles built from the trades.

| Where | What |
|---|---|
| `models.py` | FloorsheetTransaction, Broker, IntradayCandle (tables keep their market_data_* names) |
| `api/` | /api/floorsheet/, /api/floorsheet/summary/, /api/stocks/<symbol>/intraday/ |
| `services/` | sharehub_floorsheet (ShareHub trade sync), intraday_candles, broker_directory |
| `tasks.py` | build_intraday_candles_live, finalize_intraday_candles |
| `management/commands/` | backfill_floorsheet, backfill/load_sharehub_floorsheet, fix_sharehub_trade_times, rebuild_intraday_candles, import_brokers, sync_broker_directory, check_brokers |

Tests: `tests/`. Layout and the page map: `Backend/docs/architecture.md`.
