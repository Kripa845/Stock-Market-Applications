from rest_framework import serializers
from .models import ArticleCompanyTag, CategorizationCorrection, NewsArticle, RawArticle
from apps.companies.models import Company


class ArticleCompanyTagSerializer(serializers.ModelSerializer):
    company_symbol = serializers.CharField(source="company.symbol", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)

    class Meta:
        model = ArticleCompanyTag
        fields = [
            "id",
            "article",
            "company",
            "company_symbol",
            "company_name",
            "confidence",
            "method",
            "evidence",
            "is_manual",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class CategorizationCorrectionSerializer(serializers.ModelSerializer):
    corrected_by_username = serializers.CharField(
        source="corrected_by.username",
        read_only=True,
    )
    company_symbol = serializers.CharField(
        source="company.symbol",
        read_only=True,
    )
    company_name = serializers.CharField(
        source="company.name",
        read_only=True,
    )
    article_headline = serializers.CharField(
        source="article.headline",
        read_only=True,
    )

    class Meta:
        model = CategorizationCorrection
        fields = [
            "id",
            "article",
            "article_headline",
            "company",
            "company_symbol",
            "company_name",
            "previous_confidence",
            "previous_method",
            "action",
            "reason",
            "corrected_by",
            "corrected_by_username",
            "corrected_at",
        ]
        read_only_fields = [
            "id",
            "corrected_by",
            "corrected_at",
        ]


class NewsArticleSerializer(serializers.ModelSerializer):
    company_tags = ArticleCompanyTagSerializer(many=True, read_only=True)
    corrections = CategorizationCorrectionSerializer(many=True, read_only=True)

    class Meta:
        model = NewsArticle
        fields = [
            "id",
            "source",
            "url",
            "headline",
            "body",
            "published_at",
            "language",
            "sentiment",
            "sentiment_label",
            "is_processed",
            "created_at",
            "updated_at",
            "company_tags",
            "corrections",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class RecategorizeRequestSerializer(serializers.Serializer):
    company_id = serializers.IntegerField(required=True)
    action = serializers.ChoiceField(
        choices=["add", "remove", "update"],
        default="update",
    )
    confidence = serializers.FloatField(
        required=False,
        default=1.0,
        min_value=0.0,
        max_value=1.0,
    )
    reason = serializers.CharField(
        required=True,
        allow_blank=False,
        max_length=500,
    )
