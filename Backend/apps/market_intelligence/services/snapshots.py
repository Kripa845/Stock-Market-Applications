"""Deterministic daily market calculations sourced only from DailyPrice."""

from datetime import date
from decimal import Decimal, InvalidOperation
from math import ceil

from django.conf import settings
from django.db import transaction

from apps.analysis.models import DailyAnalysis
from apps.market_data.models import DailyPrice
from apps.market_intelligence.models import MarketBreadthSnapshot, ProxyIndexSnapshot
from apps.market_intelligence.app_settings import MARKET_INTELLIGENCE_EXCLUDED_SESSIONS as DEFAULT_EXCLUDED_SESSIONS

BASE_INDEX_LEVEL = Decimal("1000")
PROXY_METHODOLOGY_VERSION = "turnover-weighted-v1"
DMA_COVERAGE_RATIO = Decimal("0.95")


def _decimal(value):
    try:
        return Decimal(str(value)) if value is not None else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def _configured_excluded_dates():
    """Read optional ISO dates from Django settings, defaulting to none."""
    values = getattr(
        settings,
        "MARKET_INTELLIGENCE_EXCLUDED_SESSIONS",
        DEFAULT_EXCLUDED_SESSIONS,
    ) or []
    excluded = set()
    for value in values:
        if isinstance(value, date):
            excluded.add(value)
        else:
            excluded.add(date.fromisoformat(str(value)))
    return excluded


def _trading_calendar(prices, manual_exclusions):
    """Return valid global sessions and a date-to-reasons exclusion mapping.

    Friday (weekday 4) and Saturday (weekday 5) are excluded. A duplicate
    market-wide date is excluded only when every company represented on that
    date also has a row on the prior raw date, with unchanged close and either
    unchanged or zero volume. Rows themselves are never changed or deleted.
    """
    rows_by_date = {}
    for row in prices:
        rows_by_date.setdefault(row.date, {})[row.company_id] = row
    raw_dates = sorted(rows_by_date)
    excluded = {}
    prior_raw_date = {day: raw_dates[index - 1] if index else None for index, day in enumerate(raw_dates)}

    for day in raw_dates:
        reasons = []
        if day.weekday() in (4, 5):
            reasons.append("weekend (NEPSE closed Friday/Saturday)")
        if day in manual_exclusions:
            reasons.append("manual exclusion: MARKET_INTELLIGENCE_EXCLUDED_SESSIONS")

        previous_day = prior_raw_date[day]
        current_rows = rows_by_date[day]
        previous_rows = rows_by_date.get(previous_day, {}) if previous_day else {}
        if current_rows and set(current_rows) == set(previous_rows) and all(
            company_id in previous_rows
            and _decimal(row.close) == _decimal(previous_rows[company_id].close)
            and (
                row.volume == previous_rows[company_id].volume
                or row.volume == 0
            )
            for company_id, row in current_rows.items()
        ):
            reasons.append("duplicate date: all closes unchanged and volume unchanged or zero")

        if reasons:
            excluded[day] = reasons

    sessions = [day for day in raw_dates if day not in excluded]
    return sessions, excluded


def _corporate_action_flags(prices, sessions, analysis_rows):
    """Flag >10% session moves or inconsistent stored previous-close values."""
    by_date_company = {(row.date, row.company_id): row for row in prices}
    company_ids = sorted({row.company_id for row in prices})
    flagged = set()
    for index, current_date in enumerate(sessions):
        if index == 0:
            continue
        prior_date = sessions[index - 1]
        for company_id in company_ids:
            row = by_date_company.get((current_date, company_id))
            prior = by_date_company.get((prior_date, company_id))
            if row is None or prior is None:
                continue
            prior_close = _decimal(prior.close)
            close = _decimal(row.close)
            analysis = analysis_rows.get((company_id, current_date))
            stored_previous_close = _decimal(analysis.previous_close) if analysis else None
            mismatch = stored_previous_close is not None and stored_previous_close != prior_close
            circuit_move = False
            if prior_close is not None and prior_close > 0 and close is not None:
                change = (close - prior_close) / prior_close
                circuit_move = change > Decimal("0.10") or change < Decimal("-0.10")
            if mismatch or circuit_move:
                flagged.add((company_id, current_date))
    return flagged


