from datetime import date, datetime, time, timedelta

from django.shortcuts import get_object_or_404, render
from rest_framework import generics
from rest_framework.views import APIView
from apps.users.permissions import HasAppPermission
from apps.users.company_access import filter_company_queryset, require_company_access
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
import django_filters
from rest_framework.filters import SearchFilter, OrderingFilter

from apps.companies.models import Company
from .models import DailyPrice, FloorsheetTransaction, IntradayCandle
from .services.intraday_candles import NPT, latest_candle_date
from .services.price_source import requested_price_source
from .serializers import (
    DailyPriceSerializers,
    FloorsheetSerializer,
    IntradayCandleQuerySerializer,
    IntradayCandleSerializer,
)


class FloorsheetFilter(django_filters.FilterSet):
    company_id = django_filters.NumberFilter(field_name="company_id")
    symbol = django_filters.CharFilter(field_name="company__symbol", lookup_expr="iexact")
    date_from = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="date", lookup_expr="lte")

    class Meta:
        model = FloorsheetTransaction
        fields = [
            "company",
            "company_id",
            "symbol",
            "date",
            "buyer_broker",
            "seller_broker",
        ]


class CompanyPriceList(APIView):
    permission_classes = [HasAppPermission]
    permission_key = "view_price_history"

    def get(self, request):
        prices = DailyPrice.objects.filter(
            company__is_active=True, source=requested_price_source(request)
        ).select_related("company")

        prices = filter_company_queryset(prices, request.user)

        company_id = request.query_params.get("company_id")
        if company_id:
            require_company_access(request.user, company_id)
            prices = prices.filter(company_id=company_id)

        serializer = DailyPriceSerializers(prices[:500], many=True)
        return Response(serializer.data)


class FloorsheetListAPIView(generics.ListAPIView):
    serializer_class = FloorsheetSerializer
    permission_classes = [HasAppPermission]
    permission_key = "view_trading_volume"
    queryset = FloorsheetTransaction.objects.select_related("company").all()

    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    ]
    filterset_class = FloorsheetFilter
    search_fields = [
        "company__symbol",
        "company__name",
        "buyer_broker",
        "seller_broker",
        "transaction_id",
    ]
    ordering_fields = [
        "date",
        "quantity",
        "rate",
        "amount",
        "id",
    ]
    ordering = ["-date", "-id"]

    def get_queryset(self):
        company_id = self.request.query_params.get("company_id")
        if company_id:
            require_company_access(self.request.user, company_id)
        return filter_company_queryset(
            super().get_queryset(), self.request.user
        )


class StockIntradayCandlesAPIView(APIView):
    """
    GET /api/stocks/<symbol>/intraday/?interval=5m&date=YYYY-MM-DD

    Stored IntradayCandle rows for one Asia/Kathmandu trading day (default:
    the latest day with candles), oldest first.  One day is at most 240
    candles, so the response is not paginated, like the daily prices endpoint.
    """
    permission_classes = [HasAppPermission]
    permission_key = "view_price_history"

    def get(self, request, symbol):
        company = get_object_or_404(Company, symbol__iexact=symbol, is_active=True)
        require_company_access(request.user, company.pk)

        params = IntradayCandleQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        interval = params.validated_data["interval"]
        day = params.validated_data.get("date") or latest_candle_date(company)

        candles = IntradayCandle.objects.none()
        if day is not None:
            day_start = datetime.combine(day, time.min, tzinfo=NPT)
            candles = IntradayCandle.objects.filter(
                company=company,
                interval=interval,
                bucket_start__gte=day_start,
                bucket_start__lt=day_start + timedelta(days=1),
            ).order_by("bucket_start")

        data = IntradayCandleSerializer(candles, many=True).data
        return Response(
            {
                "company_id": company.id,
                "symbol": company.symbol,
                "name": company.name,
                "interval": interval,
                "date": day.isoformat() if day else None,
                "count": len(data),
                "candles": data,
            }
        )
