from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.market_indices.models import IndexDaily, IndexIntradayPoint, MarketIndex
from apps.users.models import User


class IndexTechnicalsApiTests(TestCase):

    def setUp(self):
        cache.clear()
        call_command("seed_market_indices", stdout=mock.Mock())
        self.nepse = MarketIndex.objects.get(code="NEPSE")
        self.client = APIClient()
        self.client.force_authenticate(User.objects.create_user(
            username="a", email="a@example.test", password="unused-test-password", role=User.Role.ADMIN,
        ))

    def test_intraday_returns_recorded_points_as_bars(self):
        now = timezone.now()
        for minutes, value in ((10, "2600.50"), (5, "2601.25")):
            IndexIntradayPoint.objects.create(index=self.nepse, recorded_at=now - timedelta(minutes=minutes), value=Decimal(value))
        IndexIntradayPoint.objects.create(index=self.nepse, recorded_at=now - timedelta(days=30), value=Decimal("2500"))

        bars = self.client.get("/api/market-indices/intraday/", {"code": "nepse", "days": 1}).data["bars"]
        self.assertEqual([bar["close"] for bar in bars], [Decimal("2600.50"), Decimal("2601.25")])
        self.assertEqual(bars[0]["open"], bars[0]["high"])
        self.assertEqual(self.client.get("/api/market-indices/intraday/", {"code": "BANKING"}).data["bars"], [])
        self.assertEqual(self.client.get("/api/market-indices/intraday/", {"days": "x"}).status_code, 400)
        self.assertEqual(self.client.get("/api/market-indices/intraday/", {"code": "NOPE"}).status_code, 404)

    def test_support_resistance_from_stored_index_history(self):
        # 120 sessions oscillating between ~95 and ~105: repeated swing highs and lows.
        start = date(2026, 1, 1)
        for i in range(120):
            close = Decimal(100 + (5 if i % 20 == 10 else -5 if i % 20 == 0 else (i % 20 - 10) * 0.3))
            IndexDaily.objects.create(
                index=self.nepse, date=start + timedelta(days=i),
                open=close, high=close + 1, low=close - 1, close=close, turnover=0, volume=0, transactions=0,
            )
        data = self.client.get("/api/market-indices/support-resistance/", {"code": "NEPSE"}).data
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["sessions_used"], 120)
        kinds = {level["kind"] for level in data["levels"]}
        self.assertTrue(kinds <= {"support", "resistance"} and kinds)

        empty = self.client.get("/api/market-indices/support-resistance/", {"code": "BANKING"}).data
        self.assertEqual((empty["status"], empty["levels"]), ("insufficient_history", []))
