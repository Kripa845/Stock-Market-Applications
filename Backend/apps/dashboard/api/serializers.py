from rest_framework import serializers

from rest_framework import serializers


class DashboardSummarySerializer(serializers.Serializer):
    tracked_companies = serializers.IntegerField()
    total_news = serializers.IntegerField()
    total_trading_days = serializers.IntegerField()
    total_floorsheet_transactions = serializers.IntegerField()

    market_volume = serializers.IntegerField()
    market_turnover = serializers.FloatField()

    positive_news = serializers.IntegerField()
    negative_news = serializers.IntegerField()
    neutral_news = serializers.IntegerField()