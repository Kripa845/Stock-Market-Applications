from .settings import *  # noqa: F401,F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

# The suite logs in far more than 10 times a minute; throttling has its own test.
REST_FRAMEWORK = {**REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": {"auth": "10000/min", "public": "10000/min"}}  # noqa: F405
