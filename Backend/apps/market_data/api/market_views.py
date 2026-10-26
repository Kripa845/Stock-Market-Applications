"""
/api/market/ -- the tracked-companies dashboard.

Every number covers ONLY the tracked companies (see services.market_stats),
so each response carries ``"scope": "tracked_companies"``.  Values are raw
numbers (NPR, shares, percent); crore / lakh formatting is the frontend's job.

GET responses are cached for 60 seconds.  The cache key includes the
caller's accessible company ids, so users with different company access
never share a cached response.
"""

import hashlib
from datetime import datetime

from django.core.cache import cache
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.companies.models import Company
from apps.market_indices.services import aggregates
from apps.market_intelligence.services import technical_summary
from apps.news.api.views import NewsArticleListAPIView
from apps.users.company_access import get_accessible_company_ids, require_company_access
from apps.users.permissions import HasAppPermission

from apps.market_data.services import heatmap, live_prices, market_overview, market_stats, movers, top_movers

CACHE_SECONDS = 60
SCOPE = "tracked_companies"


def _parse_date(request):
    raw = request.query_params.get("date", "").strip()
    if not raw:
        return None, None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date(), None
    except ValueError:
        return None, Response({"detail": "date must use YYYY-MM-DD format."}, status=status.HTTP_400_BAD_REQUEST)


def _cache_key(request, accessible_ids):
    scope = "all" if accessible_ids is None else ",".join(str(i) for i in sorted(accessible_ids))
    params = "&".join(f"{k}={v}" for k, v in sorted(request.query_params.items()))
    raw = f"{request.path}?{params}|{scope}"
    return "market-api:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cached(request, build):
    """Return ``build(accessible_ids)`` wrapped with scope/units, cached for 60s per access scope."""
    accessible_ids = get_accessible_company_ids(request.user)
    key = _cache_key(request, accessible_ids)
    payload = cache.get(key)
    if payload is None:
        payload = {"scope": SCOPE, "units": market_stats.UNITS, **build(accessible_ids)}
        cache.set(key, payload, CACHE_SECONDS)
    return Response(payload)


def _tracked_company(request, symbol):
    company = get_object_or_404(market_stats.tracked_companies(), symbol__iexact=symbol)
    require_company_access(request.user, company)
    return company


def _limit(request, default):
    try:
        return max(1, min(int(request.query_params.get("limit", default)), 50))
    except ValueError:
        return default


class TrackedSummaryAPIView(APIView):
    """GET /api/market/summary/?date=YYYY-MM-DD"""
    permission_classes = [HasAppPermission]
    permission_key = "view_market_data"

    def get(self, request):
        trade_date, error = _parse_date(request)
        if error:
            return error
        return _cached(request, lambda ids: {
            "summary": movers.tracked_summary(trade_date, ids),
            "circuit_threshold_pct": movers.CIRCUIT_THRESHOLD_PCT,
            "provenance": movers.provenance(),
            "note": market_stats.CORPORATE_ACTION_NOTE,
        })


