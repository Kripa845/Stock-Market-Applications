"""
Market-wide accumulation / distribution over a small hand-calculated floorsheet.

Sample (stock: buyer <- seller, qty @ rate):

    2026-09-14  AAA: 10 <- 20     100 @ 500
    2026-09-15  AAA: 10 <- 30     200 @ 510
                AAA: 30 <- 10      50 @ 520
                AAA: " 20 " <- 30  10 @ 505   (padded broker, cleaned to "20")
                BBB: 40 <- 20     300 @ 100
                BBB: 20 <- 40     100 @ 110

1D (2026-09-15 only):

    AAA/10  buy 200 / 102,000, sell  50 / 26,000   -> net +150,  +76,000, avg buy 510.00
    AAA/20  buy  10 /   5,050                       -> net  +10,   +5,050, avg buy 505.00
    AAA/30  buy  50 /  26,000, sell 210 / 107,050  -> net -160,  -81,050, avg sell 509.76
    BBB/40  buy 300 /  30,000, sell 100 / 11,000   -> net +200,  +19,000, avg buy 100.00
    BBB/20  buy 100 /  11,000, sell 300 / 30,000   -> net -200,  -19,000, avg sell 100.00

AAA has 200,000 public shares (latest non-null CompanyDaily row); BBB has
none, so it falls back to its 500,000 listed shares.
"""

from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.analysis.services.acc_dist import build_acc_dist
from apps.companies.models import Company
from apps.floorsheet.models import FloorsheetTransaction
from apps.market_indices.models import CompanyDaily
from apps.users.models import User

D1 = date(2026, 9, 14)
D2 = date(2026, 9, 15)


class AccDistTestBase(TestCase):

    def setUp(self):
        self.aaa = Company.objects.create(symbol="AAA", name="Triple A", sector="Banking", listed_shares=1_000_000)
        self.bbb = Company.objects.create(symbol="BBB", name="Triple B", sector="Hydro", listed_shares=500_000)
        self.counter = 0
        for company, when, buyer, seller, quantity, rate in (
            (self.aaa, D1, "10", "20", 100, 500),
            (self.aaa, D2, "10", "30", 200, 510),
            (self.aaa, D2, "30", "10", 50, 520),
            (self.aaa, D2, " 20 ", "30", 10, 505),
            (self.bbb, D2, "40", "20", 300, 100),
            (self.bbb, D2, "20", "40", 100, 110),
        ):
            self.tx(company, when, buyer, seller, quantity, rate)

        daily = dict(symbol="AAA", security_id=1, sector="Banking", instrument_type="Equity", close=500, listed_shares=1_000_000)
        CompanyDaily.objects.create(date=D1, public_shares=100_000, **daily)
        CompanyDaily.objects.create(date=D2, public_shares=200_000, **{**daily, "close": 510})
        # A newer row without public shares must not hide the last known count.
        CompanyDaily.objects.create(date=date(2026, 9, 16), public_shares=None, **{**daily, "close": 515})

    def tx(self, company, when, buyer, seller, quantity, rate):
        self.counter += 1
        return FloorsheetTransaction.objects.create(
            company=company, date=when, transaction_id=f"AD{self.counter:04d}",
            buyer_broker=buyer, seller_broker=seller, quantity=quantity, rate=Decimal(str(rate)),
        )

    @staticmethod
    def pairs(rows):
        return [(row["symbol"], row["broker"]) for row in rows]


class BuildAccDistTests(AccDistTestBase):

    def test_one_day_pairs_ranked_by_net_amount(self):
        result = build_acc_dist("1D")

        self.assertEqual((result["sessions"], result["start_date"], result["end_date"]), (1, D2, D2))
        self.assertEqual(self.pairs(result["accumulation"]), [("AAA", "10"), ("BBB", "40"), ("AAA", "20")])
        self.assertEqual(self.pairs(result["distribution"]), [("AAA", "30"), ("BBB", "20")])
        self.assertEqual([row["rank"] for row in result["accumulation"]], [1, 2, 3])

        top = result["accumulation"][0]
        self.assertEqual((top["net_qty"], top["net_amount"], top["avg_rate"]), (150, Decimal("76000"), Decimal("510.00")))
        seller = result["distribution"][0]
        self.assertEqual((seller["net_qty"], seller["net_amount"], seller["avg_rate"]), (-160, Decimal("-81050"), Decimal("509.76")))
        self.assertEqual(result["accumulation"][1]["sector"], "Hydro")

    def test_float_pct_uses_public_shares_then_listed(self):
        rows = {(row["symbol"], row["broker"]): row for row in build_acc_dist("1D")["accumulation"]}

        self.assertEqual((rows["AAA", "10"]["float_qty_pct"], rows["AAA", "10"]["float_basis"]), (Decimal("0.0750"), "public"))
        self.assertEqual((rows["BBB", "40"]["float_qty_pct"], rows["BBB", "40"]["float_basis"]), (Decimal("0.0400"), "listed"))

    def test_longer_period_covers_more_sessions(self):
        result = build_acc_dist("2D")

        self.assertEqual((result["sessions"], result["start_date"]), (2, D1))
        rows = {(row["symbol"], row["broker"]): row for row in result["accumulation"] + result["distribution"]}
        self.assertEqual((rows["AAA", "10"]["net_qty"], rows["AAA", "10"]["net_amount"]), (250, Decimal("126000")))
        # Broker 20 sold 100 AAA on D1, bought back 10 on D2.
        self.assertEqual((rows["AAA", "20"]["net_qty"], rows["AAA", "20"]["net_amount"]), (-90, Decimal("-44950")))
        # 3Y on two sessions of history is just both of them.
        self.assertEqual(build_acc_dist("3Y")["sessions"], 2)

    def test_company_scope(self):
        result = build_acc_dist("1D", company_ids=[self.bbb.pk])
        self.assertEqual(self.pairs(result["accumulation"]), [("BBB", "40")])
        self.assertEqual(build_acc_dist("1D", company_ids=[])["sessions"], 0)


class AccDistApiTests(AccDistTestBase):

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username="acc-dist-admin", email="acc-dist-admin@example.test",
            password="unused-test-password", role=User.Role.ADMIN,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_endpoint(self):
        response = self.client.get("/api/analysis/acc-dist/", {"period": "1d"})
        self.assertEqual(response.status_code, 200, response.content[:500])
        self.assertEqual(response.data["period"], "1D")
        self.assertEqual(response.data["accumulation"][0]["broker"], "10")
        self.assertEqual(response.data["distribution"][0]["net_amount"], -81050)

    def test_invalid_period(self):
        self.assertEqual(self.client.get("/api/analysis/acc-dist/", {"period": "5Y"}).status_code, 400)

    def test_new_trades_are_not_hidden_by_the_cache(self):
        first = self.client.get("/api/analysis/acc-dist/").data["accumulation"][0]["net_qty"]
        self.tx(self.aaa, D2, "10", "30", 25, 510)
        second = self.client.get("/api/analysis/acc-dist/").data["accumulation"][0]["net_qty"]
        self.assertEqual((first, second), (150, 175))
