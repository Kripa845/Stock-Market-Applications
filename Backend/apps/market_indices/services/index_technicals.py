"""
Intraday bars and support / resistance for an index, for the Technical Charts page.

Intraday: the index values NEPSE's live feed published while the market was open, stored every
5 minutes by snapshot_live_index (IndexIntradayPoint).  Each point becomes a one-point bar
(open = high = low = close = value, no volume); the chart groups them into 5 min / 15 min / 1 h
candles itself, exactly as it does with company minute bars.  Only indices the live feed covers
have points; others return no bars.

Support / resistance: the same algorithm as companies (market_intelligence.services.support_resistance
.compute_levels) on the stored daily IndexDaily bars.  NEPSE's own percentage change is passed as
source_change_pct, so a re-based index is back-adjusted rather than read as a price gap.  Indices
have no corporate actions to flag.  Computed on request (a few hundred bars) and cached by the view.

Indicators: the company indicator library (market_intelligence.indicators) on the same IndexDaily
bars.  Index volume is published only for recent sessions, so volume indicators start there.
Benchmark and floorsheet indicators need a stock and are reported as unavailable.
"""

from dataclasses import asdict
from datetime import timedelta

from django.utils import timezone

from apps.market_indices.models import IndexDaily, IndexIntradayPoint
from apps.market_intelligence.services import indicator_series as series
from apps.market_intelligence.services.support_resistance import Bar, Params, compute_levels

# Same rule as the company endpoint: only crawled company prices feed the market-wide indicators.
UNIVERSE_SOURCES = ("crawled",)
UNAVAILABLE = {
    "benchmark": "Needs a stock to compare with the benchmark; not available for an index.",
    "floorsheet": "Built from a stock's floorsheet trades; not available for an index.",
}

MAX_INTRADAY_DAYS = 60


def intraday_bars(index, days):
    """One-point bars for the last ``days`` calendar days, oldest first."""
    days = min(max(int(days), 1), MAX_INTRADAY_DAYS)
    since = timezone.now() - timedelta(days=days)
    points = (
        IndexIntradayPoint.objects
        .filter(index=index, recorded_at__gte=since)
        .order_by("recorded_at")
        .values_list("recorded_at", "value")
    )
    return [
        {"time": timezone.localtime(at).isoformat(), "open": value, "high": value, "low": value,
         "close": value, "volume": 0}
        for at, value in points
    ]


def indicator_series(index, specs, start=None, end=None):
    """Registry indicators for ``index`` -> (dates from ``start``, one result per spec)."""
    rows = IndexDaily.objects.filter(index=index).order_by("date")
    if end:
        rows = rows.filter(date__lte=end)
    rows = list(rows.values_list("date", "open", "high", "low", "close", "volume"))
    optional = lambda v: None if v is None else float(v)  # noqa: E731
    data = {
        "date": [r[0] for r in rows],
        "open": [optional(r[1]) for r in rows], "high": [optional(r[2]) for r in rows],
        "low": [optional(r[3]) for r in rows], "close": [float(r[4]) for r in rows],
        "volume": [r[5] for r in rows],
    }
    if "market" in series.scopes(specs):
        data["universe"] = series.market_universe(UNIVERSE_SOURCES, end)
    return series.run(specs, data, start, unavailable=UNAVAILABLE)


def support_resistance(index, params: Params = Params()):
    """Levels for ``index`` in the same shape as the company support-resistance endpoint."""
    rows = IndexDaily.objects.filter(index=index).order_by("date")
    bars = [
        Bar(
            date=row.date,
            open=float(row.open if row.open is not None else row.close),
            high=float(row.high if row.high is not None else row.close),
            low=float(row.low if row.low is not None else row.close),
            close=float(row.close),
            volume=float(row.volume or 0),
            source_change_pct=float(row.source_change_pct) if row.source_change_pct is not None else None,
        )
        for row in rows
    ]
    result = compute_levels(bars, set(), params)
    close = result.latest_close
    return {
        "index_code": index.code,
        "symbol": index.name,
        "as_of": result.as_of,
        "status": result.status,
        "latest_close": round(close, 2) if close is not None else None,
        "sessions_used": result.sessions_used,
        "window_start": result.window_start,
        "adjustment_cut": result.adjustment_cut,
        "adjustments": result.adjustments,
        "params": asdict(params),
        "levels": [
            {
                "price": round(level.price, 2), "kind": level.kind, "touches": level.touches,
                "strength": round(level.strength, 4), "at_price": level.at_price,
                "distance_pct": round((level.price / close - 1) * 100, 2) if close else None,
                "first_touch": level.first_touch, "last_touch": level.last_touch,
            }
            for level in result.levels
        ],
        "disclaimer": "Levels are computed from historical index values and are not investment advice.",
        "computed_at": timezone.now(),
    }
