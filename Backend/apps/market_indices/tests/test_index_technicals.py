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

    def _history(self, sessions=40, volume_from=None):
        start = date(2026, 1, 1)
        for i in range(sessions):
            close = Decimal(100 + i)
            IndexDaily.objects.create(
                index=self.nepse, date=start + timedelta(days=i), open=close, high=close + 1, low=close - 1,
                close=close, volume=None if volume_from is None or i < volume_from else 1000 + i,
            )
        return start

    def indicators(self, specs, **params):
        import json
        return self.client.get("/api/market-indices/indicators/", {"code": "NEPSE", "specs": json.dumps(specs), **params})

    def test_indicators_from_stored_index_history(self):
        start = self._history()
        response = self.indicators([{"id": "sma", "params": {"period": 5}}, {"id": "rsi"}])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["index_code"], "NEPSE")
        self.assertEqual(len(response.data["dates"]), 40)
        sma = response.data["results"][0]["outputs"]["value"]
        self.assertEqual(sma[:4], [None] * 4)
        self.assertAlmostEqual(sma[4], 102.0)  # mean of closes 100..104
        self.assertIn("value", response.data["results"][1]["outputs"])

        # start_date cuts the output but not the warm-up.
        cut = self.indicators([{"id": "sma", "params": {"period": 5}}], start_date=(start + timedelta(days=10)).isoformat())
        self.assertEqual(cut.data["dates"][0], start + timedelta(days=10))
        self.assertAlmostEqual(cut.data["results"][0]["outputs"]["value"][0], 108.0)

    def test_index_volume_indicators_start_at_first_published_volume(self):
        self._history(volume_from=30)
        response = self.indicators([{"id": "obv"}, {"id": "volume"}])
        obv, volume = (r["outputs"] for r in response.data["results"])
        self.assertEqual(obv["value"][:30], [None] * 30)  # never counted as zero volume
        self.assertEqual(obv["value"][30], 0.0)
        self.assertEqual(volume["volume"][30], 1030.0)

        IndexDaily.objects.update(volume=None)
        self.assertIn("No volume", self.indicators([{"id": "obv"}]).data["results"][0]["error"])

    def test_index_indicators_that_need_a_stock_are_unavailable(self):
        self._history()
        results = self.indicators([{"id": "ratio"}, {"id": "tick_volume"}, {"id": "ema"}]).data["results"]
        self.assertIn("not available for an index", results[0]["error"])
        self.assertIn("not available for an index", results[1]["error"])
        self.assertNotIn("error", results[2])

    def test_index_indicator_errors(self):
        self.assertEqual(self.indicators([{"id": "nope"}]).status_code, 400)
        self.assertEqual(self.client.get("/api/market-indices/indicators/", {"specs": "x"}).status_code, 400)
        self.assertEqual(self.indicators([{"id": "rsi"}], code="NOPE").status_code, 404)
