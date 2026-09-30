"""Rolling sector returns/ranks using previous-session turnover weights."""

from decimal import Decimal

from django.db import transaction

from apps.market_data.models import DailyPrice
from apps.market_intelligence.models import SectorRotationSnapshot
from apps.market_intelligence.services.snapshots import (
    _corporate_action_flags,
    _configured_excluded_dates,
    _decimal,
    _trading_calendar,
)

PERIODS = {"1w": 5, "1m": 21, "3m": 63}


def compute_sector_rotation_snapshots():
    prices = list(DailyPrice.objects.filter(source="crawled").select_related("company").order_by("date", "company_id", "pk"))
    sessions, _ = _trading_calendar(prices, _configured_excluded_dates())
    if not sessions:
        SectorRotationSnapshot.objects.all().delete()
        return {"sessions": 0, "snapshots": 0}

    lookup = {(row.date, row.company_id): row for row in prices}
    analyses = {}
    from apps.analysis.models import DailyAnalysis
    analyses = {
        (row.company_id, row.date): row
        for row in DailyAnalysis.objects.filter(date__in=sessions).only("company_id", "date", "previous_close")
    }
    flags = _corporate_action_flags(prices, sessions, analyses)
    sector_by_company = {row.company_id: row.company.sector for row in prices}
    current_returns = {period: {} for period in PERIODS}

    def sector_returns(end_index, session_count):
        start_index = end_index - session_count
        if start_index < 0:
            return {}
        start_day, end_day = sessions[start_index], sessions[end_index]
        sums, weights, counts = {}, {}, {}
        for company_id, sector in sector_by_company.items():
            start = lookup.get((start_day, company_id))
            end = lookup.get((end_day, company_id))
            if not start or not end or (company_id, start_day) in flags or (company_id, end_day) in flags:
                continue
            observed = sum(
                1 for day in sessions[start_index:end_index + 1]
                if (day, company_id) in lookup and (company_id, day) not in flags
            )
            if observed < (len(sessions[start_index:end_index + 1]) * 95 + 99) // 100:
                continue
            base = _decimal(start.close)
            weight = _decimal(start.turnover)
            finish = _decimal(end.close)
            if base is None or base <= 0 or weight is None or weight <= 0 or finish is None:
                continue
            sums[sector] = sums.get(sector, Decimal("0")) + (finish - base) / base * weight
            weights[sector] = weights.get(sector, Decimal("0")) + weight
            counts[sector] = counts.get(sector, 0) + 1
        return {
            sector: (sums[sector] / weights[sector] * 100, weights[sector], counts[sector])
            for sector in sums if weights[sector]
        }

    ranks = {period: {} for period in PERIODS}
    for index in range(len(sessions)):
        for period, count in PERIODS.items():
            values = sector_returns(index, count)
            current_returns[period][index] = values
            ordered = sorted(values, key=lambda sector: (-values[sector][0], sector))
            ranks[period][index] = {sector: rank for rank, sector in enumerate(ordered, 1)}

    rows = []
    sectors = sorted({row.company.sector for row in prices})
    for index, day in enumerate(sessions):
        for sector in sectors:
            snapshot = {"sector": sector, "date": day}
            any_data = False
            latest_turnover = Decimal("0")
            latest_count = 0
            for period, count in PERIODS.items():
                values = current_returns[period].get(index, {})
                item = values.get(sector)
                snapshot[f"return_{period}"] = item[0] if item else None
                snapshot[f"rank_{period}"] = ranks[period].get(index, {}).get(sector)
                prior_index = index - count
                snapshot[f"previous_rank_{period}"] = ranks[period].get(prior_index, {}).get(sector)
                if item:
                    any_data = True
                    latest_turnover = max(latest_turnover, item[1])
                    latest_count = max(latest_count, item[2])
            if any_data:
                snapshot["turnover"] = latest_turnover
                snapshot["company_count"] = latest_count
                rows.append(snapshot)

    with transaction.atomic():
        for row in rows:
            sector, day = row.pop("sector"), row.pop("date")
            SectorRotationSnapshot.objects.update_or_create(sector=sector, date=day, defaults=row)
        SectorRotationSnapshot.objects.exclude(date__in=sessions).delete()
    return {"sessions": len(sessions), "snapshots": len(rows)}
