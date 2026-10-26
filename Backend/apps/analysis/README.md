# analysis

Behaviour analysis: broker accumulation, daily pressure, volume anomalies, news vs price.

| Where | What |
|---|---|
| `models.py` | DailyAnalysis, VolumeAnomaly, NewsPriceCorrelation |
| `api/` | /api/analysis/ |
| `services/` | brokers, broker_accumulation, daily_metrics, volume_anomaly, news_price_correlation, news_market_reaction, news_sentiment_forward |
| `management/commands/` | backfill_market_analysis |

Tests: `tests/`. Layout and the page map: `Backend/docs/architecture.md`.
