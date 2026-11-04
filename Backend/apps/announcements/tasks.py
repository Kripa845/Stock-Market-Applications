from celery import shared_task

from .services import sync_announcements


@shared_task
def sync_announcements_task(days_back: int = 3) -> int:
    return sync_announcements(days_back)