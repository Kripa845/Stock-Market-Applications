# """Trading-calendar tests: sessions, not calendar days."""

# from datetime import date, timedelta
# from decimal import Decimal

# from django.test import TestCase

# from apps.companies.models import Company
# from apps.market_data.models import DailyPrice
# from apps.market_data.services.trading_calendar import (
#     latest_trading_date,
#     previous_trading_sessions,
#     rolling_window_bounds,
#     select_sample_dates,
#     trading_dates,
# )


# class CalendarTestBase(TestCase):

#     def setUp(self):
#         self.company = Company.objects.create(
#             symbol="NABIL", name="Nabil Bank", sector="Banking",
#         )

#     def price(self, when, close="100", volume=1000, company=None):
#         return DailyPrice.objects.create(
#             company=company or self.company,
#             date=when,
#             open=Decimal(close),
#             high=Decimal(close),
#             low=Decimal(close),
#             close=Decimal(close),
#             volume=volume,
#             turnover=Decimal(close) * volume,
#         )

#     def weekday_sessions(self, count, start=date(2026, 8, 3)):
#         """`count` consecutive weekday sessions, skipping weekends."""
#         sessions = []
#         cursor = start
#         while len(sessions) < count:
#             if cursor.weekday() < 5:
#                 sessions.append(cursor)
#             cursor += timedelta(days=1)
#         return sessions


# class LatestTradingDateTests(CalendarTestBase):

#     def test_returns_latest_stored_date(self):
#         self.price(date(2026, 9, 14))
#         self.price(date(2026, 9, 18))
#         self.price(date(2026, 9, 16))

#         self.assertEqual(latest_trading_date(), date(2026, 9, 18))

#     def test_is_not_today(self):
#         # The whole point: if the market last traded days ago, we anchor
#         # to that, not to date.today().
#         stale = date(2020, 1, 6)
#         self.price(stale)

#         self.assertEqual(latest_trading_date(), stale)
#         self.assertNotEqual(latest_trading_date(), date.today())

#     def test_returns_none_with_no_data(self):
#         self.assertIsNone(latest_trading_date())

#     def test_can_be_scoped_to_a_company(self):
#         other = Company.objects.create(
#             symbol="NICA", name="NIC Asia", sector="Banking",
#         )
#         self.price(date(2026, 9, 18))
#         self.price(date(2026, 9, 10), company=other)

#         self.assertEqual(latest_trading_date(company=other), date(2026, 9, 10))


# class PreviousSessionTests(CalendarTestBase):

#     def test_returns_only_dates_strictly_before_the_anchor(self):
#         sessions = self.weekday_sessions(5)
#         for day in sessions:
#             self.price(day)

#         previous = previous_trading_sessions(sessions[-1], 10)

#         self.assertNotIn(sessions[-1], previous)
#         self.assertEqual(len(previous), 4)

#     def test_returns_fewer_when_history_is_short(self):
#         sessions = self.weekday_sessions(3)
#         for day in sessions:
#             self.price(day)

#         self.assertEqual(len(previous_trading_sessions(sessions[-1], 20)), 2)

#     def test_skips_weekends_automatically(self):
#         # Weekend dates are simply never in DailyPrice.
#         sessions = self.weekday_sessions(10)
#         for day in sessions:
#             self.price(day)

#         previous = previous_trading_sessions(sessions[-1], 5)

#         for day in previous:
#             self.assertLess(day.weekday(), 5)

#     def test_empty_for_missing_anchor(self):
#         self.assertEqual(previous_trading_sessions(None, 5), [])


# class SampleDateTests(CalendarTestBase):

#     def test_offsets_are_sessions_not_calendar_days(self):
#         sessions = self.weekday_sessions(30)
#         for day in sessions:
#             self.price(day)

#         selected = select_sample_dates(offsets=(0, 5))
#         latest = sessions[-1]

#         self.assertEqual(selected[0], latest)

#         # Five SESSIONS back is seven calendar days back across a weekend.
#         self.assertEqual(selected[1], sessions[-6])
#         self.assertNotEqual(selected[1], latest - timedelta(days=5))

