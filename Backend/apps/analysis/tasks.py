

# from __future__ import annotations

# import logging

# from celery import shared_task

# from apps.analysis.models import DailyAnalysis
# from apps.analysis.services.daily_metrics import (
#     BASELINE_SESSIONS,
#     calculate_period_vwap,
#     rebuild_company_analysis,
# )
# from apps.companies.models import Company
# from apps.market_data.models import DailyPrice
# from apps.market_data.services.trading_calendar import rolling_window_bounds


# logger = logging.getLogger(__name__)

# #: Length of the rolling summary window, in calendar days.
# SUMMARY_WINDOW_DAYS = 31


# @shared_task(bind=True)
# def rebuild_company_analysis_task(self, company_id, since=None):
#     """
#     Recompute ``DailyAnalysis`` for one company.

#     ``since`` is an optional ISO date string; omit it to rebuild the
#     company's full history.
#     """
#     from datetime import date as date_cls

#     try:
#         company = Company.objects.get(pk=company_id)
#     except Company.DoesNotExist:
#         logger.error("rebuild_company_analysis_task: company %s missing", company_id)
#         return {"company_id": company_id, "rows": 0, "error": "company_not_found"}

#     since_date = None
#     if since:
#         since_date = (
#             since
#             if isinstance(since, date_cls)
#             else date_cls.fromisoformat(str(since))
#         )

#     rows = rebuild_company_analysis(company, since=since_date)

#     _update_period_vwap(company)

#     logger.info(
#         "Analysis rebuilt | company=%s | rows=%s | baseline_sessions=%s",
#         company.symbol,
#         len(rows),
#         BASELINE_SESSIONS,
#     )

#     return {
#         "company_id": company.id,
#         "symbol": company.symbol,
#         "rows": len(rows),
#     }


# @shared_task(bind=True)
# def rebuild_all_analysis(self, since=None):
#     """
#     Recompute ``DailyAnalysis`` for every active company.

#     Scheduled to run shortly after the daily price crawl so the stored
#     analytical state always reflects the freshest DailyPrice rows.
#     A failure on one company is logged and skipped — it must not stop
#     the remaining companies from being analysed.
#     """
#     from datetime import date as date_cls

#     since_date = None
#     if since:
#         since_date = (
#             since
#             if isinstance(since, date_cls)
#             else date_cls.fromisoformat(str(since))
#         )

#     companies = Company.objects.filter(is_active=True).order_by("symbol")

#     processed = 0
#     failed = []
#     total_rows = 0

#     for company in companies:
#         try:
#             rows = rebuild_company_analysis(company, since=since_date)
#             _update_period_vwap(company)
#             total_rows += len(rows)
#             processed += 1
#         except Exception as exc:  # noqa: BLE001 - one bad company must not halt the run
#             logger.exception("Analysis failed for %s: %s", company.symbol, exc)
#             failed.append(company.symbol)

#     logger.info(
#         "Analysis pass finished | companies=%s | rows=%s | failed=%s",
#         processed,
#         total_rows,
#         len(failed),
#     )

#     return {
#         "companies_processed": processed,
#         "rows_written": total_rows,
#         "failed": failed,
#     }


# def _update_period_vwap(company):
#     """
#     Stamp the separate 30-day aggregate VWAP onto the rows inside the
#     current rolling window.

#     This is a summary metric kept deliberately distinct from the per-day
#     ``vwap`` column: it answers "what did this stock average over the
#     window", not "what did it average today".
#     """
#     start_date, end_date = rolling_window_bounds(
#         window_days=SUMMARY_WINDOW_DAYS,
#         company=company,
#     )

#     if start_date is None:
#         return None

#     window_prices = DailyPrice.objects.filter(
#         company=company,
#         date__gte=start_date,
#         date__lte=end_date,
#     )

#     period_vwap = calculate_period_vwap(window_prices)

#     DailyAnalysis.objects.filter(
#         company=company,
#         date__gte=start_date,
#         date__lte=end_date,
#     ).update(vwap_30d=period_vwap)

#     return period_vwap

from __future__ import annotations

import logging

from celery import shared_task

