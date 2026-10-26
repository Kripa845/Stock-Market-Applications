"""
/api/market/watchlist/ and /api/market/watchlists/ -- the user's saved companies.
Not cached: every response is per user and changes on each write.
"""

from decimal import Decimal

from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.companies.models import Company
from apps.market_data.api.market_views import SCOPE, _tracked_company
from apps.market_data.services import market_stats, movers
from apps.market_data.services import watchlist as watchlist_service
from apps.users.company_access import get_accessible_company_ids, require_company_access
from apps.users.models import Watchlist, WatchlistItem
from apps.users.permissions import HasViewMethodPermissions


class WatchlistAPIView(APIView):
    """
    GET    /api/market/watchlist/          the user's default list with latest ltp / change
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
