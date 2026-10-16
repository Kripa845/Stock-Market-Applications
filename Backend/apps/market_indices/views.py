"""
/api/market-indices/ -- NEPSE indices, sub-indices, Top 10 and market % analysis.

Every response carries ``scope``: "whole_market" (crawled NEPSE-wide data) or
"tracked_companies" (the 20 tracked companies only).  The API returns raw
numbers; the frontend formats them (Cr / L, percent).
"""

from datetime import date, timedelta

from django.core.cache import cache
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.market_data.services.trading_days import is_market_open
from apps.market_indices.models import MarketIndex
from apps.market_indices.services import aggregates, index_technicals, index_verification
from apps.market_indices.services.nepse_indices import IndexFeedError
from apps.users.permissions import HasAppPermission, HasViewMethodPermissions

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


class IndexHistoryAPIView(_MarketIndicesView):
    """
    Daily OHLC of one index for the candlestick chart, oldest first.

    ?code=NEPSE (default) | BANKING | HYDROPOWER ...  (MarketIndex.code, any case)
    ?range=7d|30d|90d|180d|1y|all (default all; same windows as the company price endpoint)
    ?start_date= / ?end_date=YYYY-MM-DD narrow the rows; start_date overrides range.
    """

    RANGE_DAYS = {"7d": 7, "30d": 30, "31d": 31, "90d": 90, "180d": 180, "1y": 365, "365d": 365}

    def get(self, request):
        code = request.query_params.get("code", "NEPSE").strip().upper()
        index = MarketIndex.objects.filter(code=code).first()
        if index is None:
            return Response({"detail": f"Unknown index code: {code}."}, status=404)

        try:
            start, end = (
                date.fromisoformat(raw) if raw else None
                for raw in (request.query_params.get(k, "").strip() for k in ("start_date", "end_date"))
            )
        except ValueError:
            return Response({"detail": "start_date and end_date must use YYYY-MM-DD format."}, status=400)

        range_param = request.query_params.get("range", "all").lower()
        if start is None and range_param != "all":
            # Unknown range -> 31-day window, as on the company endpoint.
            start = timezone.localdate() - timedelta(days=self.RANGE_DAYS.get(range_param, 31))

        data = aggregates.index_candles(index, start, end)
        return Response({
            "index_id": index.id,
            "symbol": index.code,
            "name": index.name,
            "kind": index.kind,
            "range": range_param,
            "count": len(data["prices"]),
            **data,
            "units": UNITS,
        })


class IndexVerificationAPIView(APIView):
    """
    GET  /api/market-indices/verify/?date=YYYY-MM-DD   per-index scraped / missing / mismatch vs NEPSE's feed
    POST /api/market-indices/verify/?date=YYYY-MM-DD   re-scrape that session from NEPSE, then verify again

    GET is cached for VERIFY_CACHE_SECONDS: each check calls NEPSE.  POST needs run_crawler.
    """
    permission_classes = [HasViewMethodPermissions]
    VERIFY_CACHE_SECONDS = 300

    def get_required_permissions(self, request):
        return "run_crawler" if request.method == "POST" else "view_market_data"

    def _day(self, request):
        raw = request.query_params.get("date", "").strip()
        return date.fromisoformat(raw) if raw else None

    def get(self, request):
        try:
            day = self._day(request)
        except ValueError:
            return Response({"detail": "date must use YYYY-MM-DD format."}, status=400)
        key = f"mi:verify:{day or 'latest'}"
        data = cache.get(key)
        if data is None:
            data = index_verification.verify_session(day)
            # A failed feed check is retried on the next request instead of being cached.
            if data["feed_ok"]:
                cache.set(key, data, self.VERIFY_CACHE_SECONDS)
        return Response(data)

    def post(self, request):
        try:
            day = self._day(request)
        except ValueError:
            return Response({"detail": "date must use YYYY-MM-DD format."}, status=400)
        try:
            result, data = index_verification.resync_session(day)
        except IndexFeedError as exc:
            return Response({"detail": f"{exc}. Nothing was saved."}, status=502)
        cache.delete_many([
            f"mi:verify:{day or 'latest'}", "mi:verify:latest",
            f"mi:indices:{day or 'latest'}", f"mi:sub-indices:{day or 'latest'}",
            "mi:indices:latest", "mi:sub-indices:latest",
        ])
        return Response({**data, "sync": result})


def _index_or_404(request):
    code = request.query_params.get("code", "NEPSE").strip().upper()
    index = MarketIndex.objects.filter(code=code).first()
    if index is None:
        return None, Response({"detail": f"Unknown index code: {code}."}, status=404)
    return index, None


class IndexIntradayAPIView(_MarketIndicesView):
    """GET /api/market-indices/intraday/?code=NEPSE&days=5 -- recorded 5-minute index values as one-point bars."""

    def get(self, request):
        index, error = _index_or_404(request)
        if error:
            return error
        try:
            days = int(request.query_params.get("days", 5))
        except (TypeError, ValueError):
            return Response({"detail": "days must be an integer from 1 to 60."}, status=400)
        return Response({"code": index.code, "bars": index_technicals.intraday_bars(index, days)})


class IndexSupportResistanceAPIView(_MarketIndicesView):
    """GET /api/market-indices/support-resistance/?code=NEPSE -- same levels as for companies, from IndexDaily."""
    permission_key = "view_analysis"

    def get(self, request):
        index, error = _index_or_404(request)
        if error:
            return error
        latest = index.daily.order_by("-date").values_list("date", flat=True).first()
        data = _cached(f"mi:sr:{index.code}:{latest}", lambda: index_technicals.support_resistance(index))
        return Response(data)
