# reports

Company fundamentals (dividends, EPS, quarterly reports) and the data exports.

| Where | What |
|---|---|
| `models.py` | DividendAnnouncement, CompanyEarnings, QuarterlyReport, YearlyDPPS (tables keep their market_data_* names) |
| `api/` | /api/market/dividends/, /api/market/quarterly-report/ |
| `services/` | dividends (upserts from the crawler, payout metrics), quarterly_reports, quarterly_metrics (PE / PB / yields) |
| `exports/` | /api/reports/export/ — news, trading, floorsheet, broker and combined report as CSV / XLSX / PDF |
| `management/commands/` | import_quarterly_reports, fill_yearly_dpps |

Tests: `tests/`. Layout and the page map: `Backend/docs/architecture.md`.