from apps.analysis.models import DailyAnalysis
from apps.analysis.services.daily_metrics import (
    BASELINE_SESSIONS,
    calculate_period_vwap,
    rebuild_company_analysis,
)
from apps.companies.models import Company
from apps.market_data.models import DailyPrice
from apps.market_data.services.trading_calendar import rolling_window_bounds


logger = logging.getLogger(__name__)

#: Length of the rolling summary window, in calendar days.
SUMMARY_WINDOW_DAYS = 31


@shared_task(bind=True)
def rebuild_company_analysis_task(self, company_id, since=None):
    """
    Recompute ``DailyAnalysis`` for one company.

    ``since`` is an optional ISO date string; omit it to rebuild the
    company's full history.
    """
    from datetime import date as date_cls

    try:
        company = Company.objects.get(pk=company_id)
    except Company.DoesNotExist:
        logger.error("rebuild_company_analysis_task: company %s missing", company_id)
        return {"company_id": company_id, "rows": 0, "error": "company_not_found"}

    since_date = None
    if since:
        since_date = (
            since
            if isinstance(since, date_cls)
            else date_cls.fromisoformat(str(since))
        )

    rows = rebuild_company_analysis(company, since=since_date)

    _update_period_vwap(company)
    _rebuild_persisted_market_features(company)

    logger.info(
        "Analysis rebuilt | company=%s | rows=%s | baseline_sessions=%s",
        company.symbol,
        len(rows),
        BASELINE_SESSIONS,
    )

    return {
        "company_id": company.id,
        "symbol": company.symbol,
        "rows": len(rows),
    }


@shared_task(bind=True)
def rebuild_all_analysis(self, since=None):
    """
    Recompute ``DailyAnalysis`` for every active company.

    Scheduled to run shortly after the daily price crawl so the stored
    analytical state always reflects the freshest DailyPrice rows.
    A failure on one company is logged and skipped — it must not stop
    the remaining companies from being analysed.
    """
    from datetime import date as date_cls

    since_date = None
    if since:
        since_date = (
            since
            if isinstance(since, date_cls)
            else date_cls.fromisoformat(str(since))
        )

    companies = Company.objects.filter(is_active=True).order_by("symbol")

    processed = 0
    failed = []
    total_rows = 0

    for company in companies:
        try:
            rows = rebuild_company_analysis(company, since=since_date)
            _update_period_vwap(company)
            _rebuild_persisted_market_features(company)
            total_rows += len(rows)
            processed += 1
        except Exception as exc:  # noqa: BLE001 - one bad company must not halt the run
            logger.exception("Analysis failed for %s: %s", company.symbol, exc)
            failed.append(company.symbol)

    logger.info(
        "Analysis pass finished | companies=%s | rows=%s | failed=%s",
        processed,
        total_rows,
        len(failed),
    )

    return {
        "companies_processed": processed,
        "rows_written": total_rows,
        "failed": failed,
    }


def _rebuild_persisted_market_features(company):
    """Refresh both persisted features after the existing analysis crawl task."""
    from apps.analysis.services.volume_anomaly import rebuild_company_volume_anomalies
    from apps.analysis.services.news_price_correlation import rebuild_company_news_price_correlation

    for feature_name, rebuild in (
        ("volume anomalies", rebuild_company_volume_anomalies),
        ("news-price correlation", rebuild_company_news_price_correlation),
    ):
        try:
            rebuild(company)
        except Exception as exc:  # noqa: BLE001 - a bad feature/company must not stop other analysis
            logger.exception("Could not refresh %s for %s: %s", feature_name, company.symbol, exc)


def _update_period_vwap(company):
    """
    Stamp the separate 30-day aggregate VWAP onto the rows inside the
    current rolling window.

    This is a summary metric kept deliberately distinct from the per-day
    ``vwap`` column: it answers "what did this stock average over the
    window", not "what did it average today".
    """
    start_date, end_date = rolling_window_bounds(
        window_days=SUMMARY_WINDOW_DAYS,
        company=company,
    )

    if start_date is None:
        return None

    window_prices = DailyPrice.objects.filter(
        company=company,
        source="crawled",
        date__gte=start_date,
        date__lte=end_date,
    )

    period_vwap = calculate_period_vwap(window_prices)

    DailyAnalysis.objects.filter(
        company=company,
        date__gte=start_date,
        date__lte=end_date,
    ).update(vwap_30d=period_vwap)

    return period_vwap
