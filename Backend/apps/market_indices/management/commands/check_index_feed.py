from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.market_data.services.trading_days import is_market_open, market_closed_reason
from apps.market_indices.models import IndexIntradayPoint

TASK = "apps.market_indices.tasks.snapshot_live_index"


class Command(BaseCommand):
    help = "Check that the Celery worker and beat are running and NEPSE index ticks are being saved."

    def handle(self, *args, **opts):
        from config.celery import app

        now = timezone.localtime()
        self.stdout.write(f"Now: {now:%Y-%m-%d %H:%M:%S} Nepal time | CELERY_TIMEZONE={settings.CELERY_TIMEZONE} "
                          f"enable_utc={settings.CELERY_ENABLE_UTC}")
        reason = market_closed_reason(now.date())
        self.stdout.write(f"Market: {'OPEN' if is_market_open() else 'closed'}"
                          + (f" ({reason})" if reason else " (trading day, 11:00-15:00)"))

        # Broker
        try:
            with app.connection_for_read() as conn:
                conn.ensure_connection(max_retries=1, timeout=3)
            self._ok(f"Broker reachable: {settings.CELERY_BROKER_URL}")
        except Exception as exc:
            self._bad(f"Broker NOT reachable ({exc}); start Redis first")
            return

        # Worker
        inspect = app.control.inspect(timeout=3)
        registered = inspect.registered() or {}
        queues = inspect.active_queues() or {}
        if not registered:
            self._bad("No Celery worker answered. Start one:  celery -A config worker --pool=solo -Q crawling -l info")
        for worker, tasks in registered.items():
            names = sorted(q["name"] for q in queues.get(worker, []))
            self._ok(f"Worker {worker} listening on {names}")
            if TASK in tasks:
                self._ok("  snapshot_live_index is registered")
            else:
                self._bad("  snapshot_live_index is NOT registered: this worker started before the task existed. "
                          "Restart the worker.")
            if settings.CELERY_TASK_DEFAULT_QUEUE not in names:
                self._bad(f"  worker does not consume '{settings.CELERY_TASK_DEFAULT_QUEUE}', where the task is sent")

        # Beat: the schedule entries, and signs that beat is alive
        for name, entry in settings.CELERY_BEAT_SCHEDULE.items():
            if entry["task"] == TASK:
                self.stdout.write(f"Beat entry '{name}': {entry['schedule']}")
        self._beat_heartbeat(now)

        # Ticks
        points = IndexIntradayPoint.objects.filter(index__code="NEPSE")
        today = points.filter(recorded_at__date=now.date()).count()
        last = points.order_by("-recorded_at").first()
        if last is None:
            self._bad("No NEPSE ticks stored yet")
            return
        age = now - last.recorded_at
        line = f"NEPSE ticks today: {today} | last {timezone.localtime(last.recorded_at):%Y-%m-%d %H:%M:%S} = {last.value}"
        if is_market_open() and age > timedelta(minutes=5):
            self._bad(line + f" | {int(age.total_seconds() // 60)} min old during the session: ticks are NOT arriving")
        else:
            self._ok(line)

    def _beat_heartbeat(self, now):
        scheduler_files = list(Path(settings.BASE_DIR).glob("celerybeat-schedule*"))
        if scheduler_files:
            touched = max(datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.get_current_timezone())
                          for p in scheduler_files)
            minutes = int((now - touched).total_seconds() // 60)
            message = f"Beat state file last written {touched:%H:%M:%S} ({minutes} min ago)"
            # Beat rewrites its state file every few minutes while running.
            (self._ok if minutes <= 10 else self._bad)(
                message + ("" if minutes <= 10 else ": beat looks stopped. Start it:  celery -A config beat -l info"))
        try:
            from django_celery_beat.models import PeriodicTask

            last_runs = [t.last_run_at for t in PeriodicTask.objects.filter(task=TASK) if t.last_run_at]
            if last_runs:
                self.stdout.write(f"DatabaseScheduler last sent the task at {timezone.localtime(max(last_runs)):%Y-%m-%d %H:%M:%S}")
        except Exception:
            pass

    def _ok(self, message):
        self.stdout.write(self.style.SUCCESS("OK   ") + message)

    def _bad(self, message):
        self.stdout.write(self.style.ERROR("FAIL ") + message)
