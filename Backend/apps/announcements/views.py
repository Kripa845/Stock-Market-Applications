from django.shortcuts import render

# Create your views here.
from django.conf import settings
from rest_framework import generics
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Announcement
from .serializers import AnnouncementSerializer


class Pager(PageNumberPagination):
    page_size = 12
    page_size_query_param = "size"
    max_page_size = 100


class AnnouncementList(generics.ListAPIView):
    serializer_class = AnnouncementSerializer
    pagination_class = Pager

    def get_queryset(self):
        p = self.request.query_params
        qs = Announcement.objects.all()
        if p.get("symbol"):
            qs = qs.filter(symbol__iexact=p["symbol"])
        if p.get("is_event") in ("true", "false"):
            qs = qs.filter(is_event=(p["is_event"] == "true"))
        if p.get("type"):
            qs = qs.filter(type=p["type"])
        if p.get("source"):
            qs = qs.filter(source__iexact=p["source"])
        if p.get("category"):
            qs = qs.filter(category=p["category"])
        if p.get("date_from"):
            qs = qs.filter(published_at__date__gte=p["date_from"])
        if p.get("date_to"):
            qs = qs.filter(published_at__date__lte=p["date_to"])
        return qs


class AnnouncementFilterOptions(APIView):
    def get(self, request):
        return Response({
            "is_event": [{"value": "true", "label": "True"}, {"value": "false", "label": "False"}],
            "type": [
                {"value": "Announcement", "label": "Announcement"},
                {"value": "AnnouncementAndEvent", "label": "Announcement and Event"},
                {"value": "Event", "label": "Event"},
                {"value": "NewsAndAlert", "label": "News and Alert"},
            ],
            "source": [{"value": s, "label": s} for s in ["Nepse", "Company", "Registrars", "Other"]],
            "category": [{"value": c, "label": c} for c in [
                "Nepse Circular", "Nepse News and Alert",
            ]],
            "symbols": sorted(settings.TRACKED_SYMBOLS),
        })