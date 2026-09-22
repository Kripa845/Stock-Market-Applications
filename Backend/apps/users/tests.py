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
            # Valid chain: view_users → create_users → edit_users
            {"permissions": ["view_users", "create_users", "edit_users"]},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        self.client.force_authenticate(self.analyst)
        response = self.client.get("/api/users/me/permissions/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.data["permissions"]),
            {"view_users", "create_users", "edit_users"},
        )

    def test_user_update_is_forbidden_without_edit_permission(self):
        self.client.force_authenticate(self.analyst)
        response = self.client.patch(
            f"/api/users/admin/users/{self.admin.pk}/",
            {"first_name": "Changed"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)


# ======================================================
# COMPANY ACCESS TESTS
# ======================================================

from apps.companies.models import Company
from apps.users.company_access import has_company_access, get_accessible_company_ids
from apps.users.models import UserCompanyAccess


def _make_company(symbol, name="Test Co"):
    return Company.objects.create(symbol=symbol, name=name, sector="Banking", is_active=True)


def _give_access(user, company, status=1):
    obj, _ = UserCompanyAccess.objects.update_or_create(
        user=user, company=company, defaults={"status": status}
    )
    return obj


class UserCompanyAccessHelperTests(TestCase):
    """Unit tests for has_company_access() and get_accessible_company_ids()."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username="ca_admin", email="ca_admin@example.com", password="pw",
            role=User.Role.ADMIN,
        )
        self.analyst = User.objects.create_user(
            username="ca_analyst", email="ca_analyst@example.com", password="pw",
            role=User.Role.ANALYST,
        )
        self.viewer = User.objects.create_user(
            username="ca_viewer", email="ca_viewer@example.com", password="pw",
            role=User.Role.VIEWER,
        )
        self.abc = _make_company("ABCTEST", "ABC Bank")
        self.xyz = _make_company("XYZTEST", "XYZ Bank")

    # Test 1 — user with status=1 is allowed
    def test_has_access_when_status_is_1(self):
        _give_access(self.analyst, self.abc, status=1)
        self.assertTrue(has_company_access(self.analyst, self.abc.pk))

    # Test 2 — user with status=0 is denied
    def test_no_access_when_status_is_0(self):
        _give_access(self.analyst, self.abc, status=0)
        self.assertFalse(has_company_access(self.analyst, self.abc.pk))

    # Test 3 — user with no row is denied (default-deny)
    def test_no_access_when_no_row_exists(self):
        self.assertFalse(has_company_access(self.analyst, self.abc.pk))

    # Test 4 — admin always has access regardless
    def test_admin_always_has_access(self):
        # No UserCompanyAccess row for admin — still allowed
        self.assertTrue(has_company_access(self.admin, self.abc.pk))
        self.assertTrue(has_company_access(self.admin, self.xyz.pk))

    # Test 5 — mixed access: ABC=1, XYZ=0
    def test_mixed_access(self):
        _give_access(self.analyst, self.abc, status=1)
        _give_access(self.analyst, self.xyz, status=0)
        self.assertTrue(has_company_access(self.analyst, self.abc.pk))
        self.assertFalse(has_company_access(self.analyst, self.xyz.pk))

    # Test 6 — get_accessible_company_ids returns only status=1
    def test_get_accessible_ids_returns_only_granted(self):
        _give_access(self.analyst, self.abc, status=1)
        _give_access(self.analyst, self.xyz, status=0)
        ids = get_accessible_company_ids(self.analyst)
        self.assertIn(self.abc.pk, ids)
        self.assertNotIn(self.xyz.pk, ids)

    # Test 7 — admin returns None (no filtering needed)
    def test_get_accessible_ids_returns_none_for_admin(self):
        result = get_accessible_company_ids(self.admin)
        self.assertIsNone(result)

    # Test 8 & 9 — status change propagates
    def test_access_change_propagates(self):
        row = _give_access(self.analyst, self.abc, status=0)
        self.assertFalse(has_company_access(self.analyst, self.abc.pk))

        row.status = 1
        row.save()
        self.assertTrue(has_company_access(self.analyst, self.abc.pk))

        row.status = 0
        row.save()
        self.assertFalse(has_company_access(self.analyst, self.abc.pk))


class UserCompanyAccessAPITests(TestCase):
    """Integration tests for the Company Access API endpoints."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username="api_admin", email="api_admin@example.com", password="pw",
            role=User.Role.ADMIN,
        )
        self.analyst = User.objects.create_user(
            username="api_analyst", email="api_analyst@example.com", password="pw",
            role=User.Role.ANALYST,
        )
        RolePermissionConfig.objects.update_or_create(
            role_key=User.Role.ANALYST,
            defaults={
                "name": "Analyst",
                "permissions": [
                    "view_users", "edit_users",
                    "view_market_data", "view_price_history",
                ],
            },
        )
        self.abc = _make_company("ABCAPI", "ABC API Bank")
        self.xyz = _make_company("XYZAPI", "XYZ API Bank")
        self.client = APIClient()

    def test_admin_can_set_company_access(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            f"/api/users/admin/users/{self.analyst.pk}/company-access/",
            {
                "company_access": [
                    {"company_id": self.abc.pk, "status": 1},
                    {"company_id": self.xyz.pk, "status": 0},
                ]
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        rows = {r["company_id"]: r["status"] for r in resp.data["company_access"]}
        self.assertEqual(rows[self.abc.pk], 1)
        self.assertEqual(rows[self.xyz.pk], 0)

    def test_admin_can_read_company_access(self):
        _give_access(self.analyst, self.abc, status=1)
        self.client.force_authenticate(self.admin)
        resp = self.client.get(
            f"/api/users/admin/users/{self.analyst.pk}/company-access/"
        )
        self.assertEqual(resp.status_code, 200)
        ids = [r["company_id"] for r in resp.data["company_access"]]
        self.assertIn(self.abc.pk, ids)

    def test_non_admin_without_edit_users_cannot_set_access(self):
        # analyst has edit_users but no company-specific override — still needs edit_users
        viewer = User.objects.create_user(
            username="plain_viewer", email="pv@example.com", password="pw",
            role=User.Role.VIEWER,
        )
        self.client.force_authenticate(viewer)
        resp = self.client.post(
            f"/api/users/admin/users/{self.analyst.pk}/company-access/",
            {"company_access": [{"company_id": self.abc.pk, "status": 1}]},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_create_user_with_company_access(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            "/api/users/admin/users/",
            {
                "username": "newuser_ca",
                "email": "newuser_ca@example.com",
                "password": "Password123!",
                "password_confirm": "Password123!",
                "role": "viewer",
                "is_active": True,
                "company_access": [
                    {"company_id": self.abc.pk, "status": 1},
                ],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        new_user = User.objects.get(username="newuser_ca")
        self.assertTrue(has_company_access(new_user, self.abc.pk))
        self.assertFalse(has_company_access(new_user, self.xyz.pk))


class NewsCategorizationCompanyAccessTests(TestCase):
    """
    News viewing is unrestricted by company access.
    News categorization (POST /api/news/:id/recategorize/) requires status=1.
    """

    def setUp(self):
        from apps.news.models import NewsArticle, RawArticle
        from apps.crawler_runs.models import CrawlRun

        self.admin = User.objects.create_user(
            username="news_admin", email="news_admin@example.com", password="pw",
            role=User.Role.ADMIN,
        )
        self.analyst = User.objects.create_user(
            username="news_analyst", email="news_analyst@example.com", password="pw",
            role=User.Role.ANALYST,
        )
        RolePermissionConfig.objects.update_or_create(
            role_key=User.Role.ANALYST,
            defaults={
                "name": "Analyst",
                "permissions": ["view_news", "correct_categories"],
            },
        )
        self.abc = _make_company("NEWABCTEST", "News ABC Bank")

        crawl = CrawlRun.objects.create(
            crawl_type="news", source="test", target="test", status="success"
        )
        raw = RawArticle.objects.create(
            crawl_run=crawl, source="test", url="http://test.com/1",
            http_status=200, raw_html="<p>test</p>"
        )
        self.article = NewsArticle.objects.create(
            raw_article=raw, source="test", url="http://test.com/1",
            headline="Test Article", body="Test body.",
            content_hash="abc123test",
        )
        self.client = APIClient()

    def test_categorize_allowed_when_company_access_is_1(self):
        _give_access(self.analyst, self.abc, status=1)
        self.client.force_authenticate(self.analyst)
        resp = self.client.post(
            f"/api/news/{self.article.pk}/recategorize/",
            {
                "company_id": self.abc.pk,
                "action": "add",
                "confidence": 0.9,
                "reason": "Analyst test",
            },
            format="json",
        )
        # 200 = success, 404 would be ok too if corrections service is strict
        self.assertNotEqual(resp.status_code, 403)

    def test_categorize_denied_when_company_access_is_0(self):
        _give_access(self.analyst, self.abc, status=0)
        self.client.force_authenticate(self.analyst)
        resp = self.client.post(
            f"/api/news/{self.article.pk}/recategorize/",
            {
                "company_id": self.abc.pk,
                "action": "add",
                "confidence": 0.9,
                "reason": "Should be denied",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_categorize_denied_when_no_access_row(self):
        # No row at all → default deny
        self.client.force_authenticate(self.analyst)
        resp = self.client.post(
            f"/api/news/{self.article.pk}/recategorize/",
            {
                "company_id": self.abc.pk,
                "action": "add",
                "confidence": 0.9,
                "reason": "No row",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_always_categorize(self):
        # Admin bypasses company access — no row needed
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            f"/api/news/{self.article.pk}/recategorize/",
            {
                "company_id": self.abc.pk,
                "action": "add",
                "confidence": 0.9,
                "reason": "Admin override",
            },
            format="json",
        )
        self.assertNotEqual(resp.status_code, 403)
