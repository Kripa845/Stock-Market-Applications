from datetime import datetime, time, timedelta

import django_filters
from django.db.models import Count, Max, Min, Sum
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.companies.models import Company
from apps.floorsheet.api.serializers import (
    broker_metadata,
    broker_payload,
    FloorsheetSerializer,
    IntradayCandleQuerySerializer,
    IntradayCandleSerializer,
)
from apps.floorsheet.models import FloorsheetTransaction, IntradayCandle
from apps.floorsheet.services.intraday_candles import NPT, latest_candle_date
from apps.users.company_access import filter_company_queryset, require_company_access
from apps.users.permissions import HasAppPermission


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


class FloorsheetPagination(PageNumberPagination):
    # Default stays at the project's 20 rows; the Floorsheet page asks for more with ?page_size=.
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 200


class FloorsheetListAPIView(generics.ListAPIView):
    serializer_class = FloorsheetSerializer
    permission_classes = [HasAppPermission]
    permission_key = "view_trading_volume"
    queryset = FloorsheetTransaction.objects.select_related("company").all()
    pagination_class = FloorsheetPagination

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
        "trade_time",
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


FLOORSHEET_TOP_BROKERS = 5


FLOORSHEET_RECENT_DATES = 60


class FloorsheetSummaryAPIView(FloorsheetListAPIView):
    """
    GET /api/floorsheet/summary/ -- totals and top brokers for the same filters / search
    as /api/floorsheet/ (so the numbers always match the table), plus the dates that
    have floorsheet data (newest first) for the date picker.  Without a date filter it
    summarises the latest date only (all history is ~1M trades and slow to aggregate);
    ``date`` in the response says which day was used.
    """
    pagination_class = None
    DATE_PARAMS = ("date", "date_from", "date_to")

    def list(self, request, *args, **kwargs):
        visible = self.get_queryset()                  # company access applied, no filters
        dates = list(
            visible.order_by("-date").values_list("date", flat=True).distinct()[:FLOORSHEET_RECENT_DATES]
        )
        rows = self.filter_queryset(visible).order_by()
        day = request.query_params.get("date") or None
        if not any(request.query_params.get(name) for name in self.DATE_PARAMS):
            day = dates[0] if dates else None
            rows = rows.filter(date=day)
        totals = rows.aggregate(
            trades=Count("id"), quantity=Sum("quantity"), amount=Sum("amount"),
            companies=Count("company", distinct=True),
            first_trade=Min("trade_time"), last_trade=Max("trade_time"),
        )

        def top(side):
            field = f"{side}_broker"
            return list(
                rows.values(field)
                .annotate(quantity=Sum("quantity"), amount=Sum("amount"), trades=Count("id"))
                .order_by("-quantity")[:FLOORSHEET_TOP_BROKERS]
            )

        buyers, sellers = top("buyer"), top("seller")
        metadata = broker_metadata([r["buyer_broker"] for r in buyers] + [r["seller_broker"] for r in sellers])

        def broker_rows(items, field):
            return [
                {**broker_payload(item[field], metadata),
                 "quantity": item["quantity"], "amount": item["amount"], "trades": item["trades"]}
                for item in items
            ]

        return Response({
            "date": day,
            **totals,
            "top_buyers": broker_rows(buyers, "buyer_broker"),
            "top_sellers": broker_rows(sellers, "seller_broker"),
            "latest_date": dates[0] if dates else None,
            "dates": dates,
        })


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
