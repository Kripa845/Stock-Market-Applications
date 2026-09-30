import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="apps.market_intelligence.tasks.build_daily_market_intelligence")
def build_daily_market_intelligence():
    """Compute snapshots without allowing a failure to escape into the crawl chain."""
    try:
        from apps.market_intelligence.services.sector_rotation import compute_sector_rotation_snapshots
        from apps.market_intelligence.services.snapshots import compute_market_snapshots
        from apps.market_intelligence.services.technicals import compute_company_technical_snapshots

        result = {
            "market": compute_market_snapshots(),
            "technicals": compute_company_technical_snapshots(),
            "sectors": compute_sector_rotation_snapshots(),
        }
        logger.info("Daily market intelligence snapshots built: %s", result)
        return {"ok": True, **result}
    except Exception:
        logger.exception("Daily market intelligence build failed; crawl chain may continue.")
        return {"ok": False, "error": "market intelligence build failed"}
