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
from apps.news.views import NewsArticleListAPIView
from apps.users.company_access import get_accessible_company_ids, require_company_access
from apps.users.models import WatchlistItem
from apps.users.permissions import HasAppPermission, HasViewMethodPermissions

from .services import market_stats

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


PUBLIC_MOVER_FIELDS = ("symbol", "name", "sector", "ltp", "prev_close", "change", "change_pct", "volume", "turnover", "sparkline")
PUBLIC_BASKET_DAYS = 30


class PublicTrackedSnapshotAPIView(APIView):
    """
    GET /api/market/public/snapshot/

    Unauthenticated, for the public landing page: the tracked companies'
    latest summary, every tracked company's price / change / 7-close
    sparkline, and the last 30 Tracked Basket levels.  Nothing else --
    no brokers, signals, dividends, transactions or watchlists.
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "public"

    def get(self, request):
        key = "market-api:public-snapshot"
        payload = cache.get(key)
        if payload is None:
            movers = market_stats.ranked_by_change()
            summary = market_stats.tracked_summary(movers["trade_date"])
            payload = {
                "scope": SCOPE,
                "units": market_stats.UNITS,
                "trade_date": movers["trade_date"],
                "summary": {
                    name: summary.get(name)
                    for name in (
                        "tracked_count", "advanced", "declined", "unchanged", "no_prev_close",
                        "positive_circuit", "negative_circuit", "total_turnover", "total_traded_shares",
                    )
                },
                "movers": [{name: row[name] for name in PUBLIC_MOVER_FIELDS} for row in movers["rows"]],
                "basket": market_stats.basket_index(PUBLIC_BASKET_DAYS),
            }
            cache.set(key, payload, CACHE_SECONDS)
        return Response(payload)


class TrackedSummaryAPIView(APIView):
    """GET /api/market/summary/?date=YYYY-MM-DD"""
    permission_classes = [HasAppPermission]
    permission_key = "view_market_data"

    def get(self, request):
        trade_date, error = _parse_date(request)
        if error:
            return error
        return _cached(request, lambda ids: {
            "summary": market_stats.tracked_summary(trade_date, ids),
            "circuit_threshold_pct": market_stats.CIRCUIT_THRESHOLD_PCT,
            "note": market_stats.CORPORATE_ACTION_NOTE,
        })


class TrackedMoversAPIView(APIView):
    """GET /api/market/movers/?date=YYYY-MM-DD -- every tracked company ranked by change_pct."""
    permission_classes = [HasAppPermission]
    permission_key = "view_market_data"

    def get(self, request):
        trade_date, error = _parse_date(request)
        if error:
            return error
        return _cached(request, lambda ids: {
            **market_stats.ranked_by_change(trade_date, ids),
            "note": market_stats.CORPORATE_ACTION_NOTE,
        })


class TrackedTopAPIView(APIView):
    """GET /api/market/top-turnover/ | top-volume/ | top-transactions/ ?date=&limit="""
    permission_classes = [HasAppPermission]
    permission_key = "view_market_data"
    metric = None

    def get(self, request):
        trade_date, error = _parse_date(request)
        if error:
            return error
        try:
            limit = max(1, min(int(request.query_params.get("limit", 10)), 50))
        except ValueError:
            limit = 10
        return _cached(request, lambda ids: market_stats.top_by(self.metric, trade_date, ids, limit))


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

    def get(self, request):
        return Response({"scope": SCOPE, "units": market_stats.UNITS, "rows": market_stats.watchlist_rows(self._items(request))})

    def post(self, request):
        symbol = str(request.data.get("symbol", "")).strip()
        if not symbol:
            return Response({"detail": "symbol is required."}, status=status.HTTP_400_BAD_REQUEST)
        company = _tracked_company(request, symbol)
        _, created = WatchlistItem.objects.get_or_create(user=request.user, company=company)
        rows = market_stats.watchlist_rows(self._items(request).filter(company=company))
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
