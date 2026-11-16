import importlib
from types import SimpleNamespace

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.users.api.serializers import (
    CustomRoleSerializer,
    PERMISSION_DEPENDENCIES,
    PERMISSION_REQUIRES_ANY,
    RolePermissionConfigSerializer,
    VALID_PERMISSION_KEYS,
    validate_permission_dependencies,
)
from apps.users.models import CustomRole, RolePermissionConfig, User
from apps.users.permissions import HasAppPermission, HasViewMethodPermissions


class _PermissionUser:
    is_authenticated = True

    def __init__(self, permissions):
        self.permissions = set(permissions)

    def has_app_permission(self, key):
        return key in self.permissions

    def has_any_app_permission(self, *keys):
        return bool(self.permissions.intersection(keys))


class PermissionCheckerTests(TestCase):
    def test_has_app_permission_supports_any_of_with_old_and_new_keys(self):
        view = SimpleNamespace(permission_keys=["view_market_data", "view_indices"])
        request = SimpleNamespace(user=_PermissionUser(["view_market_data"]))
        self.assertTrue(HasAppPermission().has_permission(request, view))
        request.user = _PermissionUser(["view_indices"])
        self.assertTrue(HasAppPermission().has_permission(request, view))
        request.user = _PermissionUser([])
        self.assertFalse(HasAppPermission().has_permission(request, view))

    def test_view_method_permissions_accept_nested_any_of(self):
        class View:
            def get_required_permissions(self, request):
                return ["view_users", ("view_market_data", "view_indices")]

        request = SimpleNamespace(user=_PermissionUser(["view_users", "view_indices"]))
        self.assertTrue(HasViewMethodPermissions().has_permission(request, View()))
        request.user = _PermissionUser(["view_users"])
        self.assertFalse(HasViewMethodPermissions().has_permission(request, View()))

    def test_new_view_dependency_broker_requires_any_and_old_chain_remains(self):
        self.assertIn("view_charts", PERMISSION_DEPENDENCIES["use_indicators"])
        self.assertEqual(PERMISSION_REQUIRES_ANY["export_broker_analysis"][0], "view_top_broker")
        self.assertTrue(validate_permission_dependencies(["use_indicators"]))
        self.assertTrue(validate_permission_dependencies(["export_broker_analysis"]))
        self.assertTrue(validate_permission_dependencies(["edit_users"]))
        self.assertEqual(
            validate_permission_dependencies(["view_users", "create_users", "edit_users"]),
            [],
        )

    def test_custom_role_serializer_rejects_action_without_view_permission(self):
        serializer = CustomRoleSerializer(data={
            "name": "Export only", "permissions": ["export_floorsheet"],
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn("permissions", serializer.errors)

    def test_catalogue_keeps_all_four_legacy_keys(self):
        self.assertTrue({
            "view_market_data", "view_price_history", "view_trading_volume", "view_analysis",
        }.issubset(VALID_PERMISSION_KEYS))

    def test_additive_data_migration_keeps_old_keys_and_is_idempotent(self):
        migration = importlib.import_module("apps.users.migrations.0013_add_page_permissions")
        original = ["view_market_data"]
        once = migration.additive_permissions(original)
        twice = migration.additive_permissions(once)
        self.assertIn("view_market_data", once)
        self.assertTrue({"view_dashboard", "view_indices", "view_calendar"}.issubset(once))
        self.assertEqual(once, twice)

    def test_seeded_roles_remain_editable_after_the_applied_legacy_migration(self):
        role = RolePermissionConfig.objects.get(role_key="viewer")
        permissions = [key for key in role.permissions if key != "view_news"]
        serializer = RolePermissionConfigSerializer(role, data={"permissions": permissions}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)


FAST_HASH = override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])


@FAST_HASH
class PagePermissionEndpointTests(TestCase):
    def _user(self, name, permissions):
        user = User.objects.create_user(
            username=name, email=f"{name}@example.com", password="Pw-12345!",
        )
        user.custom_role = CustomRole.objects.create(name=f"{name} role", permissions=permissions)
        user.save(update_fields=["custom_role"])
        return user

    def test_top_losers_permission_does_not_open_gainers_endpoint(self):
        user = self._user("losers_only", ["view_top_losers"])
        client = APIClient()
        client.force_authenticate(user)
        self.assertEqual(client.get("/api/companies/top-losers/").status_code, 200)
        self.assertEqual(client.get("/api/companies/top-gainers/").status_code, 403)

