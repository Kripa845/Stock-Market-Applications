# market_calendar

Bikram Sambat (BS) month calendar of NEPSE sessions: index close and change, trading holidays and corporate-action events. No models of its own: it reads `market_indices.IndexDaily`, `market_data.TradingHoliday` and `reports.DividendAnnouncement`.

| Where | What |
|---|---|
| `api/` | /api/market-calendar/month/, day/ |
| `services/calendar.py` | BS month and day views. BS dates come from `nepali_datetime`, never from hand-written month tables. |

Tests: `tests/`. Layout and the page map: `Backend/docs/architecture.md`.
