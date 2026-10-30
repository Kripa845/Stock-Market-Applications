"""Runs registry indicators over one price history; shared by the company and index indicator endpoints.

``data`` maps input names to per-bar lists (oldest first, aligned with ``data["date"]``) plus any
non-bar inputs (``universe``, ``trades``). Indicators run over the full history and are then cut to
``start``, so a range never restarts a warm-up. Range-scoped indicators (anchored VWAP, volume
profile) run on the selected bars only.
"""

import json
from datetime import date

from apps.market_data.models import DailyPrice
from apps.market_intelligence.indicators import REGISTRY, compute

MAX_INDICATORS_PER_REQUEST = 20
PER_BAR = ("date", "open", "high", "low", "close", "volume", "benchmark")


class SpecError(ValueError):
    """A bad request; the message is shown to the user as the 400 detail."""


def parse_query(query_params):
    """``specs`` / ``start_date`` / ``end_date`` from the query string -> (specs, start, end)."""
    try:
        specs = json.loads(query_params.get("specs", "[]"))
        if not isinstance(specs, list) or not all(isinstance(s, dict) and "id" in s for s in specs):
            raise ValueError
    except ValueError:
        raise SpecError('specs must be a JSON list like [{"id": "rsi", "params": {"period": 14}}].') from None
    if len(specs) > MAX_INDICATORS_PER_REQUEST:
        raise SpecError(f"At most {MAX_INDICATORS_PER_REQUEST} indicators per request.")
    unknown = [str(s["id"]) for s in specs if s["id"] not in REGISTRY]
    if unknown:
        raise SpecError(f"Unknown indicator(s): {', '.join(unknown)}.")

    bounds = {}
    for name in ("start_date", "end_date"):
        raw = query_params.get(name)
        try:
            bounds[name] = date.fromisoformat(raw) if raw else None
        except ValueError:
            raise SpecError(f"{name} must use YYYY-MM-DD.") from None
    return specs, bounds["start_date"], bounds["end_date"]


def scopes(specs):
    return {REGISTRY[s["id"]].scope for s in specs}


def market_universe(sources, end=None):
    """Every active company's {date: (close, volume, high, low)}, for the market-wide indicators."""
    prices = DailyPrice.objects.filter(company__is_active=True, source__in=sources)
    if end:
        prices = prices.filter(date__lte=end)
    universe = {}
    for company_id, day, close, volume, high, low in prices.values_list(
        "company_id", "date", "close", "volume", "high", "low"
    ):
        universe.setdefault(company_id, {})[day] = (float(close), float(volume or 0), float(high), float(low))
    return list(universe.values())


def _compute(indicator, data, params):
    # Index volume is published only for recent sessions; a missing volume is not zero volume,
    # so volume indicators start at the first bar that has one.
    volume = data.get("volume")
    if "volume" in indicator.inputs and volume and volume[0] is None:
        skip = next((i for i, v in enumerate(volume) if v is not None), len(volume))
        if skip == len(volume):
            raise ValueError("No volume data is available for this series.")
        trimmed = {key: (values[skip:] if key in PER_BAR else values) for key, values in data.items()}
        result = compute(indicator.id, trimmed, params)
        result["outputs"] = {key: [None] * skip + values for key, values in result["outputs"].items()}
        return result
    return compute(indicator.id, data, params)


def run(specs, data, start=None, unavailable=None):
    """-> (dates from ``start``, one result per spec). ``unavailable`` maps a scope to the error for it."""
    dates = data["date"]
    first = next((i for i, d in enumerate(dates) if start is None or d >= start), len(dates))
    ranged = {key: (values[first:] if key in PER_BAR else values) for key, values in data.items()}

    results = []
    for spec in specs:
        indicator = REGISTRY[spec["id"]]
        if unavailable and indicator.scope in unavailable:
            results.append({"id": indicator.id, "error": unavailable[indicator.scope]})
            continue
        try:
            if indicator.scope == "range":
                result = _compute(indicator, ranged, spec.get("params"))
            else:
                result = _compute(indicator, data, spec.get("params"))
                result["outputs"] = {k: v[first:] for k, v in result["outputs"].items()}
        except ValueError as exc:
            results.append({"id": indicator.id, "error": str(exc)})
            continue
        result["outputs"] = {
            key: [round(v, 6) if isinstance(v, float) else v for v in values]
            for key, values in result["outputs"].items()
        }
        results.append({"id": indicator.id, **result})
    return dates[first:], results
