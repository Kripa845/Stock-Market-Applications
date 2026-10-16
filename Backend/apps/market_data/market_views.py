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
from decimal import Decimal

from django.core.cache import cache
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.companies.models import Company
from apps.market_indices.services import aggregates
from apps.market_intelligence.services import technical_summary
from apps.news.views import NewsArticleListAPIView
from apps.users.company_access import get_accessible_company_ids, require_company_access
from apps.users.models import Watchlist, WatchlistItem
from apps.users.permissions import HasAppPermission, HasViewMethodPermissions

from .models import DividendAnnouncement
from .services import dividends, live_prices, market_overview, market_stats, movers, top_movers
from .services import watchlist as watchlist_service

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


class DividendListAPIView(APIView):
    """
    GET /api/market/dividends/?fiscal_year=2082/2083|all&status=proposed

    Rows for every tracked company crawled from ShareSansar (see services.dividends); not
    narrowed to the caller's companies.
    No fiscal_year -> the latest crawled one.  Rows with no fiscal year are always included
    (``flags`` marks them).  Cached for 60 seconds per query.
    """
    permission_classes = [HasAppPermission]
    permission_key = "view_market_data"

    def get(self, request):
        status_filter = request.query_params.get("status", "").strip()
        if status_filter and status_filter not in DividendAnnouncement.Status.values:
            return Response({"detail": f"status must be one of {DividendAnnouncement.Status.values}."},
                            status=status.HTTP_400_BAD_REQUEST)
        requested = request.query_params.get("fiscal_year", "").strip()
        key = "market-api:dividends:" + hashlib.sha256(f"{requested}|{status_filter}".encode()).hexdigest()
        payload = cache.get(key)
        if payload is None:
            years = dividends.fiscal_years()
            fiscal_year = None if requested == "all" else (requested or (years[0] if years else None))
            payload = {
                "scope": "tracked_companies",
                "units": dividends.UNITS,
                "fiscal_year": fiscal_year or "all",
                "fiscal_years": years,
                "statuses": [{"value": value, "label": label} for value, label in DividendAnnouncement.Status.choices],
                "status_note": dividends.STATUS_NOTE,
                **dividends.last_updated(),
                "rows": dividends.dividend_rows(fiscal_year, status_filter or None),
            }
            cache.set(key, payload, CACHE_SECONDS)
        return Response(payload)


