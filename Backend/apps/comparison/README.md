# comparison

Side-by-side profile of 2 to 5 tracked companies, plus a data-coverage report. It has no models of its own. It reads `market_data`, `reports`, `floorsheet`, `market_intelligence` and the `analysis` broker helpers.

| Where | What |
|---|---|
| `api/` | /api/compare/, companies/, coverage/ |
| `services/compare.py` | One profile per company: missing figures are `null` with a reason, and a failing company becomes an error entry. |
| `services/coverage.py` | The profile run for every tracked company, with problems, sanity checks and source-table checks. |
| `management/commands/comparison_coverage.py` | The coverage table / JSON on the command line (read-only). |

Formulas and reason codes: `docs/features/stock-comparison.md`. Tests: `tests/`.
