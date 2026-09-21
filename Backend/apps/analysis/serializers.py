# from rest_framework import serializers

# from .models import DailyAnalysis
# from .services.daily_metrics import (
#     BASELINE_SESSIONS,
#     PRESSURE_METHOD,
#     VOLUME_ANOMALY_THRESHOLD,
# )


# class DailyAnalysisSerializer(serializers.ModelSerializer):
#     """
#     Stored per-trading-day analytical state.

#     ``vwap`` is the DAILY VWAP (turnover / volume for that one day).
#     ``vwap_30d`` is the separate rolling-window aggregate.  They are
#     exposed under distinct names so a frontend can never accidentally
#     render one as the other.
#     """

#     company_symbol = serializers.CharField(source="company.symbol", read_only=True)
#     company_name = serializers.CharField(source="company.name", read_only=True)

#     # Explicit alias so the API speaks the documented metric name while
#     # the column keeps its existing schema name.
#     volume_avg_20d = serializers.DecimalField(
#         source="volume_average",
#         max_digits=20,
#         decimal_places=2,
#         read_only=True,
#     )

#     pressure_explanation = serializers.SerializerMethodField()

#     class Meta:
#         model = DailyAnalysis
#         fields = [
#             "id",
#             "company",
#             "company_symbol",
#             "company_name",
#             "date",
#             # VWAP
#             "vwap",
#             "vwap_30d",
#             # Price
#             "close_price",
#             "previous_close",
#             "daily_return_pct",
#             # Volume
#             "volume",
#             "volume_average",
#             "volume_avg_20d",
#             "volume_ratio",
#             "volume_anomaly",
#             "volume_baseline_sessions",
#             "has_sufficient_history",
#             # Pressure
#             "pressure",
#             "pressure_score",
#             "pressure_method",
#             "pressure_explanation",
#             # Other
#             "news_count",
#             "created_at",
#         ]
#         read_only_fields = ["id", "created_at"]

#     def get_pressure_explanation(self, obj):
#         """
#         Enough metadata for the frontend to explain the signal in words
#         rather than presenting an unexplained number.
#         """
#         missing = []
#         if obj.previous_close is None:
#             missing.append("previous_close")
#         if obj.vwap is None:
#             missing.append("vwap")
#         if obj.volume_ratio is None:
#             missing.append("volume_ratio")

#         return {
#             "method": obj.pressure_method or PRESSURE_METHOD,
#             "score": obj.pressure_score,
#             "score_range": [-100, 100],
#             "classification_band": 25,
#             "inputs": {
#                 "close": obj.close_price,
#                 "previous_close": obj.previous_close,
#                 "daily_vwap": obj.vwap,
#                 "volume_ratio": obj.volume_ratio,
#                 "volume_avg_20d": obj.volume_average,
#             },
#             "missing_inputs": missing,
#             "is_complete": not missing,
#             "baseline_sessions_required": BASELINE_SESSIONS,
#             "baseline_sessions_used": obj.volume_baseline_sessions,
#             "anomaly_threshold": VOLUME_ANOMALY_THRESHOLD,
#             "disclaimer": (
#                 "Derived from published OHLCV data only. This is a proxy for "
#                 "price/volume behaviour and is not evidence of order-book "
#                 "buying or selling interest. Broker net positions are "
#                 "reported separately from floorsheet data."
#             ),
#         }


# class BrokerActivitySerializer(serializers.Serializer):
#     """One combined row per broker: gross both sides plus net position."""

#     broker = serializers.CharField()

#     buy_quantity = serializers.IntegerField()
#     sell_quantity = serializers.IntegerField()
#     net_quantity = serializers.IntegerField()

#     buy_value = serializers.DecimalField(max_digits=30, decimal_places=4)
#     sell_value = serializers.DecimalField(max_digits=30, decimal_places=4)
#     net_value = serializers.DecimalField(max_digits=30, decimal_places=4)

