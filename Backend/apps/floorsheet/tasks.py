"""
Intraday candles.
The live task polls ShareHub for the tracked companies during the session
and rebuilds today's candles; the after-close task re-reads every page and
recomputes the whole day, fixing late or out-of-order rows.
"""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)

# Accept live runs from the open until a few minutes after the close.
INTRADAY_LIVE_GRACE = 10  # minutes after SESSION_CLOSE


def _sync_and_rebuild_today(task_name, incremental):
    from datetime import datetime, timedelta

    from django.utils import timezone

    from apps.companies.services.selection import tracked_active_companies
    from apps.floorsheet.services import intraday_candles
    from apps.floorsheet.services.sharehub_floorsheet import sync_day
    from apps.market_data.services.trading_days import market_closed_reason

    today = timezone.localdate()
    reason = market_closed_reason(today)
    if reason:
        logger.info("%s: skipping — %s.", task_name, reason)
        return {"skipped": True, "reason": reason}

    if incremental:
        session_open, session_close = intraday_candles.session_bounds(today)
        now = datetime.now(intraday_candles.NPT)
        if not session_open <= now <= session_close + timedelta(minutes=INTRADAY_LIVE_GRACE):
            return {"skipped": True, "reason": "outside market hours"}

    companies = list(tracked_active_companies())
    sync = sync_day(today, companies, incremental=incremental)
    candles = intraday_candles.rebuild_day(today, company_ids=[company.pk for company in companies])
    result = {"sync": sync, "candles": candles}
    logger.info("%s: %s", task_name, result)
    return result


@shared_task(name="apps.floorsheet.tasks.build_intraday_candles_live")
def build_intraday_candles_live():
    """Every few minutes in the session: new ShareHub trades + today's candles."""
    return _sync_and_rebuild_today("build_intraday_candles_live", incremental=True)


@shared_task(name="apps.floorsheet.tasks.finalize_intraday_candles")
def finalize_intraday_candles():
    """After the close: full ShareHub re-read and full recompute of today's candles."""
    return _sync_and_rebuild_today("finalize_intraday_candles", incremental=False)
