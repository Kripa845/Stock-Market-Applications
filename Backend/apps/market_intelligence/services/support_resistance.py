"""Support / resistance levels from clustered swing highs and lows (daily bars).

Per company, newest computation only:

1. Daily crawled bars on valid sessions (the same calendar as the technical snapshots).
2. Price adjustments.  Stored prices are NOT adjusted for bonus / right shares, so a
   book closure leaves a step in the series.  A session is an adjustment when
   ShareSansar's change % (``source_change_pct``, measured against the exchange's
   adjusted previous close) differs from the raw close-to-close % by more than
   ``ADJUSTMENT_GAP_PP``.  The factor ``(1 + raw%) / (1 + source%)`` is applied to every
   earlier bar (back-adjustment), so pre-bonus swings land at today's price scale.
   Sessions flagged by ``_corporate_action_flags`` (>10% move or a previous-close
   mismatch) without a usable factor cut the history instead.
3. Pivots: Williams fractals with ``pivot_window`` bars on each side.  Pivots on
   circuit days (a close-to-close move of ``circuit_pct`` or more in the pivot's
   direction) and on zero-range bars are dropped: trading halted there, price was
   not rejected.
4. Clustering: pivots sorted by price; a pivot joins the current cluster while it is
   within ``tolerance_pct`` of the cluster's running mean.  A level needs
   ``min_touches`` pivots.
5. Strength: sum over touches of ``0.5 ** (age / half_life_sessions)`` times the
   pivot bar's relative volume (clamped to [0.5, volume_cap]).  The level price is
   the strength-weighted mean of its pivots.
6. Kind: below the latest close = support, above = resistance; within
   ``at_price_pct`` it is also marked ``at_price``.  The strongest ``max_per_side``
   per side are kept.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

from apps.analysis.models import DailyAnalysis
from apps.companies.selection import tracked_active_companies
from apps.market_data.models import DailyPrice
from apps.market_data.services.price_source import with_crawled_price
from apps.market_intelligence.indicators.price import fractals
from apps.market_intelligence.models import SupportResistanceLevel, SupportResistanceSet
from apps.market_intelligence.services.snapshots import (
    _configured_excluded_dates,
    _corporate_action_flags,
    _trading_calendar,
)

logger = logging.getLogger(__name__)

# Percentage points between ShareSansar's change % and the raw close-to-close %
# above which a session is treated as a price adjustment.  Rounding differences are
# a few hundredths; real bonus / right adjustments are whole points.
ADJUSTMENT_GAP_PP = 1.0
# Accepted range for a derived adjustment factor; anything outside is a data problem,
# so the history is cut there instead of being scaled by a nonsense factor.
FACTOR_BOUNDS = (0.3, 1.5)


@dataclass(frozen=True)
class Params:
    pivot_window: int = 5
    tolerance_pct: float = 1.5
    min_touches: int = 2
    half_life_sessions: int = 60
    lookback_sessions: int = 250
    min_sessions: int = 60
    max_per_side: int = 4
    circuit_pct: float = 9.5
    at_price_pct: float = 0.3
    volume_avg_sessions: int = 20
    volume_cap: float = 2.0


@dataclass
class Bar:
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    source_change_pct: float | None = None


@dataclass
class Pivot:
    index: int
    date: date
    price: float
    kind: str           # "high" / "low"
    weight: float


@dataclass
class Level:
    price: float
    kind: str           # "support" / "resistance"
    touches: int
    strength: float
    first_touch: date
    last_touch: date
    at_price: bool = False
    distance_pct: float = 0.0


@dataclass
class Result:
    status: str
    levels: list[Level] = field(default_factory=list)
    as_of: date | None = None
    latest_close: float | None = None
    sessions_used: int = 0
    window_start: date | None = None
    adjustment_cut: date | None = None
    adjustments: list[dict] = field(default_factory=list)


# ─── Pure steps ──────────────────────────────────────────────────────────────

def adjust_history(bars: list[Bar], flagged_dates: set[date]):
    """Back-adjust bars for price adjustments; cut where no factor can be derived.

    Returns ``(bars, adjustments, cut_date)``; ``adjustments`` lists
    ``{"date", "factor"}`` for each back-adjusted session, oldest first.
    """
    bars = [Bar(**asdict(b)) for b in bars]           # never mutate the caller's bars
    adjustments, cut_index = [], 0
    for i in range(len(bars) - 1, 0, -1):
        current, prior = bars[i], bars[i - 1]
        if prior.close <= 0:
            continue
        raw_pct = (current.close / prior.close - 1) * 100
        source = current.source_change_pct
        factor = None
        if source is not None and abs(source - raw_pct) > ADJUSTMENT_GAP_PP and source > -100:
            factor = (1 + raw_pct / 100) / (1 + source / 100)
            if not FACTOR_BOUNDS[0] <= factor <= FACTOR_BOUNDS[1]:
                factor = None
                cut_index = i
                break
        elif current.date in flagged_dates:
            cut_index = i
            break
        if factor is None:
            continue
        for earlier in bars[:i]:
            earlier.open *= factor
            earlier.high *= factor
            earlier.low *= factor
            earlier.close *= factor
            earlier.volume /= factor                  # same traded value, more shares after a bonus
        adjustments.append({"date": current.date.isoformat(), "factor": round(factor, 6)})
    adjustments.reverse()
    cut = bars[cut_index].date if cut_index else None
    return bars[cut_index:], adjustments, cut


def find_pivots(bars: list[Bar], params: Params) -> list[Pivot]:
    """Fractal swing highs / lows, minus circuit-day and zero-range bars, with recency/volume weights."""
    if len(bars) < 2 * params.pivot_window + 1:
        return []
    marks = fractals([b.high for b in bars], [b.low for b in bars], params.pivot_window)
    last = len(bars) - 1
    pivots = []
    for i, bar in enumerate(bars):
        for kind, value in (("high", marks["up"][i]), ("low", marks["down"][i])):
            if value is None or bar.high == bar.low:
                continue
            move = (bar.close / bars[i - 1].close - 1) * 100 if i and bars[i - 1].close > 0 else 0.0
            if (kind == "high" and move >= params.circuit_pct) or (kind == "low" and move <= -params.circuit_pct):
                continue
            window = [b.volume for b in bars[max(0, i - params.volume_avg_sessions):i] if b.volume > 0]
            average = sum(window) / len(window) if window else 0
            volume_factor = min(max(bar.volume / average, 0.5), params.volume_cap) if average and bar.volume > 0 else 1.0
            recency = 0.5 ** ((last - i) / params.half_life_sessions)
            pivots.append(Pivot(i, bar.date, float(value), kind, recency * volume_factor))
    return pivots


def cluster_levels(pivots: list[Pivot], latest_close: float, params: Params) -> list[Level]:
    clusters: list[list[Pivot]] = []
    for pivot in sorted(pivots, key=lambda p: p.price):
        if clusters:
            current = clusters[-1]
            mean = sum(p.price for p in current) / len(current)
            if abs(pivot.price - mean) / mean * 100 <= params.tolerance_pct:
                current.append(pivot)
                continue
        clusters.append([pivot])

    levels = []
    for members in clusters:
        if len(members) < params.min_touches:
            continue
        strength = sum(p.weight for p in members)
        price = sum(p.price * p.weight for p in members) / strength
        distance = (price / latest_close - 1) * 100
        levels.append(Level(
            price=price,
            kind="support" if price <= latest_close else "resistance",
            touches=len(members),
            strength=strength,
            first_touch=min(p.date for p in members),
            last_touch=max(p.date for p in members),
            at_price=abs(distance) <= params.at_price_pct,
            distance_pct=distance,
        ))

    kept = []
    for kind in ("support", "resistance"):
        side = sorted((lv for lv in levels if lv.kind == kind), key=lambda lv: lv.strength, reverse=True)
        kept.extend(side[:params.max_per_side])
    return sorted(kept, key=lambda lv: lv.price, reverse=True)


def compute_levels(bars: list[Bar], flagged_dates: set[date], params: Params = Params()) -> Result:
    """Levels for one company's daily bars (oldest first)."""
    adjusted, adjustments, cut = adjust_history(bars, flagged_dates)
    window = adjusted[-params.lookback_sessions:]
    result = Result(
        status=SupportResistanceSet.STATUS_INSUFFICIENT,
        as_of=window[-1].date if window else None,
        latest_close=window[-1].close if window else None,
        sessions_used=len(window),
        window_start=window[0].date if window else None,
        adjustment_cut=cut,
        adjustments=[a for a in adjustments if window and a["date"] >= window[0].date.isoformat()],
    )
    if len(window) < params.min_sessions:
        return result
    result.levels = cluster_levels(find_pivots(window, params), window[-1].close, params)
    result.status = SupportResistanceSet.STATUS_OK if result.levels else SupportResistanceSet.STATUS_NO_LEVELS
    return result


