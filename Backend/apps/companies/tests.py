from datetime import date
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework import status

from apps.companies.models import Company
from apps.companies.serializers import CompanySerializer
from apps.market_data.models import DailyPrice
from apps.companies.views import (
    CompanyPricesAPIView,
    CompanyFloorsheetAPIView,
    CompanySectorsAPIView,
    CompanyListCreateAPIView,
    CompanyDetailUpdateDestroyAPIView,
)
from apps.users.models import UserCompanyAccess, RolePermissionConfig


class CrawledPricePresentationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(symbol="TEST", name="Test Company", sector="Other")

    def add_price(self, day, source, close):
        return DailyPrice.objects.create(
            company=self.company, source=source, date=day,
            open=Decimal(close), high=Decimal(close), low=Decimal(close),
            close=Decimal(close), volume=100, turnover=Decimal(close) * 100,
        )

    def test_company_summary_uses_crawled_price_by_default(self):
        self.add_price(date(2026, 9, 1), "crawled", "100")
        self.add_price(date(2026, 9, 2), "seeded", "999")

        data = CompanySerializer(self.company).data

        self.assertEqual(data["latest_price"], 100.0)
        self.assertEqual(data["latest_price_date"], "2026-09-01")

    def test_price_endpoint_defaults_to_crawled_and_accepts_explicit_source(self):
        self.add_price(date(2026, 9, 1), "crawled", "100")
        self.add_price(date(2026, 9, 2), "seeded", "999")
        user = get_user_model().objects.create_user(
            username="admin-test", email="admin-test@example.com", password="test-password", role="admin",
        )
        factory = APIRequestFactory()

        def get_prices(query_string=""):
            request = factory.get(f"/api/companies/{self.company.pk}/prices/?range=all{query_string}")
            force_authenticate(request, user=user)
            return CompanyPricesAPIView.as_view()(request, pk=self.company.pk).data["prices"]

        self.assertEqual([row["close"] for row in get_prices()], ["100.00"])
        self.assertEqual([row["close"] for row in get_prices("&source=seeded")], ["999.00"])

    @override_settings(DEBUG=False)
    def test_seed_command_refuses_to_run_without_force_outside_debug(self):
        with self.assertRaises(CommandError):
            call_command("seed_market_data")


