from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
)
from rest_framework import serializers

from apps.users.models import UserCompanyAccess
from apps.users.models import CustomRole, RolePermissionConfig


User = get_user_model()


# ============================================================
# PERMISSION DEFINITIONS
# ============================================================
# Every key listed here must be enforced somewhere in the backend;
# a checkbox that changes nothing misleads whoever edits a role.

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
    ],
    "news": [
        {"key": "view_news", "name": "View News"},
        {"key": "categorize_news", "name": "Categorize News"},
        {"key": "correct_categories", "name": "Correct Categories"},
    ],
    "watchlist": [
        {"key": "view_watchlist", "name": "View Watchlist"},
        {"key": "add_watchlist", "name": "Add Companies"},
        {"key": "remove_watchlist", "name": "Remove Companies"},
    ],
    "crawler": [
        {"key": "view_crawl_runs", "name": "View Crawl Runs"},
        {"key": "run_crawler", "name": "Run Crawler"},
        {"key": "view_crawl_logs", "name": "View Crawl Logs"},
        {"key": "retry_failed_crawl", "name": "Retry Failed Crawl"},
    ],
    "analysis": [
        {"key": "view_analysis", "name": "View Analysis"},
    ],
    "reports": [
        {"key": "view_reports", "name": "View Reports"},
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


LEGACY_PERMISSION_KEYS = frozenset({
    "view_market_data", "view_price_history", "view_trading_volume", "view_analysis",
})

# Migration 0012 may already have stored these abandoned-approach keys. Keep them
# round-trippable so editing a role does not fail or silently erase old JSON values;
# they are intentionally absent from the UI catalogue until their endpoints exist.
PRESERVED_UNLISTED_PERMISSION_KEYS = frozenset({
    "export_dividends", "create_events", "edit_events", "delete_events",
    "save_layouts", "export_stock_comparison", "export_watchlist_comparison",
    "create_announcements", "edit_announcements", "delete_announcements",
    "export_financial_reports", "upload_financial_reports",
})

# Page-level keys are exposed only where the backend has a corresponding protected
# endpoint. Features without a backend endpoint (for example event editing or layout
# persistence) intentionally have no checkbox yet.
PAGE_PERMISSION_GROUPS = [
    {"key": "dashboard", "name": "Dashboard", "permissions": [{"key": "view_dashboard", "name": "View Dashboard"}]},
    {"key": "market_overview", "name": "Market Overview", "permissions": [
        {"key": "view_top_gainer", "name": "View Top Gainer"},
        {"key": "view_top_losers", "name": "View Top Losers"},
        {"key": "view_top_turnover", "name": "View Top Turnover"},
        {"key": "view_top_volume", "name": "View Top Volume"},
        {"key": "view_top_transactions", "name": "View Top Transactions"},
    ]},
    {"key": "indices", "name": "Indices", "permissions": [{"key": "view_indices", "name": "View Indices"}]},
    {"key": "dividends", "name": "Proposed Dividend", "permissions": [{"key": "view_dividends", "name": "View Dividends"}]},
    {"key": "calendar", "name": "Market Calendar", "permissions": [{"key": "view_calendar", "name": "View Calendar"}]},
    {"key": "summary", "name": "Summary", "permissions": [
        {"key": "view_nepse_day_by_day", "name": "View NEPSE Day by Day"},
        {"key": "view_nepse_month_by_month", "name": "View NEPSE Month by Month"},
        {"key": "view_weekday_summary", "name": "View Weekday Summary"},
        {"key": "view_floorsheet_summary", "name": "View Floorsheet Summary"},
    ]},
    {"key": "latest_reports", "name": "Latest Report", "permissions": [{"key": "view_latest_reports", "name": "View Latest Reports"}]},
    {"key": "charts", "name": "Technical Charts", "permissions": [
        {"key": "view_charts", "name": "View Charts"},
        {"key": "use_indicators", "name": "Use Indicators"},
    ]},
    {"key": "floorsheet", "name": "Floorsheet", "permissions": [
        {"key": "view_floorsheet", "name": "View Floorsheet"},
        {"key": "export_floorsheet", "name": "Export Floorsheet"},
    ]},
    {"key": "broker_analysis", "name": "Broker Analysis", "permissions": [
        {"key": "view_top_broker", "name": "View Top Broker"},
        {"key": "view_broker_explorer", "name": "View Broker Explorer"},
        {"key": "view_broker_list", "name": "View Broker List"},
        {"key": "view_broker_accumulation", "name": "View Broker Accumulation"},
        {"key": "view_broker_acc_dist_chart", "name": "View Broker Acc/Dist Chart"},
        {"key": "export_broker_analysis", "name": "Export Broker Analysis"},
    ], "requires_any": {"export_broker_analysis": [
        "view_top_broker", "view_broker_explorer", "view_broker_list",
        "view_broker_accumulation", "view_broker_acc_dist_chart",
    ]}},
    {"key": "live_trading", "name": "Live Trading", "permissions": [{"key": "view_live_trading", "name": "View Live Trading"}]},
    {"key": "stock_comparison", "name": "Stock Comparison", "permissions": [{"key": "view_stock_comparison", "name": "View Stock Comparison"}]},
    {"key": "watchlist_comparison", "name": "Watchlist Comparison", "permissions": [{"key": "view_watchlist_comparison", "name": "View Watchlist Comparison"}]},
    {"key": "announcements", "name": "Announcements", "permissions": [{"key": "view_announcements", "name": "View Announcements"}]},
    {"key": "stock_details", "name": "Stock Details", "permissions": [{"key": "view_stock_details", "name": "View Stock Details"}]},
    {"key": "financial_reports", "name": "Financial Reports", "permissions": [{"key": "view_financial_reports", "name": "View Financial Reports"}]},
]

LEGACY_GROUP_NAMES = {
    "market_data": "Market Data",
    "analysis": "Analysis",
    "companies": "Companies",
    "watchlist": "Watchlist",
    "news": "News Feed",
    "crawler": "Crawl Management",
    "reports": "Reports",
    "users": "User Management",
    "roles_permissions": "Roles & Permissions",
}
SIDEBAR_GROUP_ORDER = ["companies", "watchlist", "news", "crawler", "reports", "users", "roles_permissions"]
PAGE_DEPENDENCIES = {
    permission["key"]: [group["permissions"][0]["key"]]
    for group in PAGE_PERMISSION_GROUPS
    if group["key"] not in {"market_overview", "summary", "broker_analysis"}
    for permission in group["permissions"][1:]
}
PERMISSION_REQUIRES_ANY = {
    key: list(options)
    for group in PAGE_PERMISSION_GROUPS
    for key, options in group.get("requires_any", {}).items()
}

VALID_PERMISSION_KEYS = {
    permission["key"]
    for permissions in ROLE_PERMISSIONS.values()
    for permission in permissions
} | {
    permission["key"]
    for group in PAGE_PERMISSION_GROUPS
    for permission in group["permissions"]
} | PRESERVED_UNLISTED_PERMISSION_KEYS

PRESERVED_UNLISTED_DEPENDENCIES = {
    "export_dividends": ["view_dividends"],
    "create_events": ["view_calendar"],
    "edit_events": ["view_calendar"],
    "delete_events": ["view_calendar"],
    "save_layouts": ["view_charts"],
    "export_stock_comparison": ["view_stock_comparison"],
    "export_watchlist_comparison": ["view_watchlist_comparison"],
    "create_announcements": ["view_announcements"],
    "edit_announcements": ["view_announcements"],
    "delete_announcements": ["view_announcements"],
    "export_financial_reports": ["view_financial_reports"],
    "upload_financial_reports": ["view_financial_reports"],
}


# ============================================================
# PERMISSION DEPENDENCY RULES
# ============================================================
# Derived directly from ROLE_PERMISSIONS so the single source
# of truth is always the group definition above.
#
# Within every group, permission[i] requires ALL permissions
# at positions 0…i-1.  Topics are independent of each other.
#
# Structure: { "permission_key": ["required_key_1", ...], ... }

def _build_dependencies() -> dict:
    deps: dict = {}
    for group in ROLE_PERMISSIONS.values():
        keys = [p["key"] for p in group]
        for idx, key in enumerate(keys):
            # permissions[0] has no prerequisites
            deps[key] = keys[:idx]   # empty list for idx == 0
    return deps


PERMISSION_DEPENDENCIES: dict = _build_dependencies()
PERMISSION_DEPENDENCIES.update(PAGE_DEPENDENCIES)
PERMISSION_DEPENDENCIES.update(PRESERVED_UNLISTED_DEPENDENCIES)


def validate_permission_dependencies(
    permissions: list,
) -> list:
    """
    Validate that every permission in *permissions* has all of its
    required prerequisites also present in *permissions*.

    Returns a list of human-readable error messages.
    An empty list means the combination is valid.

    The dependency chain is derived from the position of each
    permission inside its group in ROLE_PERMISSIONS:

        group.permissions[i] requires group.permissions[0..i-1]

    Topics are independent — a permission in "users" has NO
    dependency on any permission in "companies", etc.

    Examples (users group):
        ["view_users"]                         → valid
        ["view_users", "create_users"]         → valid
        ["edit_users"]                         → INVALID (needs view + create)
        ["view_users", "edit_users"]           → INVALID (needs create)
        ["view_users", "create_users",
         "delete_users"]                       → INVALID (needs edit)
    """
    perm_set = set(permissions)
    errors = []

    # Build a reverse map: key → human-readable name
    key_to_name: dict = {
        p["key"]: p["name"]
        for group in ROLE_PERMISSIONS.values()
        for p in group
    }

    for perm_key in permissions:
        required = PERMISSION_DEPENDENCIES.get(perm_key, [])
        missing = [r for r in required if r not in perm_set]
        if missing:
            perm_name = key_to_name.get(perm_key, perm_key)
            missing_names = ", ".join(
                key_to_name.get(m, m) for m in missing
            )
            errors.append(
                f"{perm_name} requires: {missing_names}."
            )

        alternatives = PERMISSION_REQUIRES_ANY.get(perm_key, [])
        if alternatives and not perm_set.intersection(alternatives):
            errors.append(
                f"{perm_key} requires at least one of: {', '.join(alternatives)}."
            )

    return errors


def permission_definitions_payload() -> dict:
    """Groups displayed by sidebar page, plus the retained legacy permissions."""
    sidebar_groups = []
    for key in SIDEBAR_GROUP_ORDER:
        if key not in ROLE_PERMISSIONS:
            continue
        sidebar_groups.append({
            "key": key,
            "name": LEGACY_GROUP_NAMES.get(key, key.replace("_", " ").title()),
            "permissions": ROLE_PERMISSIONS[key],
        })
    return {
        "groups": PAGE_PERMISSION_GROUPS + sidebar_groups,
        "legacy_groups": [{
            "key": "legacy_broad",
            "name": "Legacy broad permissions",
            "permissions": [
                {"key": key, "name": ROLE_PERMISSIONS[group][idx]["name"], "description": description}
                for group, idx, key, description in [
                    ("market_data", 0, "view_market_data", "Dashboard, market overview, indices, dividends, calendar, summaries, latest reports, live trading and stock details."),
                    ("market_data", 1, "view_price_history", "Technical charts, company price history and intraday candles."),
                    ("market_data", 2, "view_trading_volume", "Floorsheet, floorsheet summaries and company volume analysis."),
                    ("analysis", 0, "view_analysis", "Broker analysis, comparisons, technical analysis, and related company and market analysis."),
                ]
            ],
        }],
        "dependencies": PERMISSION_DEPENDENCIES,
        "requires_any": PERMISSION_REQUIRES_ANY,
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

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "password", "password_confirm",
                  "first_name", "last_name"]          # no "role": self-registration is always Viewer
        read_only_fields = ["id"]

    def validate_email(self, value):
        return value.lower().strip()

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        # Apply settings.AUTH_PASSWORD_VALIDATORS, which min_length alone does not.
        candidate = User(username=attrs.get("username"), email=attrs.get("email"))
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        password = validated_data.pop("password")
        user = User(**validated_data, role=User.Role.VIEWER)
        user.set_password(password)
        user.save()
        return user


class UserCompanyAccessItemSerializer(serializers.Serializer):
    company_id = serializers.IntegerField(min_value=1)
    status = serializers.IntegerField(min_value=0, max_value=1)


class UserCompanyAccessListSerializer(serializers.Serializer):
    company_access = UserCompanyAccessItemSerializer(
        many=True,
        allow_empty=True,
    )
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

    company_access = UserCompanyAccessItemSerializer(
        many=True,
        required=False,
        allow_empty=True,
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
            "company_access",
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
        company_access = validated_data.pop(
            "company_access",
            []
        )

        validated_data.pop(
            "password_confirm"
        )

        password = validated_data.pop(
            "password"
        )

        user = User(**validated_data)

        user.set_password(password)
        user.save()

        if company_access:
            from apps.users.company_access import set_company_access

            set_company_access(
                user,
                company_access
            )

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

    def get_effective_role(self, obj) -> str:
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

    def get_effective_role(self, obj) -> str:
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

        # Dependency validation — prerequisites must also be present
        dep_errors = validate_permission_dependencies(value)
        if dep_errors:
            raise serializers.ValidationError(dep_errors)

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

        # Dependency validation — prerequisites must also be present
        dep_errors = validate_permission_dependencies(value)
        if dep_errors:
            raise serializers.ValidationError(dep_errors)

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
    
    

