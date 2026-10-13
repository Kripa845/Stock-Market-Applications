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
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.companies.models import Company
from apps.market_intelligence.services import technical_summary
from apps.news.views import NewsArticleListAPIView
from apps.users.company_access import get_accessible_company_ids, require_company_access
from apps.users.models import WatchlistItem
from apps.users.permissions import HasAppPermission, HasViewMethodPermissions

from .services import live_prices, market_overview, market_stats, movers

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


class DividendListAPIView(APIView):
    """GET /api/market/dividends/"""
    permission_classes = [HasAppPermission]
    permission_key = "view_market_data"

    def get(self, request):
        return _cached(request, lambda ids: {"rows": market_stats.dividend_rows(ids)})


class WatchlistAPIView(APIView):
    """
    GET    /api/market/watchlist/            the user's saved companies with latest ltp / change
    POST   /api/market/watchlist/            {"symbol": "NABIL"}
    DELETE /api/market/watchlist/<symbol>/
    Not cached: it is per user and changes on every POST / DELETE.
    """
    permission_classes = [HasViewMethodPermissions]

    def get_required_permissions(self, request):
        return {
            "POST": "add_watchlist",
            "DELETE": "remove_watchlist",
        }.get(request.method, "view_watchlist")

    def _items(self, request):
        items = WatchlistItem.objects.filter(user=request.user)
        accessible_ids = get_accessible_company_ids(request.user)
        if accessible_ids is not None:
            items = items.filter(company_id__in=accessible_ids)
        return items

    def _rows(self, items):
        """Each saved company with its 1-session change from services.movers (any bucket)."""
        items = list(items.select_related("company").order_by("-created_at"))
        as_of, by_company = movers.company_rows([item.company_id for item in items])
        rows = []
        for item in items:
            row = by_company.get(item.company_id) or {
                "company_id": item.company_id, "symbol": item.company.symbol, "name": item.company.name,
                "bucket": "not_tracked",
            }
            rows.append({**row, "watchlist_id": item.id, "created_at": item.created_at})
        return as_of, rows

    def get(self, request):
        as_of, rows = self._rows(self._items(request))
        return Response({
            "scope": SCOPE,
            "units": market_stats.UNITS,
            "as_of": as_of,
            "rows": rows,
            "provenance": movers.provenance(),
        })

    def post(self, request):
        symbol = str(request.data.get("symbol", "")).strip()
        if not symbol:
            return Response({"detail": "symbol is required."}, status=status.HTTP_400_BAD_REQUEST)
        company = _tracked_company(request, symbol)
        _, created = WatchlistItem.objects.get_or_create(user=request.user, company=company)
        _, rows = self._rows(self._items(request).filter(company=company))
        return Response(rows[0], status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def delete(self, request, symbol=None):
        if not symbol:
            return Response({"detail": "symbol is required."}, status=status.HTTP_400_BAD_REQUEST)
        deleted, _ = WatchlistItem.objects.filter(user=request.user, company__symbol__iexact=symbol).delete()
        if not deleted:
            return Response({"detail": "Not in your watchlist."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


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
