# Announcements

The **Announcements** page (`/announcements`) shows ShareHub notices and events for tracked companies plus market-wide NEPSE items. Cards show the symbol (or NEPSE), company name, source, category, type and publication time in Nepal time. A link opens the source details in a new tab when one is available.

## Filters

The page supports a tracked symbol, event flag, announcement type, source, category and publication date range. Options come from `GET /api/announcements/filters/`. The announcement list is newest first and paginated at 12 items per page.

## API and access

| Method | Endpoint | Behavior |
|---|---|---|
| `GET` | `/api/announcements/` | Paginated list; accepts `symbol`, `is_event=true|false`, `type`, `source`, `category`, `date_from=YYYY-MM-DD`, `date_to=YYYY-MM-DD`, and `size` (maximum 100). |
| `GET` | `/api/announcements/filters/` | Filter choices and tracked symbols configured by the backend. |

The API requires authentication using the project-wide DRF default. The frontend route also requires `view_news`. The API does not narrow announcements by `UserCompanyAccess`.

## Refreshing the feed

The backend reads ShareHub's JSON endpoint and upserts entries by `external_id`. The command fetches recent pages, keeps market-wide notices and configured tracked symbols, and defaults to the last 7 days:

```powershell
cd Backend
venv\Scripts\python.exe manage.py sync_announcements [--days 90] [--debug]
```

`sync_announcements_task` exists, but Celery beat does not schedule it. Refreshes are manual unless a task is added to the schedule.