def compute_market_snapshots(dry_run=False):
    """Compute breadth and proxy snapshots for every valid DailyPrice date.

    A market session is a distinct valid date found in DailyPrice, after
    excluding Fridays/Saturdays, configured manual exclusions and dates where
    every represented company repeats its previous raw close and volume.

    DMA windows are the last N *global market-session dates*, including the
    scored date. No prices are carried forward. At least 95% of those dates
    must have an unflagged stock row; that means 48/50 or 190/200 rows. The
    average uses only those observed rows. A missing current stock row or a
    corporate-action-flagged current row is never included in breadth.

    Daily breadth returns require rows on both adjacent valid market sessions.
    The proxy uses previous valid-session turnover weights and excludes a
    return when either stock-day is possible_corporate_action. Its base is
    1000 on the first valid session, whose return remains null.
    """
    prices = list(DailyPrice.objects.filter(source="crawled").order_by("date", "company_id", "pk"))
    manual_exclusions = _configured_excluded_dates()
    sessions, excluded_dates = _trading_calendar(prices, manual_exclusions)

    if not sessions:
        result = {
            "sessions": 0,
            "breadth": 0,
            "proxy": 0,
            "excluded_dates": excluded_dates,
            "corporate_action_excluded_count": 0,
        }
        if dry_run:
            return result
        with transaction.atomic():
            MarketBreadthSnapshot.objects.all().delete()
            ProxyIndexSnapshot.objects.all().delete()
        return result

    by_date_company = {(row.date, row.company_id): row for row in prices}
    company_ids = sorted({row.company_id for row in prices})
    by_company = {company_id: {} for company_id in company_ids}
    for row in prices:
        by_company[row.company_id][row.date] = row
    analyses = {
        (row.company_id, row.date): row
        for row in DailyAnalysis.objects.filter(date__in=sessions).only(
            "company_id", "date", "previous_close"
        )
    }
    corporate_flags = _corporate_action_flags(prices, sessions, analyses)

    breadth_rows = []
    proxy_rows = []
    last_valid_level = BASE_INDEX_LEVEL
    total_corporate_exclusions = 0

    for index, session_date in enumerate(sessions):
        current = {company_id: by_date_company.get((session_date, company_id)) for company_id in company_ids}
        previous_date = sessions[index - 1] if index else None
        advances = declines = unchanged = return_eligible = 0
        above_50 = valid_50 = above_200 = valid_200 = 0
        corporate_count = sum(
            1 for company_id in company_ids
            if (company_id, session_date) in corporate_flags
        )
        total_corporate_exclusions += corporate_count

        for company_id, current_row in current.items():
            if current_row is None or (company_id, session_date) in corporate_flags:
                continue
            close = _decimal(current_row.close)
            if close is None:
                continue

            previous_row = by_date_company.get((previous_date, company_id)) if previous_date else None
            if previous_row is not None and (company_id, previous_date) not in corporate_flags:
                previous_close = _decimal(previous_row.close)
                if previous_close is not None and previous_close != 0:
                    return_eligible += 1
                    change = close - previous_close
                    if change > 0:
                        advances += 1
                    elif change < 0:
                        declines += 1
                    else:
                        unchanged += 1

            for window in (50, 200):
                if index + 1 < window:
                    continue
                window_dates = sessions[index - window + 1:index + 1]
                stock_rows = [
                    by_company[company_id].get(day)
                    for day in window_dates
                    if by_company[company_id].get(day) is not None
                    and (company_id, day) not in corporate_flags
                ]
                required = ceil(window * float(DMA_COVERAGE_RATIO))
                if len(stock_rows) < required:
                    continue
                average = sum((_decimal(row.close) for row in stock_rows), Decimal("0")) / Decimal(len(stock_rows))
                if window == 50:
                    valid_50 += 1
                    above_50 += close > average
                else:
                    valid_200 += 1
                    above_200 += close > average

        breadth_rows.append({
            "date": session_date,
            "market_session_count": index + 1,
            "advances": advances,
            "declines": declines,
            "unchanged": unchanged,
            "return_eligible_count": return_eligible,
            "above_50_dma_count": above_50,
            "valid_50_dma_count": valid_50,
            "above_50_dma_pct": (Decimal(above_50) * 100 / valid_50) if valid_50 else None,
            "above_200_dma_count": above_200,
            "valid_200_dma_count": valid_200,
            "above_200_dma_pct": (Decimal(above_200) * 100 / valid_200) if valid_200 else None,
            "corporate_action_excluded_count": corporate_count,
        })

        weighted_return = Decimal("0")
        total_weight = Decimal("0")
        eligible = 0
        if previous_date is not None:
            for company_id, current_row in current.items():
                previous_row = by_date_company.get((previous_date, company_id))
                if current_row is None or previous_row is None:
                    continue
                if (company_id, session_date) in corporate_flags or (company_id, previous_date) in corporate_flags:
                    continue
                prior_close = _decimal(previous_row.close)
                prior_turnover = _decimal(previous_row.turnover)
                current_close = _decimal(current_row.close)
                if prior_close is None or prior_close <= 0 or prior_turnover is None or prior_turnover <= 0 or current_close is None:
                    continue
                weighted_return += ((current_close - prior_close) / prior_close) * prior_turnover
                total_weight += prior_turnover
                eligible += 1

        return_pct = (weighted_return / total_weight * 100) if total_weight else None
        if return_pct is not None:
            last_valid_level *= Decimal("1") + return_pct / 100
            level = last_valid_level
        elif index == 0:
            level = BASE_INDEX_LEVEL
        else:
            level = None
        proxy_rows.append({
            "date": session_date,
            "level": level,
            "daily_return_pct": return_pct,
            "eligible_company_count": eligible,
            "methodology_version": PROXY_METHODOLOGY_VERSION,
            "corporate_action_excluded_count": corporate_count,
        })

    result = {
        "sessions": len(sessions),
        "breadth": len(breadth_rows),
        "proxy": len(proxy_rows),
        "excluded_dates": excluded_dates,
        "corporate_action_excluded_count": total_corporate_exclusions,
    }
    if dry_run:
        return result

    with transaction.atomic():
        for row in breadth_rows:
            values = dict(row)
            day = values.pop("date")
            MarketBreadthSnapshot.objects.update_or_create(date=day, defaults=values)
        for row in proxy_rows:
            values = dict(row)
            day = values.pop("date")
            ProxyIndexSnapshot.objects.update_or_create(date=day, defaults=values)

        # Remove only stale computed dates if source prices were intentionally removed.
        valid_dates = set(sessions)
        MarketBreadthSnapshot.objects.exclude(date__in=valid_dates).delete()
        ProxyIndexSnapshot.objects.exclude(date__in=valid_dates).delete()

    return result
