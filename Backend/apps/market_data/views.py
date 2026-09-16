from django.shortcuts import render
from rest_framework import generics
from rest_framework.views import APIView
from apps.users.permissions import HasAppPermission
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
import django_filters
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import DailyPrice, FloorsheetTransaction
from .serializers import DailyPriceSerializers, FloorsheetSerializer


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
            company__is_active=True
        ).select_related("company")

        company_id = request.query_params.get("company_id")
        if company_id:
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
