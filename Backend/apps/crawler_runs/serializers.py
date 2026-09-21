from rest_framework import serializers

from .models import CrawlRun

ALLOWED_SPIDER_ARGS = {
    "max_pages",
    "max_articles",
    "mode",
    "sample_offsets",
}


class CrawlRunSerializer(serializers.ModelSerializer):
    duration_seconds = serializers.SerializerMethodField()
    triggered_by_name = serializers.SerializerMethodField()
    company_symbol = serializers.SerializerMethodField()

    class Meta:
        model = CrawlRun

        fields = [
            "id",
            "crawl_type",
            "target",
            "company",
            "company_symbol",
            "started_at",
            "completed_at",
            "created_at",
            "status",
            "sources",
            "articles_found",
            "articles_created",
            "articles_updated",
            "prices_found",
            "prices_created",
            "prices_updated",
            "floorsheet_found",
            "floorsheet_created",
            "floorsheet_updated",
            "errors",
            "logs",
            "task_id",
            "process_id",
            "triggered_by",
            "triggered_by_name",
            "duration_seconds",
        ]

        read_only_fields = [
            "id",
            "started_at",
            "completed_at",
            "created_at",
            "status",
            "articles_found",
            "articles_created",
            "articles_updated",
            "prices_found",
            "prices_created",
            "prices_updated",
            "floorsheet_found",
            "floorsheet_created",
            "floorsheet_updated",
            "errors",
            "logs",
            "task_id",
            "process_id",
            "triggered_by",
            "duration_seconds",
        ]

    def get_duration_seconds(self, obj):
        if not obj.started_at:
            return None

        end = obj.completed_at

        if not end:
            from django.utils import timezone
            end = timezone.now()

        return round(
            (end - obj.started_at).total_seconds(),
            1,
        )

    def get_triggered_by_name(self, obj):
        if not obj.triggered_by:
            return None

        return (
            obj.triggered_by.get_full_name()
            or obj.triggered_by.username
        )

    def get_company_symbol(self, obj):
        return obj.company.symbol if obj.company else None

    def to_representation(self, instance):
        data = super().to_representation(instance)

        request = self.context.get("request")
        user = getattr(request, "user", None)

        if not (
            user
            and user.is_authenticated
            and user.has_app_permission(
                "view_crawl_logs"
            )
        ):
            data.pop("logs", None)

        return data


class TriggerCrawlRequestSerializer(serializers.Serializer):
    crawl_type = serializers.ChoiceField(
        choices=[
            "news",
            "trading",
            "floorsheet",
            "all",
        ],
        default="all",
    )

    source = serializers.CharField(
        required=False,
        default="all",
    )

    company = serializers.IntegerField(
        required=False,
        allow_null=True,
        default=None,
    )

    spider_args = serializers.DictField(
        required=False,
        default=dict,
    )

    def validate_spider_args(self, value):
        unknown = sorted(set(value) - ALLOWED_SPIDER_ARGS)
        if unknown:
            raise serializers.ValidationError(f"Unsupported spider_args: {unknown}")
        return value
