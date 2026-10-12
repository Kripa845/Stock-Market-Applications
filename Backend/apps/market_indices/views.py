"""
/api/market-indices/ -- NEPSE indices, sub-indices, Top 10 and market % analysis.

Every response carries ``scope``: "whole_market" (crawled NEPSE-wide data) or
"tracked_companies" (the 20 tracked companies only).  The API returns raw
numbers; the frontend formats them (Cr / L, percent).
"""

from datetime import date

from django.core.cache import cache
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.market_data.services.trading_days import is_market_open
from apps.market_indices.services import aggregates
from apps.users.permissions import HasAppPermission

CACHE_SECONDS = 60

UNITS = {
    "index": "points",
    "ch": "points",
    "ch_pct": "percent",
    "turnover": "NPR",
    "volume": "shares",
    "transactions": "trades",
}


def _cached(key, builder):
    data = cache.get(key)
    if data is None:
        data = builder()
        cache.set(key, data, CACHE_SECONDS)
    return data


class _MarketIndicesView(APIView):
    permission_classes = [HasAppPermission]
    permission_key = "view_market_data"


def _index_response(request, name, builder):
    """?date=YYYY-MM-DD -> the session on or before it (default: latest)."""
    raw = request.query_params.get("date", "").strip()
    try:
        day = date.fromisoformat(raw) if raw else None
    except ValueError:
        return Response({"detail": "date must use YYYY-MM-DD format."}, status=400)
    data = _cached(f"mi:{name}:{day or 'latest'}", lambda: builder(day))
    # While today's session is open, turnover / volume / transactions are still growing.
    open_now = is_market_open() and str(data.get("as_of")) == str(timezone.localdate())
    return Response({**data, "market_open": open_now, "requested_date": day, "units": UNITS})


class IndicesAPIView(_MarketIndicesView):
    """Main indices: NEPSE, Sensitive, Float, Sensitive Float."""

    def get(self, request):
        return _index_response(request, "indices", aggregates.main_index_table)


class SubIndicesAPIView(_MarketIndicesView):
    """13 sub-indices: OHLC + CH + sector turnover / volume / transactions."""

    def get(self, request):
        return _index_response(request, "sub-indices", aggregates.sub_index_table)


class MarketAnalysisAPIView(_MarketIndicesView):
    """Donut data (shares) and bar data (change %) per sector."""

    def get(self, request):
        data = _cached("mi:analysis", aggregates.market_sector_table)
        return Response({**data, "units": UNITS})


class MarketTopAPIView(_MarketIndicesView):
    """Top 10 whole-market stocks. ?by=turnover|volume|transactions"""

    def get(self, request):
        metric = request.query_params.get("by", "turnover")
        if metric not in aggregates.TOP_METRICS:
            return Response(
                {"detail": "by must be one of: turnover, volume, transactions"}, status=400
            )
        data = _cached(f"mi:top:{metric}", lambda: aggregates.market_top(metric))
        return Response({**data, "units": UNITS})


class TrackedSectorsAPIView(_MarketIndicesView):
    """Panel B: the same sector table, tracked companies only."""

    def get(self, request):
        data = _cached("mi:tracked-sectors", aggregates.tracked_sector_table)
        return Response({**data, "units": UNITS})
