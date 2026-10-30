# crawler_runs

Runs the Scrapy spiders and keeps their history.

| Where | What |
|---|---|
| `models.py` | CrawlRun |
| `api/` | /api/crawler-runs/ (also /api/admin/crawl-runs/) |
| `tasks.py` | run_crawl and the scheduled news / price / floorsheet / broker crawls |
| `management/commands/` | run_crawl, recover_crawls |

Tests: `tests/`. Layout and the page map: `ARCHITECTURE.md` (repo root).
