from django.test import TestCase
from rest_framework.test import APIClient

from .models import RolePermissionConfig, User


class RolePermissionAPITests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin", email="admin@example.com", password="password",
            role=User.Role.ADMIN,
        )
        self.analyst = User.objects.create_user(
            username="analyst", email="analyst@example.com", password="password",
            role=User.Role.ANALYST,
        )
        RolePermissionConfig.objects.update_or_create(
            role_key=User.Role.ANALYST,
            defaults={"name": "Analyst", "permissions": ["view_users"]},
        )
        self.client = APIClient()

    def test_admin_replaces_role_permissions_and_analyst_sees_them(self):
        self.client.force_authenticate(self.admin)
        response = self.client.put(
            "/api/users/admin/roles/analyst/",
            {"permissions": ["view_users", "edit_users"]},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        self.client.force_authenticate(self.analyst)
        response = self.client.get("/api/users/me/permissions/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data["permissions"]), {"view_users", "edit_users"})

    def test_user_update_is_forbidden_without_edit_permission(self):
        self.client.force_authenticate(self.analyst)
        response = self.client.patch(
            f"/api/users/admin/users/{self.admin.pk}/",
            {"first_name": "Changed"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
