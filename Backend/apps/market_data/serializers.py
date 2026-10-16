from rest_framework import serializers
from .models import Broker, DailyPrice, FloorsheetTransaction
from .services.sharehub_time import NPT


def broker_metadata(codes):
    normalized = {str(code).strip() for code in codes if code is not None}
    return {
        broker.broker_code: {
            "name": broker.name,
            "short_name": broker.short_name,
            "logo_url": f"/broker-logos/{broker.logo}" if broker.logo else None,
        }
        for broker in Broker.objects.filter(broker_code__in=normalized)
    }


def broker_payload(code, metadata):
    code = str(code or "").strip()
    details = metadata.get(code)
    return {
        "broker_code": code,
        "name": details["name"] if details else f"Broker {code}",
        "short_name": details["short_name"] if details else f"Broker {code}",
        "logo_url": details["logo_url"] if details else None,
    }


class BrokerMetadataListSerializer(serializers.ListSerializer):
    def to_representation(self, data):
        rows = list(data)
        codes = []
        for row in rows:
            if isinstance(row, FloorsheetTransaction):
                codes.extend((row.buyer_broker, row.seller_broker))
            else:
                codes.append(row.get("broker"))
        metadata = self.context.get("broker_metadata")
        self.child._broker_metadata = (
            metadata if metadata is not None else broker_metadata(codes)
        )
        return super().to_representation(rows)

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
        
class FloorsheetSerializer(serializers.ModelSerializer):
    symbol = serializers.CharField(source="company.symbol", read_only=True)
    buyer_broker_name = serializers.SerializerMethodField()
    buyer_broker_short_name = serializers.SerializerMethodField()
    buyer_broker_logo_url = serializers.SerializerMethodField()
    seller_broker_name = serializers.SerializerMethodField()
    seller_broker_short_name = serializers.SerializerMethodField()
    seller_broker_logo_url = serializers.SerializerMethodField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = self.instance
        if isinstance(instance, FloorsheetTransaction):
            self._broker_metadata = broker_metadata(
                (instance.buyer_broker, instance.seller_broker)
            )
        else:
            self._broker_metadata = {}

    def _broker_detail(self, obj, side, key):
        return broker_payload(
            getattr(obj, f"{side}_broker"), self._broker_metadata
        )[key]

    def get_buyer_broker_name(self, obj):
        return self._broker_detail(obj, "buyer", "name")

    def get_buyer_broker_short_name(self, obj):
        return self._broker_detail(obj, "buyer", "short_name")

    def get_buyer_broker_logo_url(self, obj):
        return self._broker_detail(obj, "buyer", "logo_url")

    def get_seller_broker_name(self, obj):
        return self._broker_detail(obj, "seller", "name")

    def get_seller_broker_short_name(self, obj):
        return self._broker_detail(obj, "seller", "short_name")

    def get_seller_broker_logo_url(self, obj):
        return self._broker_detail(obj, "seller", "logo_url")

    class Meta:
        list_serializer_class = BrokerMetadataListSerializer
        model=FloorsheetTransaction
        fields=[
             "id",
            "company",
            "symbol",
            "date",
            "trade_time",
            "transaction_id",
            "buyer_broker",
            "seller_broker",
            "buyer_broker_name",
            "buyer_broker_short_name",
            "buyer_broker_logo_url",
            "seller_broker_name",
            "seller_broker_short_name",
            "seller_broker_logo_url",
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


class IntradayCandleQuerySerializer(serializers.Serializer):
    """Query parameters of GET /api/stocks/<symbol>/intraday/."""

    interval = serializers.ChoiceField(
        choices=["1m", "5m", "15m", "30m", "1h"],
        default="5m",
    )
    # Trading day in Asia/Kathmandu; omitted = the latest day with candles.
    date = serializers.DateField(required=False, input_formats=["%Y-%m-%d"])


class IntradayCandleSerializer(serializers.Serializer):
    # Same keys as the daily candle (plus turnover / trade_count), with `time`
    # an ISO datetime in Asia/Kathmandu (e.g. 2026-10-09T11:05:00+05:45).
    # Always rendered in Nepal time with an explicit +05:45 offset, whatever
    # time zone is active for the request.
    time = serializers.DateTimeField(source="bucket_start", default_timezone=NPT)
    open = serializers.DecimalField(max_digits=14, decimal_places=4)
    high = serializers.DecimalField(max_digits=14, decimal_places=4)
    low = serializers.DecimalField(max_digits=14, decimal_places=4)
    close = serializers.DecimalField(max_digits=14, decimal_places=4)
    volume = serializers.IntegerField()
    turnover = serializers.DecimalField(max_digits=20, decimal_places=4)
    trade_count = serializers.IntegerField()
