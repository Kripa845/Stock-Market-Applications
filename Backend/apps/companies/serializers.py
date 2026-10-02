from rest_framework import serializers
from .models import Company, TrackedCompany
from .utils import normalize_symbol


def _get_prices(obj, n=None):
    """
    Return daily prices for a company, using the prefetched cache
    (_prices_cache) when available to avoid extra queries on list
    endpoints.  Falls back to a direct queryset for detail endpoints
    that don't carry the prefetch.

    Prices are already ordered -date (most recent first) in both paths.
    """
    if hasattr(obj, "_prices_cache"):
        cache = obj._prices_cache  # already ordered -date
        return cache[:n] if n is not None else cache
    qs = obj.dailyprice_set.filter(source="crawled").order_by("-date")
    return list(qs[:n]) if n is not None else list(qs)


class CompanySerializer(serializers.ModelSerializer):
    is_tracked = serializers.SerializerMethodField()
    latest_price = serializers.SerializerMethodField()
    latest_price_date = serializers.SerializerMethodField()
    price_change = serializers.SerializerMethodField()
    price_change_percent = serializers.SerializerMethodField()
    volume_24h = serializers.SerializerMethodField()
    turnover_24h = serializers.SerializerMethodField()
    high_24h = serializers.SerializerMethodField()
    low_24h = serializers.SerializerMethodField()
    news_count = serializers.SerializerMethodField()
    sentiment_score = serializers.SerializerMethodField()
    sparkline = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = [
            "id",
            "symbol",
            "name",
            "logo_url",
            "sector",
            "aliases",
            "is_active",
            "is_tracked",
            "latest_price",
            "latest_price_date",
            "price_change",
            "price_change_percent",
            "volume_24h",
            "turnover_24h",
            "high_24h",
            "low_24h",
            "news_count",
            "sentiment_score",
            "sparkline",
        ]
        read_only_fields = ["id"]

    def get_is_tracked(self, obj):
        if hasattr(obj, "tracking"):
            return obj.tracking.is_tracked
        return True

    def get_latest_price(self, obj):
        prices = _get_prices(obj, 1)
        return float(prices[0].close) if prices else 0.0

    def get_latest_price_date(self, obj):
        prices = _get_prices(obj, 1)
        return prices[0].date.isoformat() if prices else None

    def get_price_change(self, obj):
        prices = _get_prices(obj, 2)
        if len(prices) >= 2:
            return round(float(prices[0].close - prices[1].close), 2)
        return 0.0

    def get_price_change_percent(self, obj):
        prices = _get_prices(obj, 2)
        if len(prices) >= 2 and float(prices[1].close) > 0:
            diff = float(prices[0].close - prices[1].close)
            return round((diff / float(prices[1].close)) * 100, 2)
        return 0.0

    def get_volume_24h(self, obj):
        prices = _get_prices(obj, 1)
        return int(prices[0].volume) if prices else 0

    def get_turnover_24h(self, obj):
        prices = _get_prices(obj, 1)
        return float(prices[0].turnover) if prices else 0.0

    def get_high_24h(self, obj):
        prices = _get_prices(obj, 1)
        return float(prices[0].high) if prices else 0.0

    def get_low_24h(self, obj):
        prices = _get_prices(obj, 1)
        return float(prices[0].low) if prices else 0.0

    def get_news_count(self, obj):
        return obj.article_tags.count()

    def get_sentiment_score(self, obj):
        tags = obj.article_tags.select_related("article")
        sentiments = [
            tag.article.sentiment
            for tag in tags
            if tag.article.sentiment is not None
        ]
        if sentiments:
            return round(sum(sentiments) / len(sentiments), 2)
        return 0.0

    def get_sparkline(self, obj):
        # Last 10 prices in chronological order (oldest → newest)
        prices = _get_prices(obj, 10)
        return [float(p.close) for p in reversed(prices)]

    def validate_symbol(self, value):
        return normalize_symbol(value)

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["created_by"] = request.user
        company = super().create(validated_data)
        TrackedCompany.objects.get_or_create(company=company, defaults={"is_tracked": True})
        return company
