from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.analysis.services.brokers import (
    TOP_STOCKS_LIMIT,
    build_top_stock_by_broker,
    build_top_stocks_by_broker,
)
from apps.companies.models import Company
from apps.floorsheet.models import FloorsheetTransaction

DAY = date(2026, 9, 12)
OTHER_DAY = date(2026, 9, 10)


class TopStocksByBrokerTests(TestCase):
    def setUp(self):
        # 12 companies, so a broker trading all of them is cut to the top 10.
        self.companies = [
            Company.objects.create(symbol=f"S{n:02d}", name=f"Stock {n}", sector="Banking")
            for n in range(1, 13)
        ]
        self.seq = 0

    def tx(self, buyer, seller, quantity, company, when=DAY, rate="100", transaction_id=None):
        self.seq += 1
        return FloorsheetTransaction.objects.create(
            company=company, date=when,
            transaction_id=transaction_id or f"T{self.seq}",
            buyer_broker=buyer, seller_broker=seller,
            quantity=quantity, rate=Decimal(rate),
        )

    def test_limited_to_ten_sorted_by_turnover_with_full_stock_count(self):
        # Broker 1 buys 10, 20 ... 120 shares at Rs 100 in S01 ... S12.
        for n, company in enumerate(self.companies, start=1):
            self.tx("1", "99", 10 * n, company)

        result = build_top_stocks_by_broker(start_date=DAY, end_date=DAY)

        entry = result["1"]
        self.assertEqual(entry["stock_count"], 12)
        self.assertEqual(len(entry["stocks"]), TOP_STOCKS_LIMIT)
        self.assertEqual([row["symbol"] for row in entry["stocks"]], [f"S{n:02d}" for n in range(12, 2, -1)])
        top = entry["stocks"][0]
        self.assertEqual(top["turnover"], Decimal("12000"))
        self.assertEqual((top["buy_amt"], top["sell_amt"]), (Decimal("12000"), Decimal("0")))
        self.assertEqual((top["buy_qty"], top["sell_qty"]), (120, 0))
        self.assertEqual(top["company_id"], self.companies[11].pk)

    def test_buy_and_sell_in_the_same_stock_add_up(self):
        s01, s02 = self.companies[:2]
        self.tx("7", "99", 30, s01)            # buys 3,000 of S01
        self.tx("98", "7", 20, s01)            # sells 2,000 of S01 -> 5,000 total
        self.tx("7", "99", 40, s02)            # buys 4,000 of S02

        stocks = build_top_stocks_by_broker(start_date=DAY, end_date=DAY)["7"]["stocks"]

        self.assertEqual([row["symbol"] for row in stocks], ["S01", "S02"])
        s01_row = stocks[0]
        self.assertEqual((s01_row["buy_amt"], s01_row["sell_amt"], s01_row["turnover"]),
                         (Decimal("3000"), Decimal("2000"), Decimal("5000")))
        self.assertEqual((s01_row["buy_qty"], s01_row["sell_qty"]), (30, 20))

    def test_broker_with_fewer_than_ten_stocks_gets_a_shorter_list(self):
        for company in self.companies[:3]:
            self.tx("5", "99", 10, company)
        entry = build_top_stocks_by_broker(start_date=DAY, end_date=DAY)["5"]
        self.assertEqual(entry["stock_count"], 3)
        self.assertEqual(len(entry["stocks"]), 3)

    def test_equal_turnover_sorts_by_symbol(self):
        for company in reversed(self.companies[:4]):
            self.tx("3", "99", 10, company)
        stocks = build_top_stocks_by_broker(start_date=DAY, end_date=DAY)["3"]["stocks"]
        self.assertEqual([row["symbol"] for row in stocks], ["S01", "S02", "S03", "S04"])

    def test_two_queries_for_any_number_of_brokers(self):
        for broker in range(1, 21):
            for company in self.companies[:5]:
                self.tx(str(broker), str(broker + 50), broker, company)
        with self.assertNumQueries(2):
            result = build_top_stocks_by_broker(start_date=DAY, end_date=DAY)
        self.assertEqual(len(result), 40)     # 20 buyers + 20 sellers

    def test_filters_dates_companies_and_synthetic_rows(self):
        s01, s02 = self.companies[:2]
        self.tx("4", "99", 10, s01)
        self.tx("4", "99", 90, s02, when=OTHER_DAY)                       # other day
        self.tx("4", "99", 500, s01, transaction_id="TX-synthetic-1")     # synthetic row

        result = build_top_stocks_by_broker(start_date=DAY, end_date=DAY)
        self.assertEqual([row["symbol"] for row in result["4"]["stocks"]], ["S01"])
        self.assertEqual(result["4"]["stocks"][0]["buy_qty"], 10)

        restricted = build_top_stocks_by_broker(company_ids=[s02.pk])
        self.assertEqual([row["symbol"] for row in restricted["4"]["stocks"]], ["S02"])

    def test_blank_brokers_are_dropped_and_codes_trimmed(self):
        s01 = self.companies[0]
        self.tx(" 12 ", "", 10, s01)
        result = build_top_stocks_by_broker(start_date=DAY, end_date=DAY)
        self.assertIn("12", result)
        self.assertNotIn("", result)

    def test_custom_limit(self):
        for company in self.companies[:6]:
            self.tx("8", "99", 10, company)
        entry = build_top_stocks_by_broker(start_date=DAY, end_date=DAY, limit=2)["8"]
        self.assertEqual((entry["stock_count"], len(entry["stocks"])), (6, 2))


class TopStockWrapperTests(TestCase):
    """build_top_stock_by_broker keeps its original shape (used by the Broker Explorer)."""

    def setUp(self):
        self.a = Company.objects.create(symbol="AAA", name="A", sector="Banking")
        self.b = Company.objects.create(symbol="BBB", name="B", sector="Banking")
        FloorsheetTransaction.objects.create(company=self.a, date=DAY, transaction_id="W1",
                                             buyer_broker="52", seller_broker="99", quantity=10, rate=Decimal("100"))
        FloorsheetTransaction.objects.create(company=self.b, date=DAY, transaction_id="W2",
                                             buyer_broker="99", seller_broker="52", quantity=30, rate=Decimal("100"))

    def test_same_keys_and_first_ranked_stock(self):
        best = build_top_stock_by_broker(start_date=DAY, end_date=DAY)
        self.assertEqual(set(best["52"]), {"symbol", "buy_amt", "sell_amt", "turnover"})
        self.assertEqual(best["52"], {
            "symbol": "BBB", "buy_amt": Decimal("0"), "sell_amt": Decimal("3000"), "turnover": Decimal("3000"),
        })
        ranked = build_top_stocks_by_broker(start_date=DAY, end_date=DAY)["52"]["stocks"][0]
        self.assertEqual(best["52"]["symbol"], ranked["symbol"])
