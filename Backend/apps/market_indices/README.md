# market_indices

NEPSE and sector indices: sync from NEPSE / ShareSansar, replication and verification.

| Where | What |
|---|---|
| `models.py` | MarketIndex, IndexDaily, IndexIntradayPoint, StockSector, MarketStockDaily, CompanyDaily, IndexCalibration, IndexCheck |
| `api/` | /api/market-indices/ |
| `services/` | nepse_indices, sharesansar_indices, index_replication, index_verification, index_technicals, aggregates |
| `management/commands/` | sync_market_indices, seed_market_indices, replicate_index, check_index_feed, import_stock_sectors |

Tests: `tests/`. Layout and the page map: `ARCHITECTURE.md` (repo root).
