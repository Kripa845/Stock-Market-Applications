"""
Circuit breaker for scheduled feed polls (NEPSE live prices, NEPSE live index).

After ``threshold`` failed runs in a row the breaker opens and the task stops calling
the source for ``pause_seconds``, so a blocked or broken feed is not hit every few
minutes all session.  State lives in Redis (the Celery broker), not Django's
per-process cache, so every worker process sees the same count.

Keys: ``<name>:consecutive_failures`` and ``<name>:paused``.
"""

import logging

logger = logging.getLogger(__name__)


def broker_redis():
    import redis
    from django.conf import settings

    return redis.Redis.from_url(settings.CELERY_BROKER_URL)


class CircuitBreaker:
    def __init__(self, redis_client, name, threshold=3, pause_seconds=30 * 60):
        self.redis = redis_client
        self.name = name
        self.threshold = threshold
        self.pause_seconds = pause_seconds
        self.failures_key = f"{name}:consecutive_failures"
        self.open_key = f"{name}:paused"

    def is_open(self):
        return bool(self.redis.exists(self.open_key))

    def seconds_left(self):
        return self.redis.ttl(self.open_key)

    def record_failure(self):
        """Count a failed run; returns True when this failure opened the breaker."""
        if self.redis.incr(self.failures_key) < self.threshold:
            return False
        self.redis.set(self.open_key, 1, ex=self.pause_seconds)
        self.redis.delete(self.failures_key)
        logger.error("%s: %d failures in a row, pausing for %d minutes",
                     self.name, self.threshold, self.pause_seconds // 60)
        return True

    def record_success(self):
        self.redis.delete(self.failures_key)
