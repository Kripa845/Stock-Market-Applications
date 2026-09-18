# Starting Celery Workers on Windows

## Prerequisites

1. **Redis** must be running before starting any Celery process.
   - Download: https://github.com/microsoftarchive/redis/releases
   - Or via WSL: `sudo service redis-server start`
   - Verify: `redis-cli ping` should return `PONG`

2. Activate the virtual environment:
   ```
   .\venv\Scripts\activate
   ```

3. Make sure you are in the `Backend/` directory for all commands below.

---

## Start the Celery Worker (Windows)

Windows does not support the default `fork` prefork pool.
You **must** use `--pool=solo` or `--pool=threads`.

```bat
celery -A config worker --pool=solo -Q crawling -l info
```

Or, if you want more concurrency (requires `gevent` installed):

```bat
pip install gevent
celery -A config worker --pool=gevent --concurrency=4 -Q crawling -l info
```

---

## Start Celery Beat (scheduler)

Run this in a **separate terminal** from the worker:

```bat
celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

---

## Schedules configured

| Task | Schedule | What it does |
|---|---|---|
| `crawl_all_news` | Every hour (:00) | Crawls all news sources |
| `crawl_daily_prices` | Daily 18:00 NPT | Collects OHLCV data for all companies |
| `crawl_floorsheet` | Daily 18:15 NPT | Collects last 5 days of floorsheet transactions |
| `categorize_unprocessed_news` | Every 10 minutes | Runs ML categorisation on new articles |

---

## Manual one-off crawls (without Celery)

You can also run spiders directly from the `Backend/crawlers/` directory:

```bat
# Daily price data (last 50 rows ≈ 2 months per company)
python -m scrapy crawl trading_data

# Floorsheet — last 5 days (default)
python -m scrapy crawl floorsheet

# Floorsheet — last 10 days
python -m scrapy crawl floorsheet -a floorsheet_days_back=10

# Floorsheet — specific single date
python -m scrapy crawl floorsheet -a floorsheet_date=2026-09-16

# News (single source)
python -m scrapy crawl sharesansar
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `kombu.exceptions.OperationalError: [Errno 111] Connection refused` | Redis is not running. Start Redis first. |
| `ValueError: not enough values to unpack` on Windows | Use `--pool=solo` |
| Spider hangs immediately | Check that `DJANGO_SETTINGS_MODULE=config.settings` is set in the environment |
| `No module named scrapy` in worker | The worker is using a different Python. Activate `venv` first. |
