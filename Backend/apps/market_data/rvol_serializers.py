from rest_framework import serializers
from .models import DailyPrice


class RvolQuerySerializer(serializers.Serializer):
    source = serializers.ChoiceField(required=False, default="crawled", choices=tuple(choice[0] for choice in DailyPrice.SOURCE_CHOICES))
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    ma_length = serializers.IntegerField(required=False, default=21, min_value=1, max_value=1000)
    ma_type = serializers.ChoiceField(required=False, default="SMA", choices=("SMA", "EMA"))
    threshold = serializers.FloatField(required=False, default=2.0, min_value=0.01, max_value=1000)

    def validate(self, attrs):
        if attrs.get("start_date") and attrs.get("end_date") and attrs["start_date"] > attrs["end_date"]:
            raise serializers.ValidationError({"start_date": "Must be on or before end_date."})
        return attrs


class RvolPointSerializer(serializers.Serializer):
    date = serializers.DateField()
    open = serializers.FloatField(allow_null=True)
    high = serializers.FloatField(allow_null=True)
    low = serializers.FloatField(allow_null=True)
    close = serializers.FloatField(allow_null=True)
    volume = serializers.IntegerField(min_value=0)
    rolling_avg = serializers.FloatField(allow_null=True)
    rolling_std = serializers.FloatField(allow_null=True)
    rvol = serializers.FloatField(allow_null=True)
    is_above_threshold = serializers.BooleanField()