#     def test_default_sample_selects_six_dates(self):
#         for day in self.weekday_sessions(40):
#             self.price(day)

#         self.assertEqual(len(select_sample_dates()), 6)

#     def test_selection_is_deterministic(self):
#         for day in self.weekday_sessions(40):
#             self.price(day)

#         self.assertEqual(select_sample_dates(), select_sample_dates())

#     def test_sorted_descending_and_unique(self):
#         for day in self.weekday_sessions(40):
#             self.price(day)

#         selected = select_sample_dates()

#         self.assertEqual(selected, sorted(selected, reverse=True))
#         self.assertEqual(len(selected), len(set(selected)))

#     def test_short_history_drops_unavailable_offsets(self):
#         # Only 8 sessions: offsets 10, 15, 20, 25 cannot be satisfied and
#         # must be dropped rather than guessed at.
#         for day in self.weekday_sessions(8):
#             self.price(day)

#         selected = select_sample_dates()

#         self.assertEqual(len(selected), 2)  # offsets 0 and 5 only

#     def test_no_history_returns_empty(self):
#         self.assertEqual(select_sample_dates(), [])

#     def test_never_returns_a_non_trading_day(self):
#         sessions = self.weekday_sessions(40)
#         for day in sessions:
#             self.price(day)

#         for selected in select_sample_dates():
#             self.assertIn(selected, sessions)
#             self.assertLess(selected.weekday(), 5)

#     def test_same_dates_for_every_company(self):
#         # Sampled dates are market-wide so cross-company comparison on a
#         # sampled date is valid.
#         other = Company.objects.create(
#             symbol="NICA", name="NIC Asia", sector="Banking",
#         )
#         sessions = self.weekday_sessions(40)
#         for day in sessions:
#             self.price(day)
#             self.price(day, company=other)

#         self.assertEqual(select_sample_dates(), select_sample_dates())

#     def test_custom_offsets(self):
#         sessions = self.weekday_sessions(20)
#         for day in sessions:
#             self.price(day)

#         selected = select_sample_dates(offsets=(0, 1, 2))

#         self.assertEqual(selected, [sessions[-1], sessions[-2], sessions[-3]])

#     def test_duplicate_offsets_collapse(self):
#         for day in self.weekday_sessions(20):
#             self.price(day)

#         self.assertEqual(len(select_sample_dates(offsets=(0, 0, 5, 5))), 2)


# class RollingWindowTests(CalendarTestBase):

#     def test_window_anchors_to_latest_available_date(self):
#         self.price(date(2026, 9, 18))

#         start, end = rolling_window_bounds(window_days=31)

#         self.assertEqual(end, date(2026, 9, 18))
#         self.assertEqual(start, date(2026, 8, 18))

#     def test_window_is_none_without_data(self):
#         self.assertEqual(rolling_window_bounds(), (None, None))

#     def test_window_does_not_use_today(self):
#         self.price(date(2020, 1, 6))

#         start, end = rolling_window_bounds(window_days=31)

#         self.assertEqual(end, date(2020, 1, 6))
#         self.assertNotEqual(end, date.today())


# class TradingDatesTests(CalendarTestBase):

#     def test_duplicate_dates_across_companies_are_distinct(self):
#         other = Company.objects.create(
#             symbol="NICA", name="NIC Asia", sector="Banking",
#         )
#         day = date(2026, 9, 18)
#         self.price(day)
#         self.price(day, company=other)

#         self.assertEqual(trading_dates(), [day])

#     def test_limit_is_respected(self):
#         for day in self.weekday_sessions(10):
#             self.price(day)

