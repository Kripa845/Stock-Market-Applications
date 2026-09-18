from datetime import datetime, timedelta
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q
from apps.market_data.models import DailyPrice, FloorsheetTransaction
from apps.market_data.serializers import DailyPriceSerializers, FloorsheetSerializer
from apps.users.permissions import HasAppPermission, HasViewMethodPermissions
from .models import Company, TrackedCompany
from .serializers import CompanySerializer


class CompanyListCreateAPIView(generics.ListCreateAPIView):
    """
    GET /api/companies/ - List tracked or all companies
    POST /api/companies/ - Create company (Admin only)
    """
    permission_classes = [HasViewMethodPermissions]
    serializer_class = CompanySerializer

    def get_required_permissions(self, request):
        return ["view_companies"] if request.method == "GET" else ["create_companies"]

    def get_queryset(self):
     queryset = (
        Company.objects
        .prefetch_related(
            "dailyprice_set",
            "article_tags__article",
        )
        .select_related(
            "tracking",
        )
    )

     search = self.request.query_params.get(
        "search"
    )

     sector = self.request.query_params.get(
        "sector"
    )

     tracking = self.request.query_params.get(
        "tracking"
    )

     tracked_only = self.request.query_params.get(
        "tracked_only"
     )

     status_param = self.request.query_params.get(
        "status"
    )

     if search:
        queryset = queryset.filter(
            Q(symbol__icontains=search)
            | Q(name__icontains=search)
        )

     if sector:
        queryset = queryset.filter(
            sector__iexact=sector
        )

     if status_param == "active":
        queryset = queryset.filter(
            is_active=True
        )

     elif status_param == "inactive":
        queryset = queryset.filter(
            is_active=False
        )

     if tracking == "tracked":
        queryset = queryset.filter(
            tracking__is_tracked=True
        )

     elif tracking == "not_tracked":
        queryset = queryset.filter(
            Q(tracking__isnull=True)
            | Q(tracking__is_tracked=False)
        )

     if tracked_only and tracked_only.lower() == "true":
        queryset = queryset.filter(tracking__is_tracked=True)

     return queryset.order_by("symbol")
       
     


class CompanyDetailUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET /api/companies/:id/ - Company detail
    PATCH/PUT /api/companies/:id/ - Update company (Admin only)
    DELETE /api/companies/:id/ - Delete company (Admin only)
    """
    permission_classes = [HasViewMethodPermissions]
    serializer_class = CompanySerializer
    queryset = Company.objects.all()

    def get_required_permissions(self, request):
        return {
            "GET": ["view_companies"],
            "PUT": ["edit_companies"],
            "PATCH": ["edit_companies"],
            "DELETE": ["delete_companies"],
        }.get(request.method, [])


class CompanyToggleTrackAPIView(APIView):
    """
    POST /api/companies/:id/toggle-track/
    Role-gated: Admin only
    """
    permission_classes = [HasAppPermission]
    permission_key = "manage_tracked_companies"

    def post(self, request, pk):
        company = get_object_or_404(Company, pk=pk)
        tracked_obj, _ = TrackedCompany.objects.get_or_create(
            company=company,
            defaults={"is_tracked": True},
        )
        # Toggle or set explicit status
        is_tracked_param = request.data.get("is_tracked")
        if is_tracked_param is not None:
            tracked_obj.is_tracked = bool(is_tracked_param)
        else:
            tracked_obj.is_tracked = not tracked_obj.is_tracked
        tracked_obj.save()

        return Response(
            {
                "id": company.id,
                "symbol": company.symbol,
                "is_tracked": tracked_obj.is_tracked,
                "message": f"Company {company.symbol} tracking set to {tracked_obj.is_tracked}.",
            },
            status=status.HTTP_200_OK,
        )


class CompanyPricesAPIView(APIView):
    """
    GET /api/companies/:id/prices?range=30d
    Ranges: 7d, 30d, 31d, 90d, 180d, 1y, all

    Rolling window design
    ---------------------
    The window is anchored to **today** (not the latest stored date) so
    the result is always the genuine last N calendar days of stored data.
    This means:
      - range=31d  → today - 31 days  (the canonical rolling month)
      - range=30d  → today - 30 days  (kept for backwards compatibility)
      - range=7d   → today - 7 days
      etc.

    Historical records are never deleted; the filter is query-time only.
    """
    permission_classes = [HasAppPermission]
    permission_key = "view_price_history"

    # Rolling window sizes in calendar days
    RANGE_DAYS = {
        "7d":   7,
        "30d":  30,
        "31d":  31,
        "90d":  90,
        "180d": 180,
        "1y":   365,
        "365d": 365,
    }

    def get(self, request, pk):
        company = get_object_or_404(Company, pk=pk)
        range_param = request.query_params.get("range", "31d").lower()

        prices_qs = DailyPrice.objects.filter(company=company).order_by("date")

        if range_param in self.RANGE_DAYS:
            # Anchor to today so the window is always the current rolling period.
            start_date = timezone.localdate() - timedelta(days=self.RANGE_DAYS[range_param])
            prices_qs = prices_qs.filter(date__gte=start_date)
        elif range_param != "all":
            # Unknown range — fall back to 31-day rolling window.
            start_date = timezone.localdate() - timedelta(days=31)
            prices_qs = prices_qs.filter(date__gte=start_date)
        # range == "all" → no date filter; return full history

        serializer = DailyPriceSerializers(prices_qs, many=True)
        return Response(
            {
                "company_id": company.id,
                "symbol": company.symbol,
                "name": company.name,
                "range": range_param,
                "count": prices_qs.count(),
                "prices": serializer.data,
            }
        )


class CompanyFloorsheetAPIView(APIView):
    """
    GET /api/companies/:id/floorsheet?date=YYYY-MM-DD
    """
    permission_classes = [HasAppPermission]
    permission_key = "view_market_data"

    def get(self, request, pk):
        company = get_object_or_404(Company, pk=pk)
        date_param = request.query_params.get("date")

        qs = FloorsheetTransaction.objects.filter(company=company)
        if date_param:
            qs = qs.filter(date=date_param)

        # Get latest available date if no date provided and results exist
        if not date_param and qs.exists():
            latest_date = qs.order_by("-date").first().date
            qs = qs.filter(date=latest_date)
            date_param = str(latest_date)

        transactions = qs.order_by("-id")[:200]
        serializer = FloorsheetSerializer(transactions, many=True)

        return Response(
            {
                "company_id": company.id,
                "symbol": company.symbol,
                "date": date_param,
                "count": len(serializer.data),
                "transactions": serializer.data,
            }
        )
        
        
        
class CompanySectorsAPIView(APIView):
    permission_classes = [HasAppPermission]
    permission_key = "view_companies"

    def get(self, request):
        sectors = (
            Company.objects
            .values_list(
                "sector",
                flat=True,
            )
            .distinct()
            .order_by("sector")
        )

        return Response(
            list(sectors)
        )
