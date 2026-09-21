"""
Tests for permission dependency validation — Users topic (Section 1.2 of spec).

The dependency chain for the Users group is:
    view_users
        ↓
    create_users
        ↓
    edit_users
        ↓
    delete_users
        ↓
    change_user_roles
        ↓
    activate_users

Every test exercises the actual backend validation path so that a direct API
call (bypassing the React UI) is also correctly rejected or accepted.

Coverage:
  - Valid combinations:  empty, view only, view+create, full chain
  - Invalid combinations: single action without prereqs, skipped step, etc.
  - Direct API call with invalid body → 400
  - Direct API call with valid body   → 200
  - Built-in role endpoint (PATCH /admin/roles/<key>/)
  - Custom role create (POST /admin/custom-roles/)
  - Custom role update (PATCH /admin/custom-roles/<id>/)
"""

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import CustomRole, RolePermissionConfig, User
from apps.users.serializers import validate_permission_dependencies


# ──────────────────────────────────────────────────────────────────────────────
# Unit tests for validate_permission_dependencies()
# ──────────────────────────────────────────────────────────────────────────────

class ValidatePermissionDependenciesUnitTests(TestCase):
    """
    Test the pure validation function directly.
    These run without any HTTP layer and are fast.
    """

    # ── Valid combinations ──────────────────────────────────────────────────

    def test_empty_list_is_valid(self):
        errors = validate_permission_dependencies([])
        self.assertEqual(errors, [])

    def test_view_users_alone_is_valid(self):
        errors = validate_permission_dependencies(["view_users"])
        self.assertEqual(errors, [])

    def test_view_and_create_users_is_valid(self):
        errors = validate_permission_dependencies(["view_users", "create_users"])
        self.assertEqual(errors, [])

    def test_view_create_edit_is_valid(self):
        errors = validate_permission_dependencies(
            ["view_users", "create_users", "edit_users"]
        )
        self.assertEqual(errors, [])

    def test_view_create_edit_delete_is_valid(self):
        errors = validate_permission_dependencies(
            ["view_users", "create_users", "edit_users", "delete_users"]
        )
        self.assertEqual(errors, [])

    def test_full_users_chain_is_valid(self):
        errors = validate_permission_dependencies(
            [
                "view_users",
                "create_users",
                "edit_users",
                "delete_users",
                "change_user_roles",
                "activate_users",
            ]
        )
        self.assertEqual(errors, [])

    def test_unrelated_groups_are_independent(self):
        """Selecting view_companies alone is valid — no cross-group dependency."""
        errors = validate_permission_dependencies(["view_companies"])
        self.assertEqual(errors, [])

    def test_two_independent_groups_both_valid(self):
        """view_users + view_news — no dependency between topics."""
        errors = validate_permission_dependencies(["view_users", "view_news"])
        self.assertEqual(errors, [])

    def test_full_chain_plus_another_group_is_valid(self):
        errors = validate_permission_dependencies(
            [
                "view_users",
                "create_users",
                "edit_users",
                "view_news",
                "categorize_news",
            ]
        )
        self.assertEqual(errors, [])

    # ── Invalid combinations ────────────────────────────────────────────────

    def test_edit_users_alone_is_invalid(self):
        errors = validate_permission_dependencies(["edit_users"])
        self.assertGreater(len(errors), 0)
        combined = " ".join(errors)
        self.assertIn("Edit Users", combined)

    def test_create_users_without_view_is_invalid(self):
        errors = validate_permission_dependencies(["create_users"])
        self.assertGreater(len(errors), 0)
        combined = " ".join(errors)
        self.assertIn("Create Users", combined)

    def test_delete_users_without_edit_is_invalid(self):
        errors = validate_permission_dependencies(
            ["view_users", "create_users", "delete_users"]
        )
        # delete_users requires edit_users which is absent
        self.assertGreater(len(errors), 0)
        combined = " ".join(errors)
        self.assertIn("Delete Users", combined)

    def test_view_and_edit_without_create_is_invalid(self):
        errors = validate_permission_dependencies(["view_users", "edit_users"])
        self.assertGreater(len(errors), 0)
        combined = " ".join(errors)
        self.assertIn("Edit Users", combined)
        self.assertIn("Create Users", combined)

    def test_change_user_roles_without_chain_is_invalid(self):
        errors = validate_permission_dependencies(["change_user_roles"])
        self.assertGreater(len(errors), 0)

    def test_activate_users_requires_full_preceding_chain(self):
        # Missing change_user_roles
        errors = validate_permission_dependencies(
            [
                "view_users",
                "create_users",
                "edit_users",
                "delete_users",
                "activate_users",
            ]
        )
        self.assertGreater(len(errors), 0)
        combined = " ".join(errors)
        self.assertIn("Activate", combined)

    def test_error_message_names_the_prerequisite(self):
        """Error message must name the missing prerequisite, not just the broken perm."""
        errors = validate_permission_dependencies(["edit_users"])
        combined = " ".join(errors)
        # Should mention the missing prerequisites by name
        self.assertIn("View Users", combined)
        self.assertIn("Create Users", combined)

    def test_order_does_not_matter_for_validity(self):
        """The validator must work regardless of the order keys are listed."""
        errors = validate_permission_dependencies(
            ["edit_users", "create_users", "view_users"]
        )
        self.assertEqual(errors, [])


