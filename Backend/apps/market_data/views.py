from django.shortcuts import render
from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from .models import DailyPrice,FloorsheetTransaction
from .serializers import DailyPriceSerializers,FloorsheetSerializer
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
# Create your views here.
class CompanyPriceList(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
    
            prices = DailyPrice.objects.filter(
               company__is_active=True
            ).select_related("company")
    
            serializer = DailyPriceSerializers(
                prices,
                many=True
            )
    
            return Response(serializer.data)
        
class FloorsheetListAPIView(generics.ListAPIView):

    serializer_class = (FloorsheetSerializer)

    permission_classes = [
        IsAuthenticated
    ]

    queryset = (
        FloorsheetTransaction.objects
        .select_related("company")
        .all()
    )

    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    ]

    filterset_fields = [
        "company",
        "date",
        "buyer_broker",
        "seller_broker",
    ]

    search_fields = [
        "company__symbol",
        "buyer_broker",
        "seller_broker",
        "transaction_id",
    ]

    ordering_fields = [
        "date",
        "quantity",
        "rate",
        "amount",
    ]

    ordering = [
        "-date"
    ]