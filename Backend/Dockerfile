# ── Backend / Django + Celery / Scrapy Dockerfile ────────────────────────────
#
# Single image used for all three Render services:
#   web     → gunicorn config.wsgi:application
#   worker  → celery -A config worker --pool=solo -Q crawling
#   beat    → celery -A config beat   --scheduler django_celery_beat...

FROM python:3.12-slim AS base

# ── System dependencies ───────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        # Postgres client lib (psycopg)
        libpq-dev \
        # lxml / Scrapy
        build-essential \
        libxml2-dev \
        libxslt1-dev \
        # Pillow
        libjpeg-dev \
        libpng-dev \
        libtiff-dev \
        # curl for health-checks
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python dependencies ───────────────────────────────────────────────────────
COPY requirements.txt .

# sentence-transformers / torch can be very large — install without cache
# to avoid ballooning the layer.
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir gunicorn

# ── Application source ────────────────────────────────────────────────────────
COPY . .

# ── Runtime environment ───────────────────────────────────────────────────────
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings

# Collect static files at build time (Django admin CSS etc.).
# Requires a placeholder SECRET_KEY; real secrets come from the env at runtime.
RUN SECRET_KEY=build-time-placeholder \
    DB_PASSWORD=unused \
    python manage.py collectstatic --noinput

# ── Default command (overridden per Render service) ───────────────────────────
# Production web: gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
# Celery worker:  celery -A config worker --pool=solo -Q crawling -l info
# Celery beat:    celery -A config beat   --scheduler django_celery_beat.schedulers:DatabaseScheduler -l info
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]
