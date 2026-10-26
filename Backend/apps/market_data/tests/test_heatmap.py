"""Tests for services.heatmap and GET /api/market/heatmap/ (tracked companies only)."""

from datetime import datetime
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.companies.models import Company, TrackedCompany
from apps.market_data.services import heatmap
from apps.market_data.services.live_prices import NPT
from apps.users.models import User

TODAY = datetime(2026, 10, 26, 12, 30, tzinfo=NPT)
YESTERDAY = datetime(2026, 10, 25, 14, 59, tzinfo=NPT)


class HeatmapTests(TestCase):

    def setUp(self):
        cache.clear()
        closed = mock.patch("apps.market_data.services.heatmap.is_market_open", return_value=False)
        closed.start()
        self.addCleanup(closed.stop)

    def company(self, symbol, sector, ltp=None, prev=None, when=TODAY, shares=1000, volume=500, turnover=None):
        company = Company.objects.create(
            symbol=symbol, name=f"{symbol} Ltd", sector=sector,
            ltp=None if ltp is None else Decimal(str(ltp)),
            previous_close=None if prev is None else Decimal(str(prev)),
            prices_updated_at=when if ltp is not None else None,
            session_volume=volume, session_turnover=turnover, listed_shares=shares,
        )
        TrackedCompany.objects.create(company=company, is_tracked=True)
        return company

    @staticmethod
    def sector(result, name):
        return next(s for s in result["sectors"] if s["name"] == name)

    @staticmethod
    def row(sector, symbol):
        return next(c for c in sector["companies"] if c["symbol"] == symbol)

    def test_company_change_and_market_cap(self):
        self.company("UP", "Banking", 110, 100, turnover=55000)
        bank = self.sector(heatmap.heatmap(), "Banking")
        up = self.row(bank, "UP")
        self.assertEqual(up["change_pct"], Decimal("10.00"))
        self.assertEqual(up["market_cap"], Decimal("110000.00"))
        self.assertEqual((up["volume"], up["turnover"]), (500, Decimal("55000")))

    def test_sector_change_is_cap_weighted(self):
        self.company("BIG", "Banking", 105, 100, shares=9000)     # +5% on 900,000 of cap
        self.company("SMALL", "Banking", 90, 100, shares=1000)    # -10% on 100,000 of cap
        bank = self.sector(heatmap.heatmap(), "Banking")
        # (945,000 + 90,000 - 1,000,000) / 1,000,000 = +3.5% (an equal-weight average would be -2.5%)
        self.assertEqual(bank["change_pct"], Decimal("3.50"))
        self.assertEqual(bank["market_cap"], Decimal("1035000.00"))
        self.assertEqual([c["symbol"] for c in bank["companies"]], ["BIG", "SMALL"])

    def test_untraded_company_is_grey_and_flat_in_its_sector(self):
        self.company("UP", "Hydro", 110, 100)
        self.company("IDLE", "Hydro", 50, 49, when=YESTERDAY, shares=2000)   # last traded yesterday
        self.company("NOVOL", "Hydro", 20, 19, volume=0)
        result = heatmap.heatmap()
        hydro = self.sector(result, "Hydro")
        for symbol in ("IDLE", "NOVOL"):
            row = self.row(hydro, symbol)
            self.assertIsNone(row["change_pct"])
            self.assertIsNone(row["volume"])
            self.assertFalse(row["traded"])
        self.assertEqual(self.row(hydro, "IDLE")["market_cap"], Decimal("100000.00"))
        # 110,000 vs 100,000 traded, plus 100,000 + 20,000 unchanged: 10,000 / 220,000
        self.assertEqual(hydro["change_pct"], Decimal("4.55"))
        self.assertEqual(result["session_date"], TODAY.date())

    def test_missing_previous_close_shares_or_price_never_divide_by_zero(self):
        self.company("NOPREV", "Finance", 100, None)
        self.company("ZERO", "Finance", 100, 0)
        self.company("NOSHARES", "Finance", 100, 90, shares=None)
        self.company("NOPRICE", "Finance")
        result = heatmap.heatmap()
        finance = self.sector(result, "Finance")
        self.assertIsNone(self.row(finance, "NOPREV")["change_pct"])
        self.assertIsNone(self.row(finance, "ZERO")["change_pct"])
        self.assertEqual(self.row(finance, "NOSHARES")["change_pct"], Decimal("11.11"))
        self.assertIsNone(self.row(finance, "NOSHARES")["market_cap"])
        self.assertIsNone(self.row(finance, "NOPRICE")["market_cap"])
        self.assertIsNone(finance["change_pct"])            # no traded member with a market cap
        self.assertEqual(result["missing_shares"], ["NOSHARES"])

    def test_no_live_prices_yet_returns_reason(self):
        self.company("NEW", "Banking")
        result = heatmap.heatmap()
        self.assertIsNone(result["last_updated"])
        self.assertIn("update_live_prices", result["action"])

    def test_endpoint_response(self):
        self.company("UP", "Banking", 110, 100)
        user = User.objects.create_user(username="heatmap-admin", email="heatmap@example.test",
                                        password="unused-test-password", role=User.Role.ADMIN)
        client = APIClient()
        client.force_authenticate(user)
        response = client.get("/api/market/heatmap/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["scope"], "tracked_companies")
        self.assertEqual(response.data["sectors"][0]["companies"][0]["symbol"], "UP")
        self.assertEqual(response.data["last_updated"], TODAY.isoformat())
