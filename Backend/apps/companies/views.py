from datetime import datetime, timedelta
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q
from apps.market_data.models import DailyPrice, FloorsheetTransaction
from apps.market_data.serializers import DailyPriceSerializers, FloorsheetSerializer
from apps.market_data.volume_anomalies import get_volume_anomalies
from apps.market_data.volume_anomaly_serializers import (
    VolumeAnomalyQuerySerializer,
    VolumeAnomalySerializer,
)
from apps.market_data.rvol_serializers import RvolPointSerializer, RvolQuerySerializer
from apps.market_data.services.rvol import get_company_rvol
from apps.analysis.serializers import (
    NewsSentimentCorrelationQuerySerializer,
    NewsSentimentForwardResponseSerializer,
)
from apps.analysis.services.news_sentiment_forward import get_company_news_sentiment_forward
from apps.users.permissions import HasAppPermission, HasViewMethodPermissions
from apps.users.company_access import (
    filter_company_queryset,
    require_company_access,
)
from .models import Company, TrackedCompany
from .serializers import CompanySerializer


def _company_list_queryset():
    """
    Shared queryset with all prefetches needed by CompanySerializer.

    Using Prefetch with an ordered queryset so that serializer methods
    such as get_latest_price() can call .first() / [:N] on the
    already-cached prefetch result without issuing additional SQL.

    Without this, every SerializerMethodField that calls
    obj.dailyprice_set.order_by("-date")... fires a new query,
    causing N×M extra queries for a list of N companies.
    """
    return (
        Company.objects
        .prefetch_related(
            Prefetch(
                "dailyprice_set",
                queryset=DailyPrice.objects.order_by("-date"),
                to_attr="_prices_cache",
            ),
            "article_tags__article",
        )
        .select_related("tracking")
    )


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
        queryset = _company_list_queryset()

        search = self.request.query_params.get("search")
        sector = self.request.query_params.get("sector")
        tracking = self.request.query_params.get("tracking")
        tracked_only = self.request.query_params.get("tracked_only")
        status_param = self.request.query_params.get("status")

        if search:
            queryset = queryset.filter(
                Q(symbol__icontains=search) | Q(name__icontains=search)
            )
        if sector:
            queryset = queryset.filter(sector__iexact=sector)
        if status_param == "active":
            queryset = queryset.filter(is_active=True)
        elif status_param == "inactive":
            queryset = queryset.filter(is_active=False)
        if tracking == "tracked":
            queryset = queryset.filter(tracking__is_tracked=True)
        elif tracking == "not_tracked":
            queryset = queryset.filter(
                Q(tracking__isnull=True) | Q(tracking__is_tracked=False)
            )
        if tracked_only and tracked_only.lower() == "true":
            queryset = queryset.filter(tracking__is_tracked=True)

        queryset = filter_company_queryset(
            queryset,
            self.request.user,
            "id",
        )

        return queryset.order_by("symbol")


class CompanyDetailUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET /api/companies/:id/ - Company detail
    PATCH/PUT /api/companies/:id/ - Update company (Admin only)
    DELETE /api/companies/:id/ - Delete company (Admin only)
    """
    permission_classes = [HasViewMethodPermissions]
    serializer_class = CompanySerializer

    def get_queryset(self):
        return _company_list_queryset()

    def get_object(self):
        company = super().get_object()

        if self.request.method == "GET":
            require_company_access(
                self.request.user,
                company.pk,
            )

        return company

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
        require_company_access(request.user, company.pk)
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
        require_company_access(request.user, company.pk)
        range_param = request.query_params.get("range", "31d").lower()

        prices_qs = DailyPrice.objects.filter(company=company).order_by("date")
        if request.query_params.get("source") == "crawled":
            prices_qs = prices_qs.filter(source="crawled")

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


class CompanyVolumeAnomaliesAPIView(APIView):
    """GET /api/companies/<symbol>/volume-anomalies/"""
    permission_classes = [HasAppPermission]
    permission_key = "view_trading_volume"

    def get(self, request, symbol):
        company = get_object_or_404(Company, symbol__iexact=symbol, is_active=True)
        require_company_access(request.user, company.pk)

        params = VolumeAnomalyQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        start_date = params.validated_data.get("start_date")
        end_date = params.validated_data.get("end_date")
        if start_date and end_date and start_date > end_date:
            return Response({"detail": "start_date must be on or before end_date."}, status=400)

        results = get_volume_anomalies(company, start_date, end_date, params.validated_data["lookback"])
        return Response(VolumeAnomalySerializer(results, many=True).data)


class CompanyRvolAPIView(APIView):
    """GET /api/companies/<symbol>/rvol/"""
    permission_classes = [HasAppPermission]
    permission_key = "view_trading_volume"

    def get(self, request, symbol):
        company = get_object_or_404(Company, symbol__iexact=symbol, is_active=True)
        require_company_access(request.user, company.pk)
        params = RvolQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        values = params.validated_data
        rows = get_company_rvol(
            company,
            start_date=values.get("start_date"),
            end_date=values.get("end_date"),
            ma_length=values["ma_length"],
            ma_type=values["ma_type"],
            threshold=values["threshold"],
        )
        return Response(RvolPointSerializer(rows, many=True).data)


class CompanyNewsSentimentCorrelationAPIView(APIView):
    """Exploratory daily sentiment versus the next one or two trading sessions."""
    permission_classes = [HasAppPermission]
    permission_key = "view_analysis"

    def get(self, request, symbol):
        company = get_object_or_404(Company, symbol__iexact=symbol, is_active=True)
        require_company_access(request.user, company.pk)
        params = NewsSentimentCorrelationQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        start_date = params.validated_data.get("start_date")
        end_date = params.validated_data.get("end_date")
        if start_date and end_date and start_date > end_date:
            return Response({"detail": "start_date must be on or before end_date."}, status=400)

        result = get_company_news_sentiment_forward(company, start_date, end_date)
        payload = {
            "company_id": company.pk,
            "symbol": company.symbol,
            **result,
            "disclaimer": (
                "Exploratory, not a trading signal — small sample size. "
                "Correlation describes association and does not imply causation."
            ),
        }
        return Response(NewsSentimentForwardResponseSerializer(payload).data)


class CompanyFloorsheetAPIView(APIView):
    """
    GET /api/companies/:id/floorsheet?date=YYYY-MM-DD
    """
    permission_classes = [HasAppPermission]
    permission_key = "view_market_data"

    def get(self, request, pk):
        company = get_object_or_404(Company, pk=pk)
        require_company_access(request.user, company.pk)
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
        companies = filter_company_queryset(
            Company.objects.filter(is_active=True), request.user, "id"
        )
        sectors = (
            companies
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
from apps.users.company_access import (
    get_accessible_company_ids,
)


def get_queryset(self):

    user = self.request.user

    queryset = Company.objects.filter(
        is_active=True
    )

    if user.is_admin():
        return queryset

    company_ids = get_accessible_company_ids(
        user
    )

    return queryset.filter(
        id__in=company_ids
    )
