"""
Django settings for config project.
"""
from datetime import timedelta
from pathlib import Path
import os
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "django-insecure-change-me-in-production",
)

# Safe defaults: development turns these on explicitly in .env.
DEBUG = os.getenv("DEBUG", "False") == "True"

ALLOWED_HOSTS = os.getenv(
    "ALLOWED_HOSTS",
    "localhost,127.0.0.1,testserver",
).split(",")


# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_celery_beat",
    "django_filters",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "apps.analysis",
    "apps.companies",
    "apps.crawler_runs",
    "apps.market_data",
    "apps.news",
    "apps.users",
    "apps.dashboard",
    "apps.market_intelligence",
    
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# ---------------------------------------------------------------------------
# Database — credentials MUST come from environment variables.
# No passwords are hardcoded here.
# ---------------------------------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "stockmarket"),
        "USER": os.getenv("DB_USER", "postgres"),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
        "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
    }
}


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

AUTH_USER_MODEL = "users.User"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation"
            ".UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation.MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation.CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation.NumericPasswordValidator"
        ),
    },
]


# ---------------------------------------------------------------------------
# REST Framework & JWT
# ---------------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": (
        "rest_framework.pagination.PageNumberPagination"
    ),
    "PAGE_SIZE": 20,
    # Used by the login and registration views (throttle_scope = "auth")
    # and the unauthenticated landing-page endpoints (throttle_scope = "public").
    "DEFAULT_THROTTLE_RATES": {
        "auth": os.getenv("AUTH_THROTTLE_RATE", "10/min"),
        "public": os.getenv("PUBLIC_THROTTLE_RATE", "60/min"),
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}


# ---------------------------------------------------------------------------
# Celery
#
# Timezone note:
#   TIME_ZONE and CELERY_TIMEZONE must match so that Beat schedules fire at
#   the correct Nepal wall-clock time.  Both are set to Asia/Kathmandu.
#   CELERY_ENABLE_UTC=False tells Celery to interpret schedule times in the
#   local timezone rather than UTC.
# ---------------------------------------------------------------------------

CELERY_BROKER_URL = os.getenv(
    "CELERY_BROKER_URL",
    "redis://localhost:6379/0",
)

CELERY_RESULT_BACKEND = os.getenv(
    "CELERY_RESULT_BACKEND",
    "redis://localhost:6379/1",
)

CELERY_TIMEZONE = "Asia/Kathmandu"
CELERY_ENABLE_UTC = False  # interpret schedules in Nepal local time

# Default task time limits.  Individual tasks (run_crawl) set their own
# soft/hard limits; these act as a backstop for any other tasks.
CELERY_TASK_SOFT_TIME_LIMIT = 60 * 55   # 55 minutes
CELERY_TASK_TIME_LIMIT = 60 * 60        # 60 minutes (hard kill)

CELERY_TASK_ROUTES = {
    "apps.crawler_runs.tasks.*": {"queue": "crawling"},
    "apps.news.tasks.*": {"queue": "crawling"},
}
CELERY_TASK_DEFAULT_QUEUE = "crawling"

# Serialize task arguments as JSON (avoids pickle security issues).
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]

# Acknowledge task AFTER it completes (not when it is received).
# This means if a worker crashes mid-task the broker will re-queue it.
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1   # one task at a time per worker process

# ---------------------------------------------------------------------------
# NEPSE trading week
#   The single source of truth for which weekdays the exchange trades
#   (Python weekday numbers, Monday=0).  NEPSE trades Monday-Friday,
#   11:00-15:00 Asia/Kathmandu.  Public holidays live in the admin-editable
#   market_data.TradingHoliday table, not here.  Read through
#   apps.market_data.services.trading_days rather than hardcoding weekdays.
# ---------------------------------------------------------------------------
NEPSE_TRADING_WEEKDAYS = (0, 1, 2, 3, 4)

# Celery's crontab counts Sunday=0, Python's weekday() counts Monday=0.
TRADING_DAYS_CRONTAB = ",".join(str((day + 1) % 7) for day in NEPSE_TRADING_WEEKDAYS)

from celery.schedules import crontab  # noqa: E402

