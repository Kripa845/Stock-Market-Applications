"""
Broker net buy/sell analysis over FloorsheetTransaction.

Gross activity and net position are different questions and must not be
conflated.
"""

from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.analysis.services.brokers import build_broker_activity
from apps.companies.models import Company
from apps.market_data.models import FloorsheetTransaction


class BrokerTestBase(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            symbol="NABIL",
            name="Nabil Bank",
            sector="Banking",
        )
        self.other = Company.objects.create(
            symbol="NICA",
            name="NIC Asia",
            sector="Banking",
        )
        self.counter = 0

    def tx(self, buyer, seller, quantity, rate, when=None, company=None):
        self.counter += 1
        return FloorsheetTransaction.objects.create(
            company=company or self.company,
            date=when or date(2026, 9, 18),
            transaction_id=f"TX{self.counter:05d}",
            buyer_broker=buyer,
            seller_broker=seller,
            quantity=quantity,
            rate=Decimal(str(rate)),
        )

    def broker(self, result, name):
        for row in result["brokers"]:
            if row["broker"] == name:
                return row
        self.fail(f"broker {name} not present in combined structure")


class BrokerCoverageTests(BrokerTestBase):

    def test_broker_appearing_only_as_buyer_is_included(self):
        self.tx(buyer="58", seller="49", quantity=100, rate=500)

        row = self.broker(build_broker_activity(company=self.company), "58")

        self.assertEqual(row["buy_quantity"], 100)
        self.assertEqual(row["sell_quantity"], 0)
        self.assertEqual(row["net_quantity"], 100)
        self.assertEqual(row["buy_value"], Decimal("50000"))
        self.assertEqual(row["sell_value"], Decimal("0"))
        self.assertEqual(row["net_value"], Decimal("50000"))

    def test_broker_appearing_only_as_seller_is_included(self):
        self.tx(buyer="58", seller="49", quantity=100, rate=500)

        row = self.broker(build_broker_activity(company=self.company), "49")

        self.assertEqual(row["buy_quantity"], 0)
        self.assertEqual(row["sell_quantity"], 100)
        self.assertEqual(row["net_quantity"], -100)
        self.assertEqual(row["net_value"], Decimal("-50000"))

    def test_broker_on_both_sides_is_one_combined_row(self):
        self.tx(buyer="58", seller="49", quantity=300, rate=100)
        self.tx(buyer="11", seller="58", quantity=100, rate=100)

        result = build_broker_activity(company=self.company)
        rows = [r for r in result["brokers"] if r["broker"] == "58"]

        # One row, not one buy row plus one sell row.
        self.assertEqual(len(rows), 1)

        row = rows[0]
        self.assertEqual(row["buy_quantity"], 300)
        self.assertEqual(row["sell_quantity"], 100)
        self.assertEqual(row["net_quantity"], 200)
        self.assertEqual(row["net_value"], Decimal("20000"))
        self.assertEqual(row["total_quantity"], 400)

    def test_equal_buy_and_sell_quantity_nets_to_zero(self):
        self.tx(buyer="58", seller="49", quantity=200, rate=100)
        self.tx(buyer="11", seller="58", quantity=200, rate=100)

        row = self.broker(build_broker_activity(company=self.company), "58")

        self.assertEqual(row["buy_quantity"], 200)
        self.assertEqual(row["sell_quantity"], 200)
        self.assertEqual(row["net_quantity"], 0)
        self.assertEqual(row["net_value"], Decimal("0"))

        # Net zero but gross 400 -- the distinction the spec cares about.
        self.assertEqual(row["total_quantity"], 400)

    def test_negative_net_quantity_when_selling_dominates(self):
        self.tx(buyer="11", seller="58", quantity=500, rate=100)
        self.tx(buyer="58", seller="49", quantity=100, rate=100)

        row = self.broker(build_broker_activity(company=self.company), "58")

        self.assertEqual(row["net_quantity"], -400)
        self.assertEqual(row["net_value"], Decimal("-40000"))


