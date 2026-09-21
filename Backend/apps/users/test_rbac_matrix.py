from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.crawler_runs.models import CrawlRun
from .models import CustomRole, RolePermissionConfig, User

FAST_HASH = override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])


def make_user(name, role=User.Role.VIEWER, perms=None):
    user = User.objects.create_user(username=name, email=f"{name}@example.com",
                                    password="Pw-12345!", role=role)
    if perms is not None:
        user.custom_role = CustomRole.objects.create(name=f"{name}-role", permissions=list(perms))
        user.save(update_fields=["custom_role"])
    return user


def as_user(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


def jwt_client(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return c


def call(client, method, url):
    fn = getattr(client, method)
    return fn(url) if method in ("get", "delete") else fn(url, {}, format="json")


CASES = [
    ("get", "/api/companies/", "view_companies"),
    ("post", "/api/companies/", "create_companies"),
    ("patch", "/api/companies/1/", "edit_companies"),
    ("delete", "/api/companies/1/", "delete_companies"),
    ("post", "/api/companies/1/toggle-track/", "manage_tracked_companies"),
    ("get", "/api/companies/1/prices/", "view_price_history"),
    ("get", "/api/companies/1/floorsheet/", "view_market_data"),
    ("get", "/api/market-data/", "view_price_history"),
    ("get", "/api/market-data/floorsheet/", "view_trading_volume"),
    ("get", "/api/news/", "view_news"),
    ("get", "/api/news/stats/", "view_news"),
    ("get", "/api/news/corrections/", "correct_categories"),
    ("post", "/api/news/1/recategorize/", "correct_categories"),
    ("post", "/api/news/1/trigger-categorize/", "categorize_news"),
    ("get", "/api/analysis/daily/", "view_analysis"),
    ("get", "/api/analysis/cross-company/", "view_analysis"),
    ("get", "/api/analysis/dashboard-summary/", "view_market_data"),
    ("get", "/api/crawler-runs/", "view_crawl_runs"),
    ("get", "/api/crawler-runs/1/", "view_crawl_runs"),
    ("post", "/api/crawler-runs/1/cancel/", "run_crawler"),
    ("post", "/api/crawler-runs/1/retry/", "retry_failed_crawl"),
    ("get", "/api/users/admin/users/", "view_users"),
    ("post", "/api/users/admin/users/", "create_users"),
    ("get", "/api/users/admin/roles/", "view_roles"),
    ("get", "/api/users/admin/role-permissions/", "view_roles"),
    ("patch", "/api/users/admin/roles/viewer/", "edit_roles"),
    ("get", "/api/users/admin/custom-roles/", "view_roles"),
    ("post", "/api/users/admin/custom-roles/", "create_roles"),
]


@FAST_HASH
class PermissionMatrixTests(TestCase):
    def test_401_403_and_success_for_every_endpoint(self):
        for i, (method, url, key) in enumerate(CASES):
            label = f"{method.upper()} {url} [{key}]"
            with self.subTest(label, case="anonymous"):
                self.assertEqual(call(APIClient(), method, url).status_code, 401)
            with self.subTest(label, case="authenticated, no permission"):
                nobody = make_user(f"none{i}", perms=[])
                self.assertEqual(call(as_user(nobody), method, url).status_code, 403)
            with self.subTest(label, case="only this permission"):
                ok = make_user(f"ok{i}", perms=[key])
                self.assertNotIn(call(as_user(ok), method, url).status_code, (401, 403))


@FAST_HASH
class EscalationTests(TestCase):
    def setUp(self):
        self.admin = make_user("boss", role=User.Role.ADMIN)
        self.victim = make_user("victim")

    def test_register_cannot_choose_role(self):
        r = APIClient().post("/api/users/register/", {
            "username": "eve", "email": "eve@example.com", "password": "Pw-12345!",
            "password_confirm": "Pw-12345!", "role": "admin"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(User.objects.get(username="eve").role, User.Role.VIEWER)

    def test_role_changer_cannot_mint_admin(self):
        mallory = make_user("mallory", perms=["view_users", "change_user_roles"])
        for target in (mallory, self.victim):
            r = as_user(mallory).patch(f"/api/users/admin/users/{target.pk}/", {"role": "admin"}, format="json")
            self.assertEqual(r.status_code, 403)
            target.refresh_from_db()
            self.assertNotEqual(target.role, User.Role.ADMIN)

    def test_create_users_cannot_create_admin(self):
        u = make_user("creator", perms=["create_users"])
        r = as_user(u).post("/api/users/admin/users/", {
            "username": "x", "email": "x@example.com", "password": "Pw-12345!",
            "password_confirm": "Pw-12345!", "role": "admin"}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertFalse(User.objects.filter(username="x").exists())

    def test_edit_users_cannot_take_over_admin(self):
        u = make_user("editor", perms=["edit_users"])
        r = as_user(u).patch(f"/api/users/admin/users/{self.admin.pk}/", {"password": "Hacked-123!"}, format="json")
        self.assertEqual(r.status_code, 403)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password("Pw-12345!"))

    def test_activate_users_cannot_deactivate_admin(self):
        u = make_user("toggler", perms=["activate_users"])
        r = as_user(u).patch(f"/api/users/admin/users/{self.admin.pk}/", {"is_active": False}, format="json")
        self.assertEqual(r.status_code, 403)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_cannot_grant_permissions_you_do_not_hold(self):
        RolePermissionConfig.objects.filter(role_key="analyst").update(
            permissions=["view_roles", "edit_roles"])
        analyst = make_user("ana", role=User.Role.ANALYST)
        c = as_user(analyst)
        r = c.patch("/api/users/admin/roles/viewer/", {"permissions": ["view_news", "delete_users"]}, format="json")
        self.assertEqual(r.status_code, 403)
        r = c.patch("/api/users/admin/roles/analyst/", {"permissions": ["view_roles", "edit_roles", "view_news"]}, format="json")
        self.assertEqual(r.status_code, 403)   # editing your own role

    def test_cannot_assign_yourself_a_stronger_custom_role(self):
        mallory = make_user("mal2", perms=["view_users", "change_user_roles"])
        strong = CustomRole.objects.create(name="strong", permissions=["delete_users"])
        r = as_user(mallory).patch(f"/api/users/admin/users/{mallory.pk}/", {"custom_role_id": strong.pk}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_crawl_logs_need_view_crawl_logs(self):
        run = CrawlRun.objects.create(crawl_type="news", target="t", logs="SECRET")
        r = as_user(make_user("a", perms=["view_crawl_runs"])).get(f"/api/crawler-runs/{run.pk}/")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("logs", r.data)
        r = as_user(make_user("b", perms=["view_crawl_runs", "view_crawl_logs"])).get(f"/api/crawler-runs/{run.pk}/")
        self.assertEqual(r.data["logs"], "SECRET")

    def test_permission_change_applies_on_next_request(self):
        viewer = make_user("v1")
        c = as_user(viewer)
        self.assertEqual(c.get("/api/news/").status_code, 200)
        perms = [p for p in RolePermissionConfig.objects.get(role_key="viewer").permissions if p != "view_news"]
        r = as_user(self.admin).patch("/api/users/admin/roles/viewer/", {"permissions": perms}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(c.get("/api/news/").status_code, 403)

    def test_demoted_admin_loses_access_immediately(self):
        adm = make_user("adm2", role=User.Role.ADMIN)
        c = jwt_client(adm)                       # real JWT: user is reloaded from the DB each request
        self.assertEqual(c.get("/api/users/admin/users/").status_code, 200)
        User.objects.filter(pk=adm.pk).update(role=User.Role.VIEWER)
        self.assertEqual(c.get("/api/users/admin/users/").status_code, 403)