CELERY_BEAT_SCHEDULE = {
    # ---- News ----
    "crawl-news-every-hour": {
        "task": "apps.crawler_runs.tasks.crawl_all_news",
        "schedule": crontab(minute=0),
    },

    # ---- Trading prices ----
    # Trading days only; the tasks also skip TradingHoliday dates.
    "crawl-daily-prices-evening": {
        "task": "apps.crawler_runs.tasks.crawl_daily_prices",
        "schedule": crontab(minute=0, hour=18, day_of_week=TRADING_DAYS_CRONTAB),
    },
    "crawl-brokers-weekly": {
        "task": "apps.crawler_runs.tasks.crawl_brokers",
        "schedule": crontab(minute=0, hour=20, day_of_week=6),
    },

    # ---- Floorsheet ----
    # Full floorsheet for every tracked company: the latest session plus any
    # trading day still missing (replaces the old weekly sampled crawl).
    "crawl-floorsheet-evening": {
        "task": "apps.crawler_runs.tasks.crawl_floorsheet",
        "schedule": crontab(minute=15, hour=18, day_of_week=TRADING_DAYS_CRONTAB),
    },

    # ---- Analysis rebuild ----
    "rebuild-analysis-after-prices": {
        "task": "apps.analysis.tasks.rebuild_all_analysis",
        "schedule": crontab(minute=45, hour=18, day_of_week=TRADING_DAYS_CRONTAB),
    },
    "build-market-intelligence-after-analysis": {
        "task": "apps.market_intelligence.tasks.build_daily_market_intelligence",
        "schedule": crontab(minute=0, hour=19),
    },

    # ---- News categorization ----
    "categorize-unprocessed-news-every-10-minutes": {
        "task": "apps.news.tasks.categorize_unprocessed_news_task",
        "schedule": crontab(minute="*/10"),
    },

    # ---- Stale-run recovery ----
    # Runs every 2 hours; marks truly stuck runs (>90 min old) as FAILED.
    "recover-stale-crawls": {
        "task": "apps.crawler_runs.tasks.recover_stale_crawls",
        "schedule": crontab(minute=30, hour="*/2"),
    },
}


# ---------------------------------------------------------------------------
# Redis (used by the application directly, separate from Celery broker URL)
# ---------------------------------------------------------------------------

REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://localhost:6379/0",
)


# ---------------------------------------------------------------------------
# Internationalization
# Keep TIME_ZONE in sync with CELERY_TIMEZONE above.
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kathmandu"
USE_I18N = True
USE_TZ = True


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

CORS_ALLOWED_ORIGINS = [
    FRONTEND_URL,
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://localhost:5174",
]
CORS_ALLOW_ALL_ORIGINS = os.getenv("CORS_ALLOW_ALL_ORIGINS", "False") == "True"
CORS_ALLOW_CREDENTIALS = True


# ---------------------------------------------------------------------------
# Automatic news categorisation settings
# ---------------------------------------------------------------------------

CATEGORIZATION_EMBEDDING_MODEL = os.getenv(
    "CATEGORIZATION_EMBEDDING_MODEL",
    "all-MiniLM-L6-v2",
)
CATEGORIZATION_EMBEDDING_WEIGHT = float(
    os.getenv("CATEGORIZATION_EMBEDDING_WEIGHT", "0.60")
)
CATEGORIZATION_KEYWORD_WEIGHT = float(
    os.getenv("CATEGORIZATION_KEYWORD_WEIGHT", "0.40")
)
CATEGORIZATION_THRESHOLD = float(
    os.getenv("CATEGORIZATION_THRESHOLD", "0.65")
)
CATEGORIZATION_SEMANTIC_ONLY_THRESHOLD = float(
    os.getenv("CATEGORIZATION_SEMANTIC_ONLY_THRESHOLD", "0.75")
)
CATEGORIZATION_SEMANTIC_REVIEW_FLOOR = float(
    os.getenv("CATEGORIZATION_SEMANTIC_REVIEW_FLOOR", "0.60")
)
SENTIMENT_METHOD = os.getenv("SENTIMENT_METHOD", "lexicon")
