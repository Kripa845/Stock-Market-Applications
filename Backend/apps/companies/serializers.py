from rest_framework import serializers
from .models import Company

from .utils import normalize_symbol


class CompanySerializer(serializers.ModelSerializer):

    class Meta:
        model = Company
        fields = [
            "id",
            "symbol",
            "name",
            "sector",
            "aliases",
            "is_active",
        ]
        
        read_only_fields = [
            "id",
            "created_by",
            "created_at",
            "updated_at",
        ]
    def validate_symbol(self, value):
        return normalize_symbol(value)

    def create(self, validated_data):

        request = self.context.get("request")

        if request and request.user.is_authenticated:
            validated_data["created_by"] = request.user

        return super().create(validated_data)