class CompanyAccessControlTests(TestCase):
    """Test company-access enforcement across Companies API endpoints."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = get_user_model().objects.create_user(
            username="admin", email="admin@example.com", password="password", role=get_user_model().Role.ADMIN
        )
        self.analyst = get_user_model().objects.create_user(
            username="analyst", email="analyst@example.com", password="password", role=get_user_model().Role.ANALYST
        )
        self.viewer = get_user_model().objects.create_user(
            username="viewer", email="viewer@example.com", password="password", role=get_user_model().Role.VIEWER
        )

        # Create two companies
        self.company_a = Company.objects.create(symbol="COMPA", name="Company A", sector="Banking")
        self.company_b = Company.objects.create(symbol="COMPB", name="Company B", sector="Insurance")

        # Give analyst access to company_a only
        UserCompanyAccess.objects.create(
            user=self.analyst, company=self.company_a, status=1
        )
        # No access for viewer to any company (default deny)
        # Admin has access to both (by role)

    def _get_response(self, view_class, url, user, **kwargs):
        """Helper to call a view with a user."""
        request = self.factory.get(url)
        force_authenticate(request, user=user)
        view = view_class.as_view()
        return view(request, **kwargs)

    def test_list_companies_returns_only_accessible(self):
        """GET /api/companies/ should return only companies the user can access."""
        # Analyst should see only company_a
        resp_analyst = self._get_response(
            CompanyListCreateAPIView, "/api/companies/", self.analyst
        )
        self.assertEqual(resp_analyst.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp_analyst.data["results"]), 1)
        self.assertEqual(resp_analyst.data["results"][0]["symbol"], "COMPA")

        # Viewer should see none
        resp_viewer = self._get_response(
            CompanyListCreateAPIView, "/api/companies/", self.viewer
        )
        self.assertEqual(resp_viewer.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp_viewer.data["results"]), 0)

        # Admin should see both
        resp_admin = self._get_response(
            CompanyListCreateAPIView, "/api/companies/", self.admin
        )
        self.assertEqual(resp_admin.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp_admin.data["results"]), 2)

    def test_detail_company_requires_access(self):
        """GET /api/companies/{id}/ should return 403 for unauthorized users."""
        # Analyst can access company_a
        resp = self._get_response(
            CompanyDetailUpdateDestroyAPIView, f"/api/companies/{self.company_a.pk}/", self.analyst, pk=self.company_a.pk
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # Analyst cannot access company_b
        resp = self._get_response(
            CompanyDetailUpdateDestroyAPIView, f"/api/companies/{self.company_b.pk}/", self.analyst, pk=self.company_b.pk
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        # Viewer cannot access any company
        resp = self._get_response(
            CompanyDetailUpdateDestroyAPIView, f"/api/companies/{self.company_a.pk}/", self.viewer, pk=self.company_a.pk
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        # Admin can access both
        resp = self._get_response(
            CompanyDetailUpdateDestroyAPIView, f"/api/companies/{self.company_a.pk}/", self.admin, pk=self.company_a.pk
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        resp = self._get_response(
            CompanyDetailUpdateDestroyAPIView, f"/api/companies/{self.company_b.pk}/", self.admin, pk=self.company_b.pk
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_prices_require_permission_and_access(self):
        """GET /api/companies/{id}/prices/ needs view_price_history AND company access."""
        from apps.users.models import RolePermissionConfig

        # Ensure analyst has view_price_history permission
        RolePermissionConfig.objects.update_or_create(
            role_key=get_user_model().Role.ANALYST,
            defaults={"name": "Analyst", "permissions": ["view_price_history"]},
        )

        # Analyst with permission and access -> should succeed
        resp = self._get_response(
            CompanyPricesAPIView, f"/api/companies/{self.company_a.pk}/prices/", self.analyst, pk=self.company_a.pk
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # Analyst with permission but no access to company_b -> 403
        resp = self._get_response(
            CompanyPricesAPIView, f"/api/companies/{self.company_b.pk}/prices/", self.analyst, pk=self.company_b.pk
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        # Viewer without permission (even if they had access) -> 403
        # Viewer does not have view_price_history by default
        resp = self._get_response(
            CompanyPricesAPIView, f"/api/companies/{self.company_a.pk}/prices/", self.viewer, pk=self.company_a.pk
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        # Admin has permission and access -> succeed
        resp = self._get_response(
            CompanyPricesAPIView, f"/api/companies/{self.company_a.pk}/prices/", self.admin, pk=self.company_a.pk
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_floorsheet_require_permission_and_access(self):
        """GET /api/companies/{id}/floorsheet/ needs view_market_data AND company access."""
        from apps.users.models import RolePermissionConfig

        # Ensure analyst has view_market_data permission
        RolePermissionConfig.objects.update_or_create(
            role_key=get_user_model().Role.ANALYST,
            defaults={"name": "Analyst", "permissions": ["view_market_data"]},
        )

        # Analyst with permission and access -> succeed
        resp = self._get_response(
            CompanyFloorsheetAPIView, f"/api/companies/{self.company_a.pk}/floorsheet/", self.analyst, pk=self.company_a.pk
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # Analyst with permission but no access -> 403
        resp = self._get_response(
            CompanyFloorsheetAPIView, f"/api/companies/{self.company_b.pk}/floorsheet/", self.analyst, pk=self.company_b.pk
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        # Viewer without permission -> 403
        resp = self._get_response(
            CompanyFloorsheetAPIView, f"/api/companies/{self.company_a.pk}/floorsheet/", self.viewer, pk=self.company_a.pk
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        # Admin -> succeed
        resp = self._get_response(
            CompanyFloorsheetAPIView, f"/api/companies/{self.company_a.pk}/floorsheet/", self.admin, pk=self.company_a.pk
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_sectors_endpoint_excludes_inaccessible_companies(self):
        """GET /api/companies/sectors/ should only reflect sectors of accessible companies."""
        # We have company_a (Banking) accessible to analyst, company_b (Insurance) not accessible.
        # Expect analyst to see only Banking sector.
        resp = self._get_response(
            CompanySectorsAPIView, "/api/companies/sectors/", self.analyst
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, ["Banking"])

        # Viewer sees no sectors (no accessible companies)
        resp = self._get_response(
            CompanySectorsAPIView, "/api/companies/sectors/", self.viewer
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, [])

        # Admin sees both sectors
        resp = self._get_response(
            CompanySectorsAPIView, "/api/companies/sectors/", self.admin
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(set(resp.data), {"Banking", "Insurance"})
