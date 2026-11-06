# announcements

ShareHub announcement and event feed for configured tracked companies and market-wide NEPSE notices.

| Where | What |
|---|---|
| `models.py` | `Announcement`, uniquely keyed by source `external_id`; blank `symbol` means market-wide |
| `services.py` | Fetches ShareHub's JSON feed, normalizes Nepal-local publication times and upserts recent entries |
| `api/` | List and filter-option endpoints are wired in `urls.py` and implemented in `views.py` |
| `management/commands/` | `sync_announcements [--days 7] [--debug]` manual refresh |
| `tasks.py` | `sync_announcements_task`; not currently scheduled in Celery beat |

The API requires authentication by default. The frontend `/announcements` route requires `view_news`; API results are not narrowed by per-user company access. Feature details: [docs/features/announcements.md](../../../docs/features/announcements.md).
