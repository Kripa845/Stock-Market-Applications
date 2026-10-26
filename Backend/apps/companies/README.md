# companies

Company list and which companies are tracked.

| Where | What |
|---|---|
| `models.py` | Company, TrackedCompany |
| `api/` | /api/companies/ — list, detail, prices, sectors, floorsheet and volume anomalies per company |
| `services/selection.py` | tracked_active_companies(), crawl selection |
| `management/commands/` | seed_companies, sync_listed_shares, import_company_logos, seed_admin |

Tests: `tests/`. Layout and the page map: `Backend/docs/architecture.md`.
