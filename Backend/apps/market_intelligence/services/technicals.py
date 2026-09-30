"""Daily technical snapshots computed from observed, valid-market-session OHLCV."""

from decimal import Decimal, ROUND_HALF_UP
from math import ceil

from django.db import transaction

from apps.analysis.models import DailyAnalysis
from apps.companies.models import Company
from apps.market_data.models import DailyPrice
from apps.market_intelligence.models import CompanyTechnicalSnapshot
from apps.market_intelligence.services.snapshots import (
    DMA_COVERAGE_RATIO,
    _corporate_action_flags,
    _configured_excluded_dates,
    _trading_calendar,
)


def _average(rows):
    if not rows:
        return None
    return sum((Decimal(row.close) for row in rows), Decimal("0")) / Decimal(len(rows))


def _range(rows):
    if not rows:
        return None, None
    return min(Decimal(row.low) for row in rows), max(Decimal(row.high) for row in rows)


def _round_level(value):
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP) if value is not None else None


def _pattern_matches(rows):
    """Small, transparent daily candle rules; these are descriptive heuristics.

    Doji: body <= 10% of range. Hammer: lower shadow >= 2x body and upper
    shadow <= 10% of range. Engulfing: current real body covers the prior body
    and direction reverses. Morning/evening star: three consecutive candles,
    first/third directional and a small middle body; gaps are not required
    because daily NEPSE OHLC data does not guarantee meaningful gap structure.
    """
    if not rows or any(row is None for row in rows):
        return []

    def parts(row):
        op, hi, lo, cl = map(Decimal, (row.open, row.high, row.low, row.close))
        body = abs(cl - op)
        full = max(hi - lo, Decimal("0"))
        upper = hi - max(op, cl)
        lower = min(op, cl) - lo
        return op, hi, lo, cl, body, full, upper, lower

    current = parts(rows[-1])
    patterns = []
    if current[5] > 0 and current[4] <= current[5] * Decimal("0.10"):
        patterns.append("doji")
    if current[5] > 0 and current[7] >= current[4] * 2 and current[6] <= current[5] * Decimal("0.10"):
        patterns.append("hammer")

    if len(rows) >= 2:
        prior = parts(rows[-2])
        prev_up, cur_up = prior[3] > prior[0], current[3] > current[0]
        prior_low, prior_high = sorted((prior[0], prior[3]))
        current_low, current_high = sorted((current[0], current[3]))
        if prior[4] > 0 and current[4] > 0 and prior_low >= current_low and prior_high <= current_high:
            if not prev_up and cur_up:
                patterns.append("bullish_engulfing")
            elif prev_up and not cur_up:
                patterns.append("bearish_engulfing")

    if len(rows) >= 3:
        first, middle = parts(rows[-3]), parts(rows[-2])
        first_down, first_up = first[3] < first[0], first[3] > first[0]
        last_up, last_down = current[3] > current[0], current[3] < current[0]
        middle_small = middle[4] <= first[4] * Decimal("0.5")
        first_mid = (first[0] + first[3]) / 2
        if first_down and middle_small and last_up and current[3] >= first_mid:
            patterns.append("morning_star")
        if first_up and middle_small and last_down and current[3] <= first_mid:
            patterns.append("evening_star")
    return patterns


