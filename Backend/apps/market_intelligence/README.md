# market_intelligence

Technical indicators, market breadth, sector rotation and support / resistance.

| Where | What |
|---|---|
| `models.py` | MarketBreadthSnapshot, ProxyIndexSnapshot, CompanyTechnicalSnapshot, SectorRotationSnapshot, SupportResistanceSet/Level |
| `api/` | /api/market-intelligence/ |
| `indicators/` | the indicator library (registry + one module per family) |
| `services/` | technicals, technical_summary, snapshots, sector_rotation, support_resistance |
| `management/commands/` | backfill_market_intelligence, compute_support_resistance |

Tests: `tests/`. Layout and the page map: `Backend/docs/architecture.md`.
