from rest_framework import serializers

from apps.market_data.models import DailyPrice


class DailyPriceSerializers(serializers.ModelSerializer):
    company_symbol = serializers.CharField(
        source="company.symbol",
        read_only=True,
    )

    company_name = serializers.CharField(
        source="company.name",
        read_only=True,
    )
    class Meta:
    
        model=DailyPrice
        fields=[
            "id",
            "company",
            "company_symbol",
            "company_name",
            "date",
            "open",
            "close",
            "high",
            "low",
            "volume",
            "turnover",
           
        ]
        read_only_fields = [
            "id",
            "company_symbol",
            "company_name",
        ]