class WatchlistAPIView(APIView):
    """
    GET    /api/market/watchlist/            the user's default list with latest ltp / change
    POST   /api/market/watchlist/            {"symbol": "NABIL"}
    DELETE /api/market/watchlist/<symbol>/
    Not cached: it is per user and changes on every POST / DELETE.
    Works on the default list only; the watchlist page uses /api/market/watchlists/.
    """
    permission_classes = [HasViewMethodPermissions]

    def get_required_permissions(self, request):
        return {
            "POST": "add_watchlist",
            "DELETE": "remove_watchlist",
        }.get(request.method, "view_watchlist")

    def _items(self, request):
        items = WatchlistItem.objects.filter(watchlist=Watchlist.default_for(request.user))
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
        _, created = WatchlistItem.objects.get_or_create(
            user=request.user, watchlist=Watchlist.default_for(request.user), company=company,
        )
        _, rows = self._rows(self._items(request).filter(company=company))
        return Response(rows[0], status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def delete(self, request, symbol=None):
        if not symbol:
            return Response({"detail": "symbol is required."}, status=status.HTTP_400_BAD_REQUEST)
        deleted, _ = self._items(request).filter(company__symbol__iexact=symbol).delete()
        if not deleted:
            return Response({"detail": "Not in your watchlist."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


def _watchlist_payload(watchlist):
    return {
        "id": watchlist.id,
        "name": watchlist.name,
        "is_default": watchlist.is_default,
        "item_count": getattr(watchlist, "item_count", None),
        "created_at": watchlist.created_at,
    }


def _clean_watchlist_name(request, user, exclude_id=None):
    """(name, error response)."""
    name = str(request.data.get("name", "")).strip()
    if not name:
        return None, Response({"detail": "name is required."}, status=status.HTTP_400_BAD_REQUEST)
    if len(name) > 60:
        return None, Response({"detail": "name must be at most 60 characters."}, status=status.HTTP_400_BAD_REQUEST)
    taken = Watchlist.objects.filter(user=user, name__iexact=name).exclude(id=exclude_id)
    if taken.exists():
        return None, Response({"detail": "You already have a watchlist with this name."}, status=status.HTTP_400_BAD_REQUEST)
    return name, None


class _WatchlistPermissions:
    """GET = view_watchlist; adding lists / companies and editing them = add_watchlist; DELETE = remove_watchlist."""
    permission_classes = [HasViewMethodPermissions]

    def get_required_permissions(self, request):
        return {
            "POST": "add_watchlist",
            "PATCH": "add_watchlist",
            "DELETE": "remove_watchlist",
        }.get(request.method, "view_watchlist")


class WatchlistsAPIView(_WatchlistPermissions, APIView):
    """
    GET  /api/market/watchlists/      the user's named lists (a "Primary" default is created on first use)
    POST /api/market/watchlists/      {"name": "Banks"}
    """

    def get(self, request):
        Watchlist.default_for(request.user)
        lists = Watchlist.objects.filter(user=request.user).annotate(item_count=Count("items"))
        return Response({"results": [_watchlist_payload(w) for w in lists]})

    def post(self, request):
        name, error = _clean_watchlist_name(request, request.user)
        if error:
            return error
        has_default = Watchlist.objects.filter(user=request.user, is_default=True).exists()
        watchlist = Watchlist.objects.create(user=request.user, name=name, is_default=not has_default)
        watchlist.item_count = 0
        return Response(_watchlist_payload(watchlist), status=status.HTTP_201_CREATED)


class WatchlistDetailAPIView(_WatchlistPermissions, APIView):
    """
    PATCH  /api/market/watchlists/<id>/    {"name": "...", "is_default": true}
    DELETE /api/market/watchlists/<id>/    another list becomes the default if this one was
    """

    def patch(self, request, pk):
        watchlist = get_object_or_404(Watchlist, pk=pk, user=request.user)
        if "name" in request.data:
            name, error = _clean_watchlist_name(request, request.user, exclude_id=watchlist.id)
            if error:
                return error
            watchlist.name = name
        if request.data.get("is_default") in (True, "true", "1", 1):
            with transaction.atomic():
                Watchlist.objects.filter(user=request.user, is_default=True).exclude(id=watchlist.id).update(is_default=False)
                watchlist.is_default = True
                watchlist.save()
        else:
            watchlist.save()
        watchlist.item_count = watchlist.items.count()
        return Response(_watchlist_payload(watchlist))

    def delete(self, request, pk):
        watchlist = get_object_or_404(Watchlist, pk=pk, user=request.user)
        was_default = watchlist.is_default
        watchlist.delete()
        if was_default:
            replacement = Watchlist.objects.filter(user=request.user).order_by("created_at").first()
            if replacement:
                replacement.is_default = True
                replacement.save(update_fields=["is_default"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class WatchlistItemsAPIView(_WatchlistPermissions, APIView):
    """
    GET  /api/market/watchlists/<id>/items/   rows (latest crawled session + holding) and summary totals
    POST /api/market/watchlists/<id>/items/   {"symbol": "NABIL", "units": 0, "wacc": 0} -- any active company
    """

    def _items(self, request, watchlist):
        items = watchlist.items.select_related("company").order_by("-created_at")
        accessible_ids = get_accessible_company_ids(request.user)
        if accessible_ids is not None:
            items = items.filter(company_id__in=accessible_ids)
        return items

    def get(self, request, pk):
        watchlist = get_object_or_404(Watchlist, pk=pk, user=request.user)
        rows = watchlist_service.item_rows(self._items(request, watchlist))
        return Response({
            "watchlist": _watchlist_payload(watchlist),
            "rows": rows,
            "summary": watchlist_service.summary(rows),
            "price_source": market_stats.PRICE_SOURCE,
        })

    def post(self, request, pk):
        watchlist = get_object_or_404(Watchlist, pk=pk, user=request.user)
        symbol = str(request.data.get("symbol", "")).strip()
        if not symbol:
            return Response({"detail": "symbol is required."}, status=status.HTTP_400_BAD_REQUEST)
        company = get_object_or_404(Company, symbol__iexact=symbol, is_active=True)
        require_company_access(request.user, company)
        holding, error = _clean_holding(request.data)
        if error:
            return error
        item, created = WatchlistItem.objects.get_or_create(
            user=request.user, watchlist=watchlist, company=company, defaults=holding,
        )
        if not created:
            return Response({"detail": f"{company.symbol} is already in {watchlist.name}."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(watchlist_service.item_rows([item])[0], status=status.HTTP_201_CREATED)


def _clean_holding(data):
    """({"units": int, "wacc": Decimal} for the fields present, error response)."""
    holding = {}
    try:
        if "units" in data and data["units"] not in ("", None):
            holding["units"] = int(data["units"])
            if holding["units"] < 0:
                raise ValueError
        if "wacc" in data and data["wacc"] not in ("", None):
            holding["wacc"] = Decimal(str(data["wacc"])).quantize(Decimal("0.01"))
            if holding["wacc"] < 0 or holding["wacc"] >= Decimal("1e10"):
                raise ValueError
    except (ValueError, ArithmeticError):
        return None, Response(
            {"detail": "units must be a whole number and wacc a price, both zero or more."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return holding, None


class WatchlistItemDetailAPIView(_WatchlistPermissions, APIView):
    """
    PATCH  /api/market/watchlists/<id>/items/<item_id>/   {"units": 100, "wacc": 380.5}
    DELETE /api/market/watchlists/<id>/items/<item_id>/
    """

    def _item(self, request, pk, item_id):
        return get_object_or_404(
            WatchlistItem.objects.select_related("company"),
            pk=item_id, watchlist_id=pk, watchlist__user=request.user,
        )

    def patch(self, request, pk, item_id):
        item = self._item(request, pk, item_id)
        holding, error = _clean_holding(request.data)
        if error:
            return error
        for field, value in holding.items():
            setattr(item, field, value)
        item.save()
        return Response(watchlist_service.item_rows([item])[0])

    def delete(self, request, pk, item_id):
        self._item(request, pk, item_id).delete()
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