class BrokerValueTests(BrokerTestBase):

    def test_value_is_quantity_times_rate(self):
        self.tx(buyer="58", seller="49", quantity=250, rate="412.50")

        row = self.broker(build_broker_activity(company=self.company), "58")

        self.assertEqual(row["buy_value"], Decimal("103125.0000"))

    def test_values_sum_across_multiple_transactions(self):
        self.tx(buyer="58", seller="49", quantity=100, rate="500.00")
        self.tx(buyer="58", seller="11", quantity=200, rate="510.00")

        row = self.broker(build_broker_activity(company=self.company), "58")

        self.assertEqual(row["buy_quantity"], 300)
        self.assertEqual(row["buy_value"], Decimal("152000"))

    def test_decimal_rates_are_not_rounded_to_int(self):
        self.tx(buyer="58", seller="49", quantity=3, rate="333.3333")

        row = self.broker(build_broker_activity(company=self.company), "58")

        self.assertEqual(row["buy_value"], Decimal("999.9999"))
        self.assertIsInstance(row["buy_value"], Decimal)

    def test_value_ignores_the_nullable_amount_column(self):
        # amount is left NULL; value must still be computed.
        tx = self.tx(buyer="58", seller="49", quantity=10, rate="100")
        self.assertIsNone(tx.amount)

        row = self.broker(build_broker_activity(company=self.company), "58")
        self.assertEqual(row["buy_value"], Decimal("1000"))


class TopMetricTests(BrokerTestBase):

    def setUp(self):
        super().setUp()
        # Broker 58: buys 1000, sells 900  -> gross buyer 1000, net +100
        # Broker 11: buys 400,  sells 0    -> gross buyer 400,  net +400
        # Broker 49: buys 0,    sells 500  -> gross seller 500, net -500
        self.tx(buyer="58", seller="49", quantity=500, rate=100)
        self.tx(buyer="58", seller="99", quantity=500, rate=100)
        self.tx(buyer="99", seller="58", quantity=900, rate=100)
        self.tx(buyer="11", seller="49", quantity=400, rate=100)

    def test_most_active_buyer_is_gross_not_net(self):
        result = build_broker_activity(company=self.company)

        # 58 has the highest GROSS buy quantity even though its net is tiny.
        self.assertEqual(result["most_active_buyer"]["broker"], "58")
        self.assertEqual(result["most_active_buyer"]["buy_quantity"], 1000)

    def test_top_net_buyer_is_net_not_gross(self):
        result = build_broker_activity(company=self.company)

        # 11 nets +400, beating 58's +100, despite buying less overall.
        self.assertEqual(result["top_net_buyer"]["broker"], "11")
        self.assertEqual(result["top_net_buyer"]["net_quantity"], 400)

    def test_most_active_buyer_differs_from_top_net_buyer(self):
        result = build_broker_activity(company=self.company)

        self.assertNotEqual(
            result["most_active_buyer"]["broker"],
            result["top_net_buyer"]["broker"],
        )

    def test_most_active_seller(self):
        result = build_broker_activity(company=self.company)

        # 99 sells 500, 58 sells 900, 49 sells 900.
        self.assertEqual(result["most_active_seller"]["sell_quantity"], 900)

    def test_top_net_seller_is_most_negative(self):
        result = build_broker_activity(company=self.company)

        self.assertEqual(result["top_net_seller"]["broker"], "49")
        self.assertEqual(result["top_net_seller"]["net_quantity"], -900)

    def test_no_transactions_yields_none_metrics(self):
        result = build_broker_activity(company=self.other)

        self.assertEqual(result["brokers"], [])
        self.assertIsNone(result["most_active_buyer"])
        self.assertIsNone(result["most_active_seller"])
        self.assertIsNone(result["top_net_buyer"])
        self.assertIsNone(result["top_net_seller"])