# ──────────────────────────────────────────────────────────────────────────────
# Integration tests — built-in role endpoint
# PATCH/PUT /api/users/admin/roles/<role_key>/
# ──────────────────────────────────────────────────────────────────────────────

class BuiltInRoleDependencyAPITests(TestCase):
    """
    Verify the built-in role endpoint rejects invalid dependency combinations
    and accepts valid ones via direct HTTP calls.
    """

    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@dep-test.com",
            password="Pw-12345!",
            role=User.Role.ADMIN,
        )
        RolePermissionConfig.objects.update_or_create(
            role_key=User.Role.ANALYST,
            defaults={"name": "Analyst", "permissions": ["view_users"]},
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.url = "/api/users/admin/roles/analyst/"

    # ── Valid requests ──────────────────────────────────────────────────────

    def test_empty_permissions_accepted(self):
        r = self.client.patch(self.url, {"permissions": []}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_view_users_only_accepted(self):
        r = self.client.patch(self.url, {"permissions": ["view_users"]}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("view_users", r.data["permissions"])

    def test_view_and_create_accepted(self):
        r = self.client.patch(
            self.url,
            {"permissions": ["view_users", "create_users"]},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_full_chain_accepted(self):
        r = self.client.patch(
            self.url,
            {
                "permissions": [
                    "view_users",
                    "create_users",
                    "edit_users",
                    "delete_users",
                    "change_user_roles",
                    "activate_users",
                ]
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    # ── Invalid requests — must be rejected with 400 ────────────────────────

    def test_edit_users_without_prerequisites_rejected(self):
        r = self.client.patch(
            self.url,
            {"permissions": ["edit_users"]},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("permissions", r.data)

    def test_view_and_edit_without_create_rejected(self):
        r = self.client.patch(
            self.url,
            {"permissions": ["view_users", "edit_users"]},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_view_create_delete_without_edit_rejected(self):
        r = self.client.patch(
            self.url,
            {"permissions": ["view_users", "create_users", "delete_users"]},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_users_alone_rejected(self):
        r = self.client.patch(
            self.url,
            {"permissions": ["delete_users"]},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_user_roles_without_chain_rejected(self):
        r = self.client.patch(
            self.url,
            {"permissions": ["view_users", "create_users", "change_user_roles"]},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_activate_users_without_change_user_roles_rejected(self):
        r = self.client.patch(
            self.url,
            {
                "permissions": [
                    "view_users",
                    "create_users",
                    "edit_users",
                    "delete_users",
                    "activate_users",
                ]
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_error_response_contains_human_readable_message(self):
        r = self.client.patch(
            self.url,
            {"permissions": ["edit_users"]},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        # permissions field must contain at least one human-readable string
        self.assertIn("permissions", r.data)
        messages = r.data["permissions"]
        self.assertIsInstance(messages, list)
        self.assertGreater(len(messages), 0)
        # Must name the broken permission
        combined = " ".join(str(m) for m in messages)
        self.assertIn("Edit Users", combined)

    def test_saved_permissions_persist_and_user_sees_them(self):
        """End-to-end: admin saves valid permissions; user's /me/permissions/ updates."""
        analyst = User.objects.create_user(
            username="analyst_dep",
            email="analyst_dep@test.com",
            password="Pw-12345!",
            role=User.Role.ANALYST,
        )
        valid_perms = ["view_users", "create_users", "edit_users"]
        self.client.patch(self.url, {"permissions": valid_perms}, format="json")

        analyst_client = APIClient()
        analyst_client.force_authenticate(analyst)
        r = analyst_client.get("/api/users/me/permissions/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(set(r.data["permissions"]), set(valid_perms))


# ──────────────────────────────────────────────────────────────────────────────
# Integration tests — custom role create/update endpoints
# POST /api/users/admin/custom-roles/
# PATCH /api/users/admin/custom-roles/<id>/
# ──────────────────────────────────────────────────────────────────────────────

class CustomRoleDependencyAPITests(TestCase):
    """
    Verify custom role create/update endpoints enforce the same dependency rules.
    A malicious client bypassing the React UI must still get a 400.
    """

    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin_cr",
            email="admin_cr@dep-test.com",
            password="Pw-12345!",
            role=User.Role.ADMIN,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.create_url = "/api/users/admin/custom-roles/"

    def _create_role(self, permissions):
        return self.client.post(
            self.create_url,
            {"name": "TestRole", "permissions": permissions},
            format="json",
        )

    # ── Create ──────────────────────────────────────────────────────────────

    def test_create_with_valid_chain_succeeds(self):
        r = self._create_role(["view_users", "create_users", "edit_users"])
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

    def test_create_with_edit_only_rejected(self):
        r = self._create_role(["edit_users"])
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_with_view_and_edit_skipping_create_rejected(self):
        r = self._create_role(["view_users", "edit_users"])
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_with_empty_permissions_succeeds(self):
        r = self.client.post(
            self.create_url,
            {"name": "EmptyRole", "permissions": []},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

    # ── Update ──────────────────────────────────────────────────────────────

    def test_patch_with_invalid_chain_rejected(self):
        role = CustomRole.objects.create(
            name="UpdRole",
            permissions=["view_users"],
        )
        url = f"/api/users/admin/custom-roles/{role.id}/"
        r = self.client.patch(
            url,
            {"permissions": ["edit_users"]},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_with_valid_chain_succeeds(self):
        role = CustomRole.objects.create(
            name="UpdRole2",
            permissions=["view_users"],
        )
        url = f"/api/users/admin/custom-roles/{role.id}/"
        r = self.client.patch(
            url,
            {"permissions": ["view_users", "create_users", "edit_users"]},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(
            set(r.data["permissions"]),
            {"view_users", "create_users", "edit_users"},
        )

    # ── Security: bypass attempt ─────────────────────────────────────────────

    def test_direct_api_call_with_isolated_privileged_permission_rejected(self):
        """
        Simulate a malicious user bypassing the React UI and directly calling
        the API with an invalid permission combination.  Backend MUST reject it.
        """
        r = self._create_role(["delete_users"])
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST,
                         msg="Backend must reject isolated delete_users without prerequisites")

    def test_direct_api_call_with_valid_combination_accepted(self):
        """
        Simulate a legitimate direct API call with a valid combination.
        Backend must accept it.
        """
        r = self._create_role(
            ["view_users", "create_users", "edit_users", "delete_users"]
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED,
                         msg="Backend must accept a valid dependency chain")

    def test_anonymous_cannot_call_role_endpoints(self):
        """Unauthenticated request must return 401."""
        anon = APIClient()
        r = anon.post(
            self.create_url,
            {"name": "Anon", "permissions": ["view_users"]},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_viewer_cannot_modify_roles(self):
        """User without edit_roles permission must get 403."""
        viewer = User.objects.create_user(
            username="plain_viewer",
            email="viewer@dep-test.com",
            password="Pw-12345!",
            role=User.Role.VIEWER,
        )
        viewer_client = APIClient()
        viewer_client.force_authenticate(viewer)
        r = viewer_client.post(
            self.create_url,
            {"name": "Attempt", "permissions": ["view_users"]},
            format="json",
        )
        self.assertIn(r.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED])