#         self.assertEqual(len(trading_dates(limit=3)), 3)
"""Trading-calendar tests: sessions, not calendar days."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from django.test import TestCase

from apps.companies.models import Company
from apps.market_data.models import DailyPrice
from apps.market_data.services.trading_calendar import (
    latest_trading_date,
    previous_trading_sessions,
    rolling_window_bounds,
    select_sample_dates,
    trading_dates,
)
from apps.market_data.services.intraday import aggregate_intraday_trades


class CalendarTestBase(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            symbol="NABIL", name="Nabil Bank", sector="Banking",
        )

    def price(self, when, close="100", volume=1000, company=None):
        return DailyPrice.objects.create(
            company=company or self.company,
            date=when,
            open=Decimal(close),
            high=Decimal(close),
            low=Decimal(close),
            close=Decimal(close),
            volume=volume,
            turnover=Decimal(close) * volume,
        )

    def weekday_sessions(self, count, start=date(2026, 8, 3)):
        """`count` consecutive weekday sessions, skipping weekends."""
        sessions = []
        cursor = start
        while len(sessions) < count:
            if cursor.weekday() < 5:
                sessions.append(cursor)
            cursor += timedelta(days=1)
        return sessions


class LatestTradingDateTests(CalendarTestBase):

    def test_returns_latest_stored_date(self):
        self.price(date(2026, 9, 14))
        self.price(date(2026, 9, 18))
        self.price(date(2026, 9, 16))

        self.assertEqual(latest_trading_date(), date(2026, 9, 18))

    def test_is_not_today(self):
        # The whole point: if the market last traded days ago, we anchor
        # to that, not to date.today().
        stale = date(2020, 1, 6)
        self.price(stale)

        self.assertEqual(latest_trading_date(), stale)
        self.assertNotEqual(latest_trading_date(), date.today())

    def test_returns_none_with_no_data(self):
        self.assertIsNone(latest_trading_date())

    def test_can_be_scoped_to_a_company(self):
        other = Company.objects.create(
            symbol="NICA", name="NIC Asia", sector="Banking",
        )
        self.price(date(2026, 9, 18))
        self.price(date(2026, 9, 10), company=other)

        self.assertEqual(latest_trading_date(company=other), date(2026, 9, 10))


class PreviousSessionTests(CalendarTestBase):

    def test_returns_only_dates_strictly_before_the_anchor(self):
        sessions = self.weekday_sessions(5)
        for day in sessions:
            self.price(day)

        previous = previous_trading_sessions(sessions[-1], 10)

        self.assertNotIn(sessions[-1], previous)
        self.assertEqual(len(previous), 4)

    def test_returns_fewer_when_history_is_short(self):
        sessions = self.weekday_sessions(3)
        for day in sessions:
            self.price(day)

        self.assertEqual(len(previous_trading_sessions(sessions[-1], 20)), 2)

    def test_skips_weekends_automatically(self):
        # Weekend dates are simply never in DailyPrice.
        sessions = self.weekday_sessions(10)
        for day in sessions:
            self.price(day)

        previous = previous_trading_sessions(sessions[-1], 5)

        for day in previous:
            self.assertLess(day.weekday(), 5)

    def test_empty_for_missing_anchor(self):
        self.assertEqual(previous_trading_sessions(None, 5), [])


class SampleDateTests(CalendarTestBase):

    def test_offsets_are_sessions_not_calendar_days(self):
        sessions = self.weekday_sessions(30)
        for day in sessions:
            self.price(day)

        selected = select_sample_dates(offsets=(0, 5))
        latest = sessions[-1]

        self.assertEqual(selected[0], latest)

        # Five SESSIONS back is seven calendar days back across a weekend.
        self.assertEqual(selected[1], sessions[-6])
        self.assertNotEqual(selected[1], latest - timedelta(days=5))

    def test_default_sample_selects_six_dates(self):
        for day in self.weekday_sessions(40):
            self.price(day)

        self.assertEqual(len(select_sample_dates()), 6)

    def test_selection_is_deterministic(self):
        for day in self.weekday_sessions(40):
            self.price(day)

        self.assertEqual(select_sample_dates(), select_sample_dates())

    def test_sorted_descending_and_unique(self):
        for day in self.weekday_sessions(40):
            self.price(day)

        selected = select_sample_dates()

        self.assertEqual(selected, sorted(selected, reverse=True))
        self.assertEqual(len(selected), len(set(selected)))

    def test_short_history_drops_unavailable_offsets(self):
        # Only 8 sessions: offsets 10, 15, 20, 25 cannot be satisfied and
        # must be dropped rather than guessed at.
        for day in self.weekday_sessions(8):
            self.price(day)

        selected = select_sample_dates()

        self.assertEqual(len(selected), 2)  # offsets 0 and 5 only

    def test_no_history_returns_empty(self):
        self.assertEqual(select_sample_dates(), [])

    def test_never_returns_a_non_trading_day(self):
        sessions = self.weekday_sessions(40)
        for day in sessions:
            self.price(day)

        for selected in select_sample_dates():
            self.assertIn(selected, sessions)
            self.assertLess(selected.weekday(), 5)

    def test_same_dates_for_every_company(self):
        # Sampled dates are market-wide so cross-company comparison on a
        # sampled date is valid.
        other = Company.objects.create(
            symbol="NICA", name="NIC Asia", sector="Banking",
        )
        sessions = self.weekday_sessions(40)
        for day in sessions:
            self.price(day)
            self.price(day, company=other)

        self.assertEqual(select_sample_dates(), select_sample_dates())

    def test_custom_offsets(self):
        sessions = self.weekday_sessions(20)
        for day in sessions:
            self.price(day)

        selected = select_sample_dates(offsets=(0, 1, 2))

        self.assertEqual(selected, [sessions[-1], sessions[-2], sessions[-3]])

    def test_duplicate_offsets_collapse(self):
        for day in self.weekday_sessions(20):
            self.price(day)

        self.assertEqual(len(select_sample_dates(offsets=(0, 0, 5, 5))), 2)


class RollingWindowTests(CalendarTestBase):

    def test_window_anchors_to_latest_available_date(self):
        self.price(date(2026, 9, 18))

        start, end = rolling_window_bounds(window_days=31)

        self.assertEqual(end, date(2026, 9, 18))
        self.assertEqual(start, date(2026, 8, 18))

    def test_window_is_none_without_data(self):
        self.assertEqual(rolling_window_bounds(), (None, None))

    def test_window_does_not_use_today(self):
        self.price(date(2020, 1, 6))

        start, end = rolling_window_bounds(window_days=31)

        self.assertEqual(end, date(2020, 1, 6))
        self.assertNotEqual(end, date.today())


class TradingDatesTests(CalendarTestBase):

    def test_duplicate_dates_across_companies_are_distinct(self):
        other = Company.objects.create(
            symbol="NICA", name="NIC Asia", sector="Banking",
        )
        day = date(2026, 9, 18)
        self.price(day)
        self.price(day, company=other)

        self.assertEqual(trading_dates(), [day])

    def test_limit_is_respected(self):
        for day in self.weekday_sessions(10):
            self.price(day)

        self.assertEqual(len(trading_dates(limit=3)), 3)


class IntradayAggregationTests(TestCase):

    def setUp(self):
        self.npt = ZoneInfo("Asia/Kathmandu")

    def trade(self, hour, minute, second, rate, quantity):
        return SimpleNamespace(
            trade_time=datetime(2026, 9, 28, hour, minute, second, tzinfo=self.npt),
            rate=Decimal(rate),
            quantity=quantity,
        )

    def test_aggregates_first_last_high_low_and_volume(self):
        bars = aggregate_intraday_trades([
            self.trade(11, 0, 5, "100", 2),
            self.trade(11, 0, 45, "103", 3),
            self.trade(11, 0, 58, "99", 4),
        ])

        self.assertEqual(len(bars), 1)
        self.assertEqual(
            {key: bars[0][key] for key in ("open", "high", "low", "close", "volume")},
            {"open": 100.0, "high": 103.0, "low": 99.0, "close": 99.0, "volume": 9},
        )

    def test_leaves_empty_minutes_as_gaps(self):
        bars = aggregate_intraday_trades([
            self.trade(11, 0, 10, "100", 1),
            self.trade(11, 3, 10, "101", 1),
        ])

        self.assertEqual(len(bars), 2)
        self.assertNotEqual(bars[0]["time"], bars[1]["time"])

    def test_serializes_nepal_timezone_offset(self):
        bars = aggregate_intraday_trades([self.trade(11, 0, 10, "100", 1)])

        self.assertTrue(bars[0]["time"].endswith("+05:45"))
# Broker directory import and response fallback coverage.
import csv
import json
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from apps.analysis.serializers import BrokerActivitySerializer
from apps.market_data.models import Broker
from crawlers.crawlers.pipelines import BrokerPipeline
from crawlers.crawlers.spiders.brokers import BrokersSpider
from scrapy import Request
from scrapy.http import TextResponse


class BrokerDirectoryTests(TestCase):
    def test_import_brokers_is_idempotent_and_updates_rows(self):
        csv_path = Path(__file__).parent / "_brokers_test.csv"
        try:
            with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=["broker_code", "name", "short_name", "logo_filename"])
                writer.writeheader()
                writer.writerow({"broker_code": "58", "name": "Alpha Securities", "short_name": "Alpha", "logo_filename": "alpha.svg"})
            call_command("import_brokers", str(csv_path), stdout=None)
            call_command("import_brokers", str(csv_path), stdout=None)
        finally:
            csv_path.unlink(missing_ok=True)

        self.assertEqual(Broker.objects.count(), 1)
        broker = Broker.objects.get(broker_code="58")
        self.assertEqual(broker.name, "Alpha Securities")
        self.assertEqual(broker.logo, "alpha.svg")

    def test_missing_directory_row_uses_broker_code_fallback(self):
        payload = BrokerActivitySerializer([{
            "broker": "999",
            "buy_quantity": 0,
            "sell_quantity": 0,
            "net_quantity": 0,
            "buy_value": 0,
            "sell_value": 0,
            "net_value": 0,
            "total_quantity": 0,
            "total_value": 0,
            "buy_trades": 0,
            "sell_trades": 0,
            "trades": 0,
        }], many=True).data[0]
        self.assertEqual(payload["broker_code"], "999")
        self.assertEqual(payload["name"], "Broker 999")
        self.assertEqual(payload["short_name"], "Broker 999")
        self.assertIsNone(payload["logo_url"])

    def test_spider_parses_sample_and_requests_more_pages_if_api_caps_limit(self):
        payload = {
            "success": True,
            "data": {
                "total": 91,
                "page": 1,
                "limit": 20,
                "brokers": [{
                    "id": 158,
                    "member_code": 58,
                    "member_name": "Naasa Securities Co. Ltd.",
                    "tms_link": "tms58.nepsetms.com.np",
                    "total_transactions": 10462,
                    "total_turnover": 733387361.58,
                    "total_buy_turnover": 436584730.2,
                    "total_sell_turnover": 296802631.38,
                    "rank": 1,
                    "date": "2026-09-30",
                }],
            },
        }
        url = "https://nepseportfoliotracker.app/api/brokers?page=1&limit=100"
        response = TextResponse(
            url=url,
            request=Request(url),
            body=json.dumps(payload).encode("utf-8"),
            encoding="utf-8",
        )

        output = list(BrokersSpider().parse(response))

        self.assertEqual(output[0], {
            "broker_no": 58,
            "name": "Naasa Securities Co. Ltd.",
            "tms_link": "tms58.nepsetms.com.np",
        })
        self.assertEqual(output[1].meta["page"], 2)
        self.assertIn("limit=100", output[1].url)

    def test_broker_pipeline_is_idempotent(self):
        pipeline = BrokerPipeline()
        item = {
            "broker_no": 58,
            "name": "Naasa Securities Co. Ltd.",
            "tms_link": "tms58.nepsetms.com.np",
        }

        pipeline.process_item(item, spider=None)
        pipeline.process_item(item, spider=None)

        self.assertEqual(Broker.objects.filter(broker_no=58).count(), 1)
        broker = Broker.objects.get(broker_no=58)
        self.assertEqual(broker.name, item["name"])
