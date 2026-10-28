from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.companies.models import Company, TrackedCompany
from apps.floorsheet.models import Broker, FloorsheetTransaction
from apps.market_calendar.services.market_day import market_day
from apps.market_data.models import DailyPrice
from apps.market_indices.models import MarketIndex
from apps.users.models import CustomRole, UserCompanyAccess

D = Decimal
PREVIOUS, SESSION, HOLIDAY = date(2026, 10, 26), date(2026, 10, 27), date(2026, 10, 28)
DAY_URL = "/api/market-calendar/day/"


def _price(company, day, close, volume, pct=None, transactions=None):
    DailyPrice.objects.create(
        company=company, date=day, source="crawled", open=D(close), high=D(close), low=D(close), close=D(close),
        volume=volume, turnover=D(close) * volume, source_change_pct=pct, transactions=transactions,
    )


def _trade(company, buyer, seller, quantity, n):
    FloorsheetTransaction.objects.create(
        company=company, date=SESSION, transaction_id=f"{company.symbol}-{n}", buyer_broker=buyer,
        seller_broker=seller, quantity=quantity, rate=D("100"), amount=D("100") * quantity,
    )


class MarketDayTests(TestCase):
    def setUp(self):
        self.companies = {}
        for symbol, prev, close, volume, transactions in [
            ("NABIL", "500", "510", 1000, 12),      # +2%
            ("ADBL", "300", "297", 5000, 40),       # -1%
            ("HDL", "100", "100", 200, None),       # unchanged, trade count not derived yet
        ]:
            company = Company.objects.create(symbol=symbol, name=f"{symbol} Ltd", sector="Banking")
            TrackedCompany.objects.create(company=company, is_tracked=True)
            _price(company, PREVIOUS, prev, volume)
            _price(company, SESSION, close, volume, transactions=transactions)
            self.companies[symbol] = company
        untracked = Company.objects.create(symbol="OTHER", name="Other", sector="Banking")
        _price(untracked, PREVIOUS, "10", 1)
        _price(untracked, SESSION, "20", 1)       # +100%, must never rank
        Broker.objects.create(broker_code="58", broker_no=58, name="Naasa Securities")
        _trade(self.companies["NABIL"], "58", "34", 600, 1)
        _trade(self.companies["NABIL"], "34", "58", 400, 2)
        _trade(self.companies["ADBL"], "34", "42", 5000, 3)

    def test_session_sections(self):
        data = market_day(SESSION)
        self.assertTrue(data["available"])
        self.assertEqual(
            {k: data["summary"][k] for k in ("tracked_count", "advanced", "declined", "unchanged", "previous_trade_date")},
            {"tracked_count": 3, "advanced": 1, "declined": 1, "unchanged": 1, "previous_trade_date": PREVIOUS},
        )
        self.assertEqual([r["symbol"] for r in data["gainers"]], ["NABIL"])
        self.assertEqual([r["symbol"] for r in data["losers"]], ["ADBL"])
        self.assertEqual(data["gainers"][0]["change_pct"], D("2.0000"))
        self.assertEqual([r["symbol"] for r in data["top_volume"]], ["ADBL", "NABIL", "HDL"])
        # HDL has no derived trade count: left out, never ranked as 0.
        self.assertEqual([r["symbol"] for r in data["top_transactions"]], ["ADBL", "NABIL"])

    def test_brokers_ranked_by_buy_plus_sell(self):
        brokers = market_day(SESSION)["brokers"]
        self.assertEqual(brokers["transaction_count"], 3)
        # 34: bought 400 NABIL + 5000 ADBL, sold 600 NABIL = 6000 shares x 100; 42: sold 5000; 58: 1000.
        self.assertEqual([r["broker"] for r in brokers["rows"]], ["34", "42", "58"])
        top = brokers["rows"][0]
        self.assertEqual((top["total_value"], top["trades"]), (D("600000"), 3))
        self.assertEqual(brokers["rows"][1]["name"], "Broker 42")      # not in the directory
        self.assertEqual(brokers["rows"][2]["name"], "Naasa Securities")

    def test_a_day_without_prices_never_falls_back_to_the_previous_session(self):
        data = market_day(HOLIDAY)
        self.assertFalse(data["available"])
        self.assertNotIn("gainers", data)

    def test_session_without_floorsheet(self):
        data = market_day(PREVIOUS)
        self.assertTrue(data["available"])
        self.assertEqual(data["top_transactions"], [])
        self.assertIsNone(data["brokers"])
        self.assertEqual(data["floorsheet_from"], SESSION)

    def test_company_ids_narrow_every_section(self):
        data = market_day(SESSION, company_ids=[self.companies["ADBL"].id])
        self.assertEqual(data["summary"]["tracked_count"], 1)
        self.assertEqual((data["gainers"], [r["symbol"] for r in data["losers"]]), ([], ["ADBL"]))
        self.assertEqual([r["broker"] for r in data["brokers"]["rows"]], ["34", "42"])

    def test_brokers_can_be_left_out(self):
        self.assertNotIn("brokers", market_day(SESSION, include_brokers=False))


def _user(name, permissions=None, role="viewer"):
    user = get_user_model().objects.create_user(username=name, email=f"{name}@example.com", password="pw", role=role)
    if permissions is not None:
        user.custom_role = CustomRole.objects.create(name=f"{name} role", permissions=permissions)
        user.save(update_fields=["custom_role"])
    return user


@patch("apps.market_calendar.services.calendar.timezone.localdate", return_value=HOLIDAY)
class MarketDayApiTests(MarketDayTests.__base__):
    def setUp(self):
        MarketDayTests.setUp(self)
        MarketIndex.objects.create(code="NEPSE", name="NEPSE Index", kind="main")

    def _get(self, user, **params):
        client = APIClient()
        client.force_authenticate(user)
        return client.get(DAY_URL, {"date": str(SESSION), **params}).json()

    def test_only_with_include_market(self, _today):
        admin = _user("md-admin", role="admin")
        self.assertNotIn("market", self._get(admin))
        market = self._get(admin, include="market")["market"]
        self.assertEqual(market["gainers"][0]["symbol"], "NABIL")
        self.assertEqual(market["gainers"][0]["change_pct"], 2.0)       # numbers, as the movers endpoints send
        self.assertIn("brokers", market)

    def test_company_access_and_broker_permission(self, _today):
        viewer = _user("md-viewer", permissions=["view_market_data"])
        UserCompanyAccess.objects.create(user=viewer, company=self.companies["NABIL"], status=1)
        market = self._get(viewer, include="market")["market"]
        self.assertEqual(market["summary"]["tracked_count"], 1)
        self.assertEqual([r["symbol"] for r in market["top_volume"]], ["NABIL"])
        self.assertNotIn("brokers", market)               # no view_analysis

        analyst = _user("md-analyst", permissions=["view_market_data", "view_analysis"])
        UserCompanyAccess.objects.create(user=analyst, company=self.companies["NABIL"], status=1)
        brokers = self._get(analyst, include="market")["market"]["brokers"]
        self.assertEqual(brokers["transaction_count"], 2)     # NABIL's trades only
