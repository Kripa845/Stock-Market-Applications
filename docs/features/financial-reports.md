# Financial report documents

The `/financial-reports` page lists company filing documents collected from Nepalipaisa. It supports filtering by sector, tracked company, BS fiscal year and report duration, with 10 results per page. Each result links to the source PDF or image when a file base URL is configured.

## Data flow

Run `python manage.py sync_financial_reports` from `Backend` to sync tracked companies incrementally. The command follows newest-first API pages and stops when it reaches a page with no new documents. Use `--full` to read every page, `--symbol NABIL` to limit a run to one tracked company, and `--delay 1.0` to set the request delay. Repeated syncs update rows by Nepalipaisa document ID.

The database stores metadata in `FinancialReport`; source document URLs are composed from `FINANCIAL_REPORT_FILE_BASE_URL` and the stored `file_name`. Set that setting to a base URL ending in `/` for document links to appear.

## Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/financial-reports/filters/` | Sector, tracked-company, fiscal-year and duration options |
| `GET` | `/api/financial-reports/` | Paginated filings; accepts `sector`, `company`, `fiscal_year`, `duration` and `page` |

The API returns only active filings belonging to tracked companies. The list and filter endpoints require one of `view_financial_reports`, `view_market_data`, or `view_reports`; they do not apply per-user company access. The frontend `/financial-reports` route is gated by `view_financial_reports` or the legacy `view_reports` key. There is no upload or export API.

## Source values

Fiscal years and duration choices come from `financial_reports/constants.py`; they mirror the source site's available filters. Report dates are returned in BS format for display. The API response includes `sn`, `date`, `symbol`, `fiscal_year`, `duration`, `title` and `file_url`.
