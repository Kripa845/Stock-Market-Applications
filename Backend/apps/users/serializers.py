from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
)

from .models import CustomRole, RolePermissionConfig


User = get_user_model()


# ============================================================
# PERMISSION DEFINITIONS
# ============================================================

ROLE_PERMISSIONS = {
    "users": [
        {"key": "view_users", "name": "View Users"},
        {"key": "create_users", "name": "Create Users"},
        {"key": "edit_users", "name": "Edit Users"},
        {"key": "delete_users", "name": "Delete Users"},
        {"key": "change_user_roles", "name": "Change User Roles"},
        {"key": "activate_users", "name": "Activate / Deactivate Users"},
    ],
    "companies": [
        {"key": "view_companies", "name": "View Companies"},
        {"key": "create_companies", "name": "Create Companies"},
        {"key": "edit_companies", "name": "Edit Companies"},
        {"key": "delete_companies", "name": "Delete Companies"},
        {"key": "manage_tracked_companies", "name": "Manage Tracked Companies"},
    ],
    "market_data": [
        {"key": "view_market_data", "name": "View Market Data"},
        {"key": "view_price_history", "name": "View Price History"},
        {"key": "view_trading_volume", "name": "View Trading Volume"},
        {"key": "view_vwap", "name": "View VWAP"},
        {"key": "view_buy_sell_pressure", "name": "View Buy/Sell Pressure"},
    ],
    "news": [
        {"key": "view_news", "name": "View News"},
        {"key": "categorize_news", "name": "Categorize News"},
        {"key": "correct_categories", "name": "Correct Categories"},
        {"key": "edit_news", "name": "Edit News"},
        {"key": "delete_news", "name": "Delete News"},
    ],
    "watchlist": [
        {"key": "view_watchlist", "name": "View Watchlist"},
        {"key": "add_watchlist", "name": "Add Companies"},
        {"key": "remove_watchlist", "name": "Remove Companies"},
        {"key": "edit_watchlist", "name": "Edit Watchlist"},
    ],
    "crawler": [
        {"key": "view_crawl_runs", "name": "View Crawl Runs"},
        {"key": "run_crawler", "name": "Run Crawler"},
        {"key": "view_crawl_logs", "name": "View Crawl Logs"},
        {"key": "retry_failed_crawl", "name": "Retry Failed Crawl"},
    ],
    "analysis": [
        {"key": "view_analysis", "name": "View Analysis"},
        {"key": "view_price_trends", "name": "View Price Trends"},
        {"key": "view_volume_trends", "name": "View Volume Trends"},
        {"key": "view_vwap_analysis", "name": "View VWAP Analysis"},
        {"key": "view_pressure_analysis", "name": "View Buy/Sell Pressure"},
    ],
    "reports": [
        {"key": "view_reports", "name": "View Reports"},
        {"key": "generate_reports", "name": "Generate Reports"},
        {"key": "export_reports", "name": "Export Reports"},
    ],
    "roles_permissions": [
        {"key": "view_roles", "name": "View Roles"},
        {"key": "create_roles", "name": "Create Roles"},
        {"key": "edit_roles", "name": "Edit Roles"},
        {"key": "delete_roles", "name": "Delete Roles"},
        {"key": "assign_roles", "name": "Assign Roles"},
    ],
}


VALID_PERMISSION_KEYS = {
    permission["key"]
    for permissions in ROLE_PERMISSIONS.values()
    for permission in permissions
}


# ============================================================
# JWT
# ============================================================

class CustomTokenObtainPairSerializer(
    TokenObtainPairSerializer
):
    def validate(self, attrs):
        data = super().validate(attrs)

        data["user"] = {
            "id": self.user.id,
            "username": self.user.username,
            "email": self.user.email,
            "first_name": self.user.first_name,
            "last_name": self.user.last_name,
            "role": self.user.role,
            "custom_role": (
                self.user.custom_role.name
                if self.user.custom_role
                else None
            ),
            "is_active": self.user.is_active,
        }

        return data


# ============================================================
# REGISTRATION
# ============================================================

class UserRegistrationSerializer(
    serializers.ModelSerializer
):
    password = serializers.CharField(
        write_only=True,
        min_length=6,
    )

    password_confirm = serializers.CharField(
        write_only=True,
    )

    role = serializers.ChoiceField(
        choices=User.Role.choices,
        default=User.Role.VIEWER,
        required=False,
    )

    class Meta:
        model = User

        fields = [
            "id",
            "username",
            "email",
            "password",
            "password_confirm",
            "first_name",
            "last_name",
            "role",
        ]

        read_only_fields = ["id"]

    def validate_email(self, value):
        return value.lower().strip()

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {
                    "password_confirm":
                    "Passwords do not match."
                }
            )

        return attrs

    def create(self, validated_data):
        validated_data.pop(
            "password_confirm"
        )

        password = validated_data.pop(
            "password"
        )

        user = User(
            **validated_data,
        )

        user.set_password(password)
        user.save()

        return user


# ============================================================
# ADMIN USER CREATE
# ============================================================

