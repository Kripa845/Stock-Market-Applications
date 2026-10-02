from datetime import date
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.companies.models import Company
from apps.companies.serializers import CompanySerializer
from apps.market_data.models import DailyPrice
from apps.companies.views import CompanyPricesAPIView


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
