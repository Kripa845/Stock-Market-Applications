from datetime import date, timedelta

from django.test import TestCase
from rest_framework.test import APIClient

from apps.companies.models import Company
from apps.market_data.models import DailyPrice
from apps.market_data.services.trading_days import is_trading_weekday
from apps.market_intelligence.models import CompanyTechnicalSnapshot
from apps.market_intelligence.services.sector_rotation import compute_sector_rotation_snapshots
from apps.market_intelligence.services.snapshots import compute_market_snapshots
from apps.market_intelligence.services.technicals import compute_company_technical_snapshots
from apps.users.models import User


class MarketIntelligenceApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(symbol="TEST", name="Test Co", sector="Banking")
        self.user = User.objects.create_user(
            username="market-intelligence-admin", email="mi-admin@example.test",
            password="unused-test-password", role=User.Role.ADMIN,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        first_day = date(2026, 9, 27)
        while not is_trading_weekday(first_day):
            first_day += timedelta(days=1)
        for offset in range(3):
            day = first_day + timedelta(days=offset)
            if not is_trading_weekday(day):
                continue
            close = 100 + offset
            DailyPrice.objects.create(
                company=self.company, source="crawled", date=day,
                open=close, high=close + 1, low=close - 1, close=close,
                volume=100 + offset, turnover=10000 + offset,
            )
        compute_market_snapshots()
        compute_company_technical_snapshots()
        compute_sector_rotation_snapshots()
        latest = DailyPrice.objects.order_by("-date").first()
        CompanyTechnicalSnapshot.objects.update_or_create(
            company=self.company, date=latest.date,
            defaults={"signal": "bullish", "signal_score": 50, "sufficient_history": True},
        )

    def test_breadth_heatmap_and_rankings_use_tracked_market_data(self):
        breadth = self.client.get("/api/market-intelligence/breadth/")
        heatmap = self.client.get("/api/market-intelligence/heatmap/?group=company")
        ranking = self.client.get("/api/market-intelligence/rankings/?metric=gainers")

        self.assertEqual(breadth.status_code, 200)
        self.assertEqual(breadth.data["universe_label"], "tracked stocks")
        self.assertEqual(heatmap.status_code, 200)
        self.assertEqual(heatmap.data["tiles"][0]["symbol"], "TEST")
        self.assertEqual(ranking.status_code, 200)
        self.assertEqual(ranking.data["results"][0]["symbol"], "TEST")

    def test_rotation_and_relative_strength_endpoints_are_registered(self):
        rotation = self.client.get("/api/market-intelligence/sectors/rotation/?period=1w")
        relative = self.client.get(
            "/api/market-intelligence/relative-strength/",
            {"company_id": self.company.pk, "period": "1w"},
        )

        self.assertEqual(rotation.status_code, 200)
        self.assertEqual(relative.status_code, 200)
        self.assertIn(relative.data["status"], ("ok", "insufficient_history"))

    def test_technical_endpoint_includes_disclaimer(self):
        response = self.client.get(f"/api/market-intelligence/companies/{self.company.pk}/technicals/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("not investment advice", response.data["disclaimer"])