class AdminUserCreateSerializer(
    serializers.ModelSerializer
):
    password = serializers.CharField(
        write_only=True,
        min_length=6,
    )

    password_confirm = serializers.CharField(
        write_only=True,
    )

    role = serializers.ChoiceField(
        choices=User.Role.choices,
        default=User.Role.VIEWER,
    )

    custom_role_id = serializers.PrimaryKeyRelatedField(
        source="custom_role",
        queryset=CustomRole.objects.filter(
            is_active=True
        ),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = User

        fields = [
            "id",
            "username",
            "email",
            "password",
            "password_confirm",
            "first_name",
            "last_name",
            "role",
            "custom_role_id",
            "is_active",
        ]

        read_only_fields = ["id"]

    def validate_email(self, value):
        return value.lower().strip()

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {
                    "password_confirm":
                    "Passwords do not match."
                }
            )

        if attrs.get("custom_role") is not None:
            attrs["role"] = User.Role.VIEWER

        return attrs

    def create(self, validated_data):
        validated_data.pop(
            "password_confirm"
        )

        password = validated_data.pop(
            "password"
        )

        user = User(**validated_data)

        user.set_password(password)
        user.save()

        return user


# ============================================================
# USER OUTPUT
# ============================================================

class UserSerializer(
    serializers.ModelSerializer
):
    role_display = serializers.CharField(
        source="get_role_display",
        read_only=True,
    )

    custom_role_name = serializers.CharField(
        source="custom_role.name",
        read_only=True,
        allow_null=True,
    )

    effective_role = serializers.SerializerMethodField()

    class Meta:
        model = User

        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "role_display",
            "custom_role_id",
            "custom_role_name",
            "effective_role",
            "is_active",
            "date_joined",
            "last_login",
        ]

        read_only_fields = fields

    def get_effective_role(self, obj):
        return obj.get_effective_role_name()


# ============================================================
# ME
# ============================================================

class MeSerializer(
    serializers.ModelSerializer
):
    custom_role_name = serializers.CharField(
        source="custom_role.name",
        read_only=True,
        allow_null=True,
    )

    effective_role = serializers.SerializerMethodField()

    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User

        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "custom_role_id",
            "custom_role_name",
            "effective_role",
            "permissions",
            "is_active",
            "date_joined",
            "last_login",
        ]

        read_only_fields = [
            "id",
            "username",
            "role",
            "custom_role_id",
            "custom_role_name",
            "effective_role",
            "permissions",
            "is_active",
            "date_joined",
            "last_login",
        ]

    def get_effective_role(self, obj):
        return obj.get_effective_role_name()

    def get_permissions(self, obj):
        if obj.is_admin():
            return list(VALID_PERMISSION_KEYS)

        if obj.custom_role:
            if not obj.custom_role.is_active:
                return []

            return list(
                obj.custom_role.permissions or []
            )

        config = (
            RolePermissionConfig.objects
            .filter(
                role_key=obj.role,
                is_active=True,
            )
            .first()
        )

        if config:
            return list(config.permissions or [])

        return []


# ============================================================
# ADMIN USER UPDATE
# ============================================================

class AdminUserUpdateSerializer(
    serializers.ModelSerializer
):
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=False,
        min_length=6,
    )

    custom_role_id = serializers.PrimaryKeyRelatedField(
        source="custom_role",
        queryset=CustomRole.objects.filter(
            is_active=True
        ),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = User

        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "custom_role_id",
            "is_active",
            "password",
        ]

        read_only_fields = [
            "id",
            "username",
        ]

    def validate_email(self, value):
        return value.lower().strip()

    def validate(self, attrs):
        if attrs.get("custom_role") is not None:
            attrs["role"] = User.Role.VIEWER

        return attrs

    def update(self, instance, validated_data):
        password = validated_data.pop(
            "password",
            None,
        )

        if password:
            instance.set_password(password)

        return super().update(
            instance,
            validated_data,
        )


# ============================================================
# CUSTOM ROLE
# ============================================================

class CustomRoleSerializer(
    serializers.ModelSerializer
):
    user_count = serializers.IntegerField(
        source="users.count",
        read_only=True,
    )

    class Meta:
        model = CustomRole

        fields = [
            "id",
            "name",
            "description",
            "permissions",
            "is_active",
            "user_count",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "user_count",
            "created_at",
            "updated_at",
        ]

    def validate_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Role name is required."
            )

        return value

    def validate_permissions(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError(
                "Permissions must be a list."
            )

        invalid = [
            permission
            for permission in value
            if permission not in VALID_PERMISSION_KEYS
        ]

        if invalid:
            raise serializers.ValidationError(
                {
                    "invalid_permissions": invalid
                }
            )

        return list(dict.fromkeys(value))


class RolePermissionConfigSerializer(
    serializers.ModelSerializer
):
    permissions = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=False,
    )

    class Meta:
        model = RolePermissionConfig

        fields = [
            "id",
            "role_key",
            "name",
            "description",
            "permissions",
            "is_active",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "role_key",
            "created_at",
            "updated_at",
        ]

    def validate_permissions(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError(
                "Permissions must be a list."
            )

        invalid = [
            permission
            for permission in value
            if permission not in VALID_PERMISSION_KEYS
        ]

        if invalid:
            raise serializers.ValidationError(
                {
                    "invalid_permissions": invalid
                }
            )

        return list(dict.fromkeys(value))


class RolePermissionSerializer(
    serializers.Serializer
):
    key = serializers.CharField()
    name = serializers.CharField()
    allowed = serializers.BooleanField()


class RoleDefinitionSerializer(
    serializers.Serializer
):
    role = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField()
    permissions = RolePermissionSerializer(
        many=True
    )