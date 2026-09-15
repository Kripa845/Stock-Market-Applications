from rest_framework import serializers
from .models import DailyAnalysis
from apps.companies.models import Company


class DailyAnalysisSerializer(serializers.ModelSerializer):
    company_symbol = serializers.CharField(source="company.symbol", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)

    class Meta:
        model = DailyAnalysis
        fields = [
            "id",
            "company",
            "company_symbol",
            "company_name",
            "date",
            "vwap",
            "close_price",
            "volume",
            "volume_average",
            "volume_anomaly",
            "pressure",
            "news_count",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]