class FilteringTests(BrokerTestBase):

    def test_filter_by_company(self):
        self.tx(buyer="58", seller="49", quantity=100, rate=100)
        self.tx(buyer="58", seller="49", quantity=900, rate=100,
                company=self.other)

        row = self.broker(build_broker_activity(company=self.company), "58")
        self.assertEqual(row["buy_quantity"], 100)

    def test_filter_by_single_date(self):
        self.tx(buyer="58", seller="49", quantity=100, rate=100,
                when=date(2026, 9, 18))
        self.tx(buyer="58", seller="49", quantity=900, rate=100,
                when=date(2026, 9, 11))

        result = build_broker_activity(
            company=self.company,
            date=date(2026, 9, 18),
        )
        self.assertEqual(self.broker(result, "58")["buy_quantity"], 100)

    def test_filter_by_date_range(self):
        self.tx(buyer="58", seller="49", quantity=100, rate=100,
                when=date(2026, 9, 18))
        self.tx(buyer="58", seller="49", quantity=200, rate=100,
                when=date(2026, 9, 11))
        self.tx(buyer="58", seller="49", quantity=400, rate=100,
                when=date(2026, 8, 1))

        result = build_broker_activity(
            company=self.company,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30),
        )
        self.assertEqual(self.broker(result, "58")["buy_quantity"], 300)

    def test_unfiltered_covers_every_sampled_date(self):
        self.tx(buyer="58", seller="49", quantity=100, rate=100,
                when=date(2026, 9, 18))
        self.tx(buyer="58", seller="49", quantity=200, rate=100,
                when=date(2026, 8, 1))

        result = build_broker_activity(company=self.company)
        self.assertEqual(self.broker(result, "58")["buy_quantity"], 300)


class DataQualityTests(BrokerTestBase):

    def test_blank_broker_values_are_dropped(self):
        self.tx(buyer="", seller="49", quantity=100, rate=100)
        self.tx(buyer="58", seller="   ", quantity=100, rate=100)

        result = build_broker_activity(company=self.company)
        names = [row["broker"] for row in result["brokers"]]

        self.assertNotIn("", names)
        self.assertNotIn("   ", names)
        self.assertIn("58", names)
        self.assertIn("49", names)

    def test_placeholder_broker_values_are_dropped(self):
        self.tx(buyer="N/A", seller="49", quantity=100, rate=100)

        names = [
            row["broker"]
            for row in build_broker_activity(company=self.company)["brokers"]
        ]
        self.assertNotIn("N/A", names)

    def test_broker_names_are_whitespace_normalised(self):
        self.tx(buyer=" 58 ", seller="49", quantity=100, rate=100)
        self.tx(buyer="58", seller="49", quantity=100, rate=100)

        result = build_broker_activity(company=self.company)
        rows = [r for r in result["brokers"] if r["broker"] == "58"]

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["buy_quantity"], 200)


class OrderingAndQueryTests(BrokerTestBase):

    def test_ordering_is_deterministic(self):
        self.tx(buyer="58", seller="49", quantity=100, rate=100)
        self.tx(buyer="11", seller="22", quantity=100, rate=100)
        self.tx(buyer="33", seller="44", quantity=100, rate=100)

        first = [
            r["broker"]
            for r in build_broker_activity(company=self.company)["brokers"]
        ]
        second = [
            r["broker"]
            for r in build_broker_activity(company=self.company)["brokers"]
        ]

        self.assertEqual(first, second)

    def test_ordering_is_net_quantity_desc_then_broker_asc(self):
        # Three brokers all net +100, so the tiebreak must be by name.
        self.tx(buyer="58", seller="X", quantity=100, rate=100)
        self.tx(buyer="11", seller="Y", quantity=100, rate=100)
        self.tx(buyer="33", seller="Z", quantity=100, rate=100)

        rows = build_broker_activity(company=self.company)["brokers"]
        positive = [r["broker"] for r in rows if r["net_quantity"] == 100]

        self.assertEqual(positive, sorted(positive))

    def test_query_count_does_not_grow_with_broker_count(self):
        # Two grouped aggregates plus one count, regardless of scale.
        for index in range(30):
            self.tx(buyer=f"B{index}", seller=f"S{index}",
                    quantity=100, rate=100)

        with self.assertNumQueries(3):
            build_broker_activity(company=self.company)

    def test_totals_are_consistent_with_rows(self):
        self.tx(buyer="58", seller="49", quantity=100, rate=100)
        self.tx(buyer="11", seller="22", quantity=300, rate=100)

        result = build_broker_activity(company=self.company)

        self.assertEqual(result["total_buy_quantity"], 400)
        self.assertEqual(result["total_sell_quantity"], 400)
        self.assertEqual(result["transaction_count"], 2)
        self.assertEqual(result["broker_count"], 4)
