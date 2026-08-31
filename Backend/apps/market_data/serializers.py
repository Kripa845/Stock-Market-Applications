from rest_framework import serializers
from .models import DailyPrice,FloorsheetTransaction

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
            "date",
            "open",
            "close",
            "high",
            "low",
            "volume",
            "turnover",
            
        ]
        
        
class FloorsheetSerializer(serializers.ModelSerializer):
    class Meta:
        
        model=FloorsheetTransaction
        fields=[
             "id",
            "company",
            "date",
            "transaction_id",
            "buyer_broker",
            "seller_broker",
            "quantity",
            "rate",
            "amount",
            "created_at",
            
        ]
        read_only_fields = [
            "id",
            "created_at",
        ]
    def validate(self, attrs):

        if attrs["quantity"] <= 0:
            raise serializers.ValidationError(
                {
                    "quantity":
                    "Quantity must be greater than zero."
                }
            )

        if attrs["rate"] <= 0:
            raise serializers.ValidationError(
                {
                    "rate":
                    "Rate must be greater than zero."
                }
            )

        return attrs