class TrackedMoversAPIView(APIView):
    """
    GET /api/market/movers/?period=1D|5S|20S&date=YYYY-MM-DD&limit=5

    Tracked gainers and losers (definition: services.movers).  1W / 1M are
    accepted as aliases of 5S / 20S (5 and 20 trading sessions).
    """
    permission_classes = [HasAppPermission]
    permission_key = "view_market_data"

    def get(self, request):
        trade_date, error = _parse_date(request)
        if error:
            return error
        period = movers.normalize_period(request.query_params.get("period"))
        if period is None:
            return Response(
                {"detail": f"period must be one of {', '.join(movers.PERIODS)} (aliases 1W, 1M)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        limit = _limit(request, 5)
        return _cached(request, lambda ids: {
            **movers.tracked_movers(period, trade_date, ids, limit),
            "note": market_stats.CORPORATE_ACTION_NOTE,
        })


class LiveTrackedMoversAPIView(APIView):
    """
    GET /api/market/movers/live/?limit=10

    Intraday gainers and losers from NEPSE's live feed (services.live_prices),
    refreshed every 2 minutes in market hours.  Unofficial until the close;
    /api/market/movers/ stays the official end-of-day view.
    """
    permission_classes = [HasAppPermission]
    permission_key = "view_market_data"

    def get(self, request):
        limit = _limit(request, 10)
        return _cached(request, lambda ids: live_prices.live_movers(ids, limit))


class HeatmapAPIView(APIView):
    """
    GET /api/market/heatmap/

    Tracked companies by sector with market cap and the day's change, from the live
    prices (services.heatmap).  The last session's snapshot until the next one trades.
    """
    permission_classes = [HasAppPermission]
    permission_key = "view_market_data"

    def get(self, request):
        return _cached(request, heatmap.heatmap)


class TopMoversAPIView(APIView):
    """
    GET /api/market/top-gainers/?type=gainers|losers&period=today|2d|3d|5d|7d|1w|1m|3m|4m|6m|1y
        &sector=&adjusted=true|false&page=1&page_size=20

    One page of the tracked companies' top gainers or losers (services.top_movers).
    Today is live from NEPSE's feed until the day's prices are crawled.
    """
    permission_classes = [HasAppPermission]
    permission_key = "view_market_data"
    PAGE_SIZES = (10, 20, 50, 100)

    def get(self, request):
        q = request.query_params
        side = q.get("type", "gainers").strip().lower()
        period = q.get("period", "today").strip().lower()
        adjusted = q.get("adjusted", "true").strip().lower()
        errors = {}
        if side not in top_movers.SIDES:
            errors["type"] = f"must be one of {', '.join(top_movers.SIDES)}."
        if period not in top_movers.PERIODS:
            errors["period"] = f"must be one of {', '.join(top_movers.PERIODS)}."
        if adjusted not in ("true", "false"):
            errors["adjusted"] = "must be true or false."
        page, page_size, page_errors = _page_params(q, self.PAGE_SIZES)
        errors.update(page_errors)
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        sector = q.get("sector", "").strip() or None
        return _cached(request, lambda ids: top_movers.top_movers(
            side, period, sector, adjusted == "true", page, page_size, ids,
        ))


def _page_params(q, page_sizes):
    """(page, page_size, errors) from the query string."""
    errors = {}
    try:
        page, page_size = int(q.get("page", 1)), int(q.get("page_size", 20))
    except ValueError:
        page, page_size = 0, 0
    if page < 1:
        errors["page"] = "must be a positive integer."
    if page_size not in page_sizes:
        errors["page_size"] = f"must be one of {', '.join(map(str, page_sizes))}."
    return page, page_size, errors


class TopActivityAPIView(APIView):
    """
    GET /api/market/top-activity/?metric=turnover|volume|transactions
        &period=today|2d|3d|5d|7d|1w|1m|3m|4m|6m|1y&sector=&page=1&page_size=20

    Tracked companies ranked by the metric summed over the period (services.top_movers).
    Official end-of-day data only.
    """
    permission_classes = [HasAppPermission]
    permission_key = "view_market_data"

    def get(self, request):
        q = request.query_params
        metric = q.get("metric", "turnover").strip().lower()
        period = q.get("period", "today").strip().lower()
        page, page_size, errors = _page_params(q, TopMoversAPIView.PAGE_SIZES)
        if metric not in top_movers.METRICS:
            errors["metric"] = f"must be one of {', '.join(top_movers.METRICS)}."
        if period not in top_movers.PERIODS:
            errors["period"] = f"must be one of {', '.join(top_movers.PERIODS)}."
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        sector = q.get("sector", "").strip() or None
        return _cached(request, lambda ids: top_movers.top_activity(metric, period, sector, page, page_size, ids))


class TrackedTopAPIView(APIView):
    """GET /api/market/top-turnover/ | top-volume/ | top-transactions/ ?date=&limit="""
    permission_classes = [HasAppPermission]
    permission_key = "view_market_data"
    metric = None

    def get(self, request):
        trade_date, error = _parse_date(request)
        if error:
            return error
        limit = _limit(request, 10)
        return _cached(request, lambda ids: movers.top_by(self.metric, trade_date, ids, limit))


PUBLIC_ROWS = 5
PUBLIC_ROW_FIELDS = ("symbol", "name", "close", "change", "change_pct", "turnover", "volume", "transactions")


def _public_rows(rows):
    return [{field: row.get(field) for field in PUBLIC_ROW_FIELDS} for row in rows]


def _public_snapshot():
    main = aggregates.main_index_table()
    sub = aggregates.sub_index_table()
    day_movers = movers.tracked_movers("1D", None, None, PUBLIC_ROWS, lean=True)
    top = {metric: movers.top_by(metric, None, None, PUBLIC_ROWS) for metric in ("turnover", "volume", "transactions")}
    overview = market_overview.market_overview()
    return {
        "scope": SCOPE,
        "nepse": overview["instrument"],
        "status": overview["status"],
        "stats": overview["stats"],
        "stats_label": overview["stats_label"],
        "indices": {"as_of": main.get("as_of"), "rows": main.get("rows", [])},
        "sub_indices": {"as_of": sub.get("as_of"), "rows": sub.get("rows", [])},
        "as_of": day_movers["as_of"],
        "gainers": _public_rows(day_movers["gainers"]),
        "losers": _public_rows(day_movers["losers"]),
        "top_turnover": _public_rows(top["turnover"]["rows"]),
        "top_volume": _public_rows(top["volume"]["rows"]),
        # A NULL trade count means "not filled yet", not zero: keep those rows out of the ranking.
        "top_transactions": _public_rows([r for r in top["transactions"]["rows"] if r.get("transactions") is not None]),
    }


class PublicMarketSnapshotAPIView(APIView):
    """
    GET /api/market/public/snapshot/

    Unauthenticated, for the public landing page: NEPSE indices / sub-indices
    (whole market) and the top 5 tracked gainers, losers, turnover, volume and
    transactions for the latest crawled session.  Rows carry only symbol, name
    and the ranked numbers -- no provenance, sparklines or company ids.
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "public"

    def get(self, request):
        payload = cache.get("market-api:public-snapshot")
        if payload is None:
            payload = _public_snapshot()
            cache.set("market-api:public-snapshot", payload, CACHE_SECONDS)
        return Response(payload)


class PublicMarketChartAPIView(APIView):
    """
    GET /api/market/public/chart/?range=1D|1W|1M|3M|6M|1Y|5Y|ALL

    Unauthenticated, for the public landing page: the NEPSE index chart only
    (same series as /api/market/overview/chart/ without a symbol).
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "public"

    def get(self, request):
        range_id = request.query_params.get("range", "1D").strip().upper()
        if range_id not in market_overview.RANGES:
            return Response(
                {"detail": f"range must be one of {', '.join(market_overview.RANGES)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        key = f"market-api:public-chart:{range_id}"
        payload = cache.get(key)
        if payload is None:
            payload = market_overview.chart_series(range_id)
            cache.set(key, payload, CACHE_SECONDS)
        return Response(payload)


class CompanyBrokerActivityAPIView(APIView):
    """GET /api/market/brokers/<symbol>/?date=YYYY-MM-DD -- 5- and 20-session broker windows."""
    permission_classes = [HasAppPermission]
    permission_key = "view_analysis"

    def get(self, request, symbol):
        company = _tracked_company(request, symbol)
        anchor, error = _parse_date(request)
        if error:
            return error
        return _cached(request, lambda ids: {
            "symbol": company.symbol,
            "windows": market_stats.broker_activity(company.id, anchor_date=anchor),
            "share_denominator": (
                "share_pct = (buy amount + sell amount) * 100 / (2 * company turnover), where company "
                "turnover = sum(quantity * rate) of the same floorsheet trades in the window. Shares sum to 100%."
            ),
        })


class CompanySignalsAPIView(APIView):
    """GET /api/market/signals/<symbol>/?date=YYYY-MM-DD"""
    permission_classes = [HasAppPermission]
    permission_key = "view_analysis"

    def get(self, request, symbol):
        company = _tracked_company(request, symbol)
        anchor, error = _parse_date(request)
        if error:
            return error
        return _cached(request, lambda ids: {"signals": market_stats.signals(company.id, anchor)})


class BasketIndexAPIView(APIView):
    """GET /api/market/basket-index/?days=N -- the "Tracked Basket" (not the NEPSE index)."""
    permission_classes = [HasAppPermission]
    permission_key = "view_market_data"

    def get(self, request):
        try:
            days = int(request.query_params["days"]) if request.query_params.get("days") else None
        except ValueError:
            return Response({"detail": "days must be an integer."}, status=status.HTTP_400_BAD_REQUEST)
        return _cached(request, lambda ids: market_stats.basket_index(days))


class CompanyNewsAPIView(NewsArticleListAPIView):
    """
    GET /api/market/news/<symbol>/ -- alias of /api/news/ (same serializer,
    permission ``view_news``, pagination and filters) restricted to one company.
    """

    def get_queryset(self):
        company = get_object_or_404(Company, symbol__iexact=self.kwargs["symbol"], is_active=True)
        require_company_access(self.request.user, company)
        return super().get_queryset().filter(company_tags__company=company).distinct()


def _overview_company(request):
    """None for the NEPSE index (default), else the tracked company named by ?symbol= (access checked)."""
    symbol = request.query_params.get("symbol", market_overview.INDEX_SYMBOL).strip()
    if not symbol or symbol.upper() == market_overview.INDEX_SYMBOL:
        return None
    return _tracked_company(request, symbol)


class MarketOverviewAPIView(APIView):
    """GET /api/market/overview/?symbol=NEPSE|<tracked symbol> -- card header + tracked-company stats."""
    permission_classes = [HasAppPermission]
    permission_key = "view_market_data"

    def get(self, request):
        company = _overview_company(request)
        return _cached(request, lambda ids: market_overview.market_overview(company=company, company_ids=ids))


class MarketOverviewChartAPIView(APIView):
    """GET /api/market/overview/chart/?symbol=&range=1D|1W|1M|3M|6M|1Y|5Y|ALL"""
    permission_classes = [HasAppPermission]
    permission_key = "view_market_data"

    def get(self, request):
        range_id = request.query_params.get("range", "1D").strip().upper()
        if range_id not in market_overview.RANGES:
            return Response(
                {"detail": f"range must be one of {', '.join(market_overview.RANGES)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        company = _overview_company(request)
        return _cached(request, lambda ids: market_overview.chart_series(range_id, company))


class MarketOverviewTechnicalAPIView(APIView):
    """GET /api/market/overview/technical/?symbol= -- indicators, pivots and summary signal."""
    permission_classes = [HasAppPermission]
    permission_key = "view_market_data"

    def get(self, request):
        company = _overview_company(request)
        return _cached(request, lambda ids: technical_summary.instrument_technicals(company))