# ─── Database ────────────────────────────────────────────────────────────────

def _dec(value, places="0.0001"):
    return Decimal(str(value)).quantize(Decimal(places), rounding=ROUND_HALF_UP)


def compute_support_resistance(company_ids=None, params: Params = Params()):
    """Compute and store levels for the tracked active companies (or ``company_ids``)."""
    companies = tracked_active_companies()
    if company_ids is not None:
        companies = companies.filter(pk__in=company_ids)
    companies = list(companies)
    if not companies:
        return {"companies": 0}

    # The session calendar and corporate-action flags are market-wide, as in the technical snapshots.
    prices = list(DailyPrice.objects.filter(source="crawled").order_by("date", "company_id", "pk"))
    sessions, _ = _trading_calendar(prices, _configured_excluded_dates())
    session_set = set(sessions)
    analyses = {
        (row.company_id, row.date): row
        for row in with_crawled_price(DailyAnalysis.objects.filter(date__in=sessions)).only("company_id", "date", "previous_close")
    }
    flags = _corporate_action_flags(prices, sessions, analyses)

    by_company: dict[int, list[Bar]] = {}
    for row in prices:
        if row.date not in session_set:
            continue
        by_company.setdefault(row.company_id, []).append(Bar(
            date=row.date, open=float(row.open), high=float(row.high), low=float(row.low),
            close=float(row.close), volume=float(row.volume or 0),
            source_change_pct=float(row.source_change_pct) if row.source_change_pct is not None else None,
        ))

    summary = {"companies": len(companies), "ok": 0, "insufficient_history": 0, "no_levels": 0, "failed": 0}
    for company in companies:
        try:
            bars = by_company.get(company.pk, [])
            flagged = {day for company_id, day in flags if company_id == company.pk}
            result = compute_levels(bars, flagged, params)
            _store(company, result, params)
            summary[result.status] += 1
        except Exception:
            # One bad company must not stop the others.
            logger.exception("support/resistance failed for %s", company.symbol)
            summary["failed"] += 1
    return summary


def _store(company, result: Result, params: Params):
    if result.as_of is None:
        SupportResistanceSet.objects.filter(company=company).delete()
        return
    with transaction.atomic():
        sr_set, _ = SupportResistanceSet.objects.update_or_create(
            company=company,
            defaults={
                "as_of": result.as_of,
                "status": result.status,
                "latest_close": _dec(result.latest_close, "0.01") if result.latest_close is not None else None,
                "sessions_used": result.sessions_used,
                "window_start": result.window_start,
                "adjustment_cut": result.adjustment_cut,
                "adjustments": result.adjustments,
                "params": asdict(params),
            },
        )
        sr_set.levels.all().delete()
        SupportResistanceLevel.objects.bulk_create([
            SupportResistanceLevel(
                set=sr_set, price=_dec(level.price), kind=level.kind, touches=level.touches,
                strength=_dec(level.strength), first_touch=level.first_touch, last_touch=level.last_touch,
                at_price=level.at_price,
            )
            for level in result.levels
        ])
