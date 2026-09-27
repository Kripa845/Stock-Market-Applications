from rest_framework import serializers


class VolumeAnomalySerializer(serializers.Serializer):
    date = serializers.DateField()
    volume = serializers.IntegerField(min_value=0)
    rolling_mean = serializers.FloatField(allow_null=True)
    average_volume_20d = serializers.FloatField(allow_null=True)
    rvol = serializers.FloatField(allow_null=True)
    anomaly_flag = serializers.ChoiceField(choices=("Normal", "Anomaly"), allow_null=True)
    is_anomaly = serializers.BooleanField(allow_null=True)
    price_change_pct = serializers.FloatField(allow_null=True)


class VolumeAnomalyQuerySerializer(serializers.Serializer):
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    lookback = serializers.IntegerField(required=False, default=20, min_value=1, max_value=1000)
