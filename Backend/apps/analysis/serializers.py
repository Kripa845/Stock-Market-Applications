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


class VolumeAnomalySerializer(serializers.ModelSerializer):
    class Meta:
        from .models import VolumeAnomaly
        model = VolumeAnomaly
        fields = ("date", "volume", "rolling_mean", "rolling_std", "z_score", "pct_of_avg", "is_anomaly", "insufficient_data", "reason")
        read_only_fields = fields


class NewsPriceCorrelationSerializer(serializers.Serializer):
    company_id = serializers.IntegerField()
    method = serializers.CharField()
    confidence_floor = serializers.FloatField()
    min_n_for_reliable = serializers.IntegerField()
    lags_days = serializers.ListField(child=serializers.IntegerField())
    window_start = serializers.CharField(allow_null=True, required=False)
    window_end = serializers.CharField(allow_null=True, required=False)
    caveat = serializers.CharField()
    by_lag = serializers.DictField()
    computed_at = serializers.DateTimeField(required=False)


class ForwardCorrelationMetricSerializer(serializers.Serializer):
    coefficient = serializers.FloatField(allow_null=True)
    observations = serializers.IntegerField(min_value=0)


class NewsSentimentItemSerializer(serializers.Serializer):
    headline = serializers.CharField(allow_blank=True)
    category = serializers.CharField(allow_null=True, allow_blank=True)
    sentiment_score = serializers.FloatField(allow_null=True)


class NewsSentimentDailySerializer(serializers.Serializer):
    date = serializers.DateField()
    article_count = serializers.IntegerField(min_value=0)
    avg_sentiment = serializers.FloatField(allow_null=True)
    news_items = NewsSentimentItemSerializer(many=True)
    positive_count = serializers.IntegerField(min_value=0)
    negative_count = serializers.IntegerField(min_value=0)
    t1_date = serializers.DateField(allow_null=True)
    t2_date = serializers.DateField(allow_null=True)
    return_t1_pct = serializers.FloatField(allow_null=True)
    return_t2_pct = serializers.FloatField(allow_null=True)
    volume_change_t1_pct = serializers.FloatField(allow_null=True)
    volume_change_t2_pct = serializers.FloatField(allow_null=True)


class NewsSentimentCorrelationSummarySerializer(serializers.Serializer):
    observations = serializers.IntegerField(min_value=0)
    sentiment_return_t1 = ForwardCorrelationMetricSerializer()
    sentiment_return_t2 = ForwardCorrelationMetricSerializer()
    sentiment_volume_change_t1 = ForwardCorrelationMetricSerializer()
    sentiment_volume_change_t2 = ForwardCorrelationMetricSerializer()


class NewsSentimentForwardResponseSerializer(serializers.Serializer):
    company_id = serializers.IntegerField()
    symbol = serializers.CharField()
    daily_data = NewsSentimentDailySerializer(many=True)
    correlation_summary = NewsSentimentCorrelationSummarySerializer()
    disclaimer = serializers.CharField()


class NewsSentimentCorrelationQuerySerializer(serializers.Serializer):
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)


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