#     total_quantity = serializers.IntegerField()
#     total_value = serializers.DecimalField(max_digits=30, decimal_places=4)

#     buy_trades = serializers.IntegerField()
#     sell_trades = serializers.IntegerField()
#     trades = serializers.IntegerField()
from rest_framework import serializers

from .models import DailyAnalysis
from .services.daily_metrics import (
    BASELINE_SESSIONS,
    PRESSURE_METHOD,
    VOLUME_ANOMALY_THRESHOLD,
)


class DailyAnalysisSerializer(serializers.ModelSerializer):
    """
    Stored per-trading-day analytical state.

    ``vwap`` is the DAILY VWAP (turnover / volume for that one day).
    ``vwap_30d`` is the separate rolling-window aggregate.  They are
    exposed under distinct names so a frontend can never accidentally
    render one as the other.
    """

    company_symbol = serializers.CharField(source="company.symbol", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)

    # Explicit alias so the API speaks the documented metric name while
    # the column keeps its existing schema name.
    volume_avg_20d = serializers.DecimalField(
        source="volume_average",
        max_digits=20,
        decimal_places=2,
        read_only=True,
    )

    pressure_explanation = serializers.SerializerMethodField()

    class Meta:
        model = DailyAnalysis
        fields = [
            "id",
            "company",
            "company_symbol",
            "company_name",
            "date",
            # VWAP
            "vwap",
            "vwap_30d",
            # Price
            "close_price",
            "previous_close",
            "daily_return_pct",
            # Volume
            "volume",
            "volume_average",
            "volume_avg_20d",
            "volume_ratio",
            "volume_anomaly",
            "volume_baseline_sessions",
            "has_sufficient_history",
            # Pressure
            "pressure",
            "pressure_score",
            "pressure_method",
            "pressure_explanation",
            # Other
            "news_count",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_pressure_explanation(self, obj):
        """
        Enough metadata for the frontend to explain the signal in words
        rather than presenting an unexplained number.
        """
        missing = []
        if obj.previous_close is None:
            missing.append("previous_close")
        if obj.vwap is None:
            missing.append("vwap")
        if obj.volume_ratio is None:
            missing.append("volume_ratio")

        return {
            "method": obj.pressure_method or PRESSURE_METHOD,
            "score": obj.pressure_score,
            "score_range": [-100, 100],
            "classification_band": 25,
            "inputs": {
                "close": obj.close_price,
                "previous_close": obj.previous_close,
                "daily_vwap": obj.vwap,
                "volume_ratio": obj.volume_ratio,
                "volume_avg_20d": obj.volume_average,
            },
            "missing_inputs": missing,
            "is_complete": not missing,
            "baseline_sessions_required": BASELINE_SESSIONS,
            "baseline_sessions_used": obj.volume_baseline_sessions,
            "anomaly_threshold": VOLUME_ANOMALY_THRESHOLD,
            "disclaimer": (
                "Derived from published OHLCV data only. This is a proxy for "
                "price/volume behaviour and is not evidence of order-book "
                "buying or selling interest. Broker net positions are "
                "reported separately from floorsheet data."
            ),
        }


class BrokerActivitySerializer(serializers.Serializer):
    """One combined row per broker: gross both sides plus net position."""

    broker = serializers.CharField()

    buy_quantity = serializers.IntegerField()
    sell_quantity = serializers.IntegerField()
    net_quantity = serializers.IntegerField()

    buy_value = serializers.DecimalField(max_digits=30, decimal_places=4)
    sell_value = serializers.DecimalField(max_digits=30, decimal_places=4)
    net_value = serializers.DecimalField(max_digits=30, decimal_places=4)

    total_quantity = serializers.IntegerField()
    total_value = serializers.DecimalField(max_digits=30, decimal_places=4)

    buy_trades = serializers.IntegerField()
    sell_trades = serializers.IntegerField()
    trades = serializers.IntegerField()