def compute_company_technical_snapshots():
    prices = list(DailyPrice.objects.filter(source="crawled").select_related("company").order_by("date", "company_id", "pk"))
    sessions, _ = _trading_calendar(prices, _configured_excluded_dates())
    if not sessions:
        CompanyTechnicalSnapshot.objects.all().delete()
        return {"sessions": 0, "snapshots": 0}

    company_rows = {}
    companies = {}
    for row in prices:
        company_rows.setdefault(row.company_id, {})[row.date] = row
        companies[row.company_id] = row.company
    analyses = {
        (row.company_id, row.date): row
        for row in DailyAnalysis.objects.filter(date__in=sessions).only("company_id", "date", "previous_close")
    }
    flags = _corporate_action_flags(prices, sessions, analyses)
    result_rows = []

    for index, day in enumerate(sessions):
        for company_id, by_day in company_rows.items():
            current = by_day.get(day)
            if current is None:
                continue
            action = (company_id, day) in flags
            previous_20 = sessions[max(0, index - 20):index]
            previous_60 = sessions[max(0, index - 60):index]
            previous_55 = sessions[max(0, index - 55):index]
            dates_50 = sessions[max(0, index - 49):index + 1]
            dates_200 = sessions[max(0, index - 199):index + 1]

            def valid_rows(dates):
                return [
                    by_day[session]
                    for session in dates
                    if session in by_day and (company_id, session) not in flags
                ]

            rows_20 = valid_rows(previous_20)
            rows_60 = valid_rows(previous_60)
            rows_55 = valid_rows(previous_55)
            rows_50_dma = valid_rows(dates_50)
            rows_200_dma = valid_rows(dates_200)
            req20 = ceil(len(previous_20) * float(DMA_COVERAGE_RATIO)) if previous_20 else 1
            req60 = ceil(len(previous_60) * float(DMA_COVERAGE_RATIO)) if previous_60 else 1
            req55 = ceil(len(previous_55) * float(DMA_COVERAGE_RATIO)) if previous_55 else 1
            req50 = ceil(len(dates_50) * float(DMA_COVERAGE_RATIO)) if index >= 49 else 51
            req200 = ceil(len(dates_200) * float(DMA_COVERAGE_RATIO)) if index >= 199 else 201

            can_20 = len(previous_20) == 20 and len(rows_20) >= req20
            can_60 = len(previous_60) == 60 and len(rows_60) >= req60
            can_55 = len(previous_55) == 55 and len(rows_55) >= req55
            can_50 = index >= 49 and len(rows_50_dma) >= req50
            can_200 = index >= 199 and len(rows_200_dma) >= req200

            support20, resistance20 = _range(rows_20) if can_20 and not action else (None, None)
            support60, resistance60 = _range(rows_60) if can_60 and not action else (None, None)
            close = Decimal(current.close)
            # Current close is compared with the preceding N valid market sessions.
            breakout20_up = breakout20_down = breakout55_up = breakout55_down = None
            if not action and can_20:
                _, prior_high = _range(rows_20)
                prior_low, _ = _range(rows_20)
                breakout20_up, breakout20_down = close > prior_high, close < prior_low
            if not action and can_55:
                prior_low, prior_high = _range(rows_55)
                breakout55_up, breakout55_down = close > prior_high, close < prior_low

            pattern_rows = [by_day.get(session) if (company_id, session) not in flags else None
                            for session in sessions[max(0, index - 2):index + 1]]
            patterns = [] if action else _pattern_matches(pattern_rows)
            dma50 = _average(rows_50_dma) if can_50 and not action else None
            dma200 = _average(rows_200_dma) if can_200 and not action else None
            sufficient = can_20 and can_55 and can_50 and can_200 and not action
            score = None
            signal = "possible_corporate_action" if action else "insufficient_history"
            if sufficient:
                score = 0
                score += 25 if close > dma50 else -25
                score += 25 if close > dma200 else -25
                score += 25 if breakout20_up or breakout55_up else 0
                score -= 25 if breakout20_down or breakout55_down else 0
                signal = "bullish" if score >= 25 else "bearish" if score <= -25 else "neutral"

            result_rows.append({
                "company": companies[company_id], "date": day,
                "support_20": _round_level(support20), "resistance_20": _round_level(resistance20),
                "support_60": _round_level(support60), "resistance_60": _round_level(resistance60),
                "breakout_20_up": breakout20_up, "breakout_20_down": breakout20_down,
                "breakout_55_up": breakout55_up, "breakout_55_down": breakout55_down,
                "patterns": patterns, "dma_50": _round_level(dma50), "dma_200": _round_level(dma200),
                "signal": signal, "signal_score": score,
                "history_sessions": sum(session in by_day for session in sessions[:index + 1]),
                "sufficient_history": sufficient, "possible_corporate_action": action,
            })

    with transaction.atomic():
        for row in result_rows:
            company = row.pop("company")
            day = row.pop("date")
            CompanyTechnicalSnapshot.objects.update_or_create(company=company, date=day, defaults=row)
        CompanyTechnicalSnapshot.objects.exclude(date__in=sessions).delete()
    return {"sessions": len(sessions), "snapshots": len(result_rows)}
