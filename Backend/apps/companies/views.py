from django.shortcuts import render
from django.shortcuts import get_object_or_404
# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Company
from .serializers import CompanySerializer


class CompanyListAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        companies = Company.objects.filter(
            is_active=True
        )

        serializer = CompanySerializer(
            companies,
            many=True,
            context={"request": request},
        )

        return Response(serializer.data)
    
    
    
class CompanyDetailView(APIView):
    
    permission_classes=[IsAuthenticated]
    
    def get(self, request, pk):
        company = get_object_or_404(
            Company,
            pk=pk,
            is_active=True,
        )

        serializer = CompanySerializer(
            company,
            context={"request": request},
        )

        return Response(serializer.data)