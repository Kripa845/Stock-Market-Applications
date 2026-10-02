from datetime import date, timedelta
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.conf import settings

from apps.analysis.models import DailyAnalysis
from apps.companies.models import Company
from apps.market_data.models import DailyPrice
from apps.market_intelligence.models import MarketBreadthSnapshot, ProxyIndexSnapshot
from apps.market_intelligence.services.snapshots import compute_market_snapshots
from apps.market_intelligence.tasks import build_daily_market_intelligence


class MarketSnapshotTests(TestCase):
    def setUp(self):
        self.first = Company.objects.create(symbol="AAA", name="Alpha", sector="Banking")
        self.second = Company.objects.create(symbol="BBB", name="Beta", sector="Banking")
        self.start = date(2025, 1, 5)  # Sunday, first NEPSE session in this fixture.

    def add_price(self, company, day, close, volume=100, turnover=1000):
        return DailyPrice.objects.create(
            company=company, source="crawled", date=day,
            open=close, high=close, low=close, close=close,
            volume=volume, turnover=turnover,
        )

    @staticmethod
    def market_days(start, count):
        days = []
        day = start
        while len(days) < count:
            if day.weekday() not in (4, 5):
                days.append(day)
            day += timedelta(days=1)
        return days

    def test_weekends_and_duplicate_market_date_are_excluded(self):
        sunday, monday, tuesday = self.start, self.start + timedelta(days=1), self.start + timedelta(days=2)
        for company in (self.first, self.second):
            self.add_price(company, sunday, 100)
            self.add_price(company, monday, 101)
            self.add_price(company, tuesday, 101)  # repeated close and volume for all companies
        friday, saturday = date(2025, 1, 10), date(2025, 1, 11)
        for company in (self.first, self.second):
            self.add_price(company, friday, 105)
            self.add_price(company, saturday, 106)

        result = compute_market_snapshots(dry_run=True)

        self.assertEqual(result["sessions"], 2)
        self.assertIn(tuesday, result["excluded_dates"])
        self.assertIn("duplicate date", result["excluded_dates"][tuesday][0])
        self.assertIn(friday, result["excluded_dates"])
        self.assertIn(saturday, result["excluded_dates"])
        self.assertEqual(DailyPrice.objects.count(), 10)  # source rows remain untouched

    @override_settings(MARKET_INTELLIGENCE_EXCLUDED_SESSIONS=["2025-01-06"])
    def test_manual_excluded_sessions_setting(self):
        for offset, close in enumerate((100, 101, 102)):
            day = self.start + timedelta(days=offset)
            self.add_price(self.first, day, close)

        result = compute_market_snapshots(dry_run=True)

        self.assertEqual(result["sessions"], 2)
        self.assertIn(date(2025, 1, 6), result["excluded_dates"])
        self.assertTrue(any("manual exclusion" in reason for reason in result["excluded_dates"][date(2025, 1, 6)]))

    def test_dma_accepts_exactly_95_percent_global_session_coverage(self):
        days = self.market_days(self.start, 50)
        for index, day in enumerate(days):
            self.add_price(self.first, day, 100 + index)
            if index not in (10, 20):
                self.add_price(self.second, day, 200 + index)

        compute_market_snapshots()
        last = MarketBreadthSnapshot.objects.get(date=days[-1])

        self.assertEqual(last.valid_50_dma_count, 2)

    def test_dma_rejects_coverage_below_95_percent(self):
        days = self.market_days(self.start, 50)
        for index, day in enumerate(days):
            self.add_price(self.first, day, 100 + index)
            if index not in (10, 20, 30):
                self.add_price(self.second, day, 200 + index)

        compute_market_snapshots()
        last = MarketBreadthSnapshot.objects.get(date=days[-1])

        self.assertEqual(last.valid_50_dma_count, 1)

    def test_first_session_has_no_return(self):
        self.add_price(self.first, self.start, 100)

        compute_market_snapshots()

        proxy = ProxyIndexSnapshot.objects.get(date=self.start)
        breadth = MarketBreadthSnapshot.objects.get(date=self.start)
        self.assertIsNone(proxy.daily_return_pct)
        self.assertEqual(proxy.level, Decimal("1000"))
        self.assertEqual(breadth.return_eligible_count, 0)

    def test_corporate_action_sessions_are_excluded_from_breadth_and_proxy(self):
        dates = self.market_days(self.start, 3)
        for day, first_close, second_close in zip(dates, (100, 120, 121), (100, 101, 102)):
            self.add_price(self.first, day, first_close, turnover=1000)
            self.add_price(self.second, day, second_close, turnover=1000)

        compute_market_snapshots()

        breadth = MarketBreadthSnapshot.objects.get(date=dates[1])
        proxy = ProxyIndexSnapshot.objects.get(date=dates[1])
        self.assertEqual(breadth.corporate_action_excluded_count, 1)
        self.assertEqual(breadth.return_eligible_count, 1)
        self.assertEqual(proxy.corporate_action_excluded_count, 1)
        self.assertEqual(proxy.eligible_company_count, 1)
        self.assertEqual(proxy.daily_return_pct, Decimal("1.000000"))

    def test_previous_close_mismatch_is_flagged(self):
        first_day, second_day = self.market_days(self.start, 2)
        self.add_price(self.first, first_day, 100)
        current = self.add_price(self.first, second_day, 101)
        DailyAnalysis.objects.create(
            company=self.first, date=second_day, close_price=101, volume=100,
            previous_close=Decimal("99"),
        )

        compute_market_snapshots()

        self.assertEqual(
            MarketBreadthSnapshot.objects.get(date=second_day).corporate_action_excluded_count,
            1,
        )
        self.assertEqual(
            ProxyIndexSnapshot.objects.get(date=second_day).eligible_company_count,
            0,
        )
        self.assertEqual(current.close, Decimal("101.00"))

    def test_backfill_is_idempotent_and_dry_run_writes_nothing(self):
        for offset, close in enumerate((100, 101, 102)):
            self.add_price(self.first, self.start + timedelta(days=offset), close)

        output = StringIO()
        call_command("backfill_market_intelligence", "--dry-run", stdout=output)
        self.assertIn("Would compute", output.getvalue())
        self.assertEqual(MarketBreadthSnapshot.objects.count(), 0)
        self.assertEqual(ProxyIndexSnapshot.objects.count(), 0)

        call_command("backfill_market_intelligence", stdout=StringIO())
        first_breadth = list(MarketBreadthSnapshot.objects.values().exclude(computed_at=None).order_by("date"))
        first_proxy = list(ProxyIndexSnapshot.objects.values().exclude(computed_at=None).order_by("date"))
        for row in first_breadth + first_proxy:
            row.pop("computed_at", None)
        call_command("backfill_market_intelligence", stdout=StringIO())

        second_breadth = list(MarketBreadthSnapshot.objects.values().order_by("date"))
        second_proxy = list(ProxyIndexSnapshot.objects.values().order_by("date"))
        for row in second_breadth + second_proxy:
            row.pop("computed_at", None)
        self.assertEqual(first_breadth, second_breadth)
        self.assertEqual(first_proxy, second_proxy)

    def test_scheduled_intelligence_task_is_idempotent_and_runs_after_analysis(self):
        self.add_price(self.first, self.start, 100)

        self.assertEqual(build_daily_market_intelligence.run()["ok"], True)
        first_counts = (
            MarketBreadthSnapshot.objects.count(),
            ProxyIndexSnapshot.objects.count(),
        )
        self.assertEqual(build_daily_market_intelligence.run()["ok"], True)
        self.assertEqual(
            (MarketBreadthSnapshot.objects.count(), ProxyIndexSnapshot.objects.count()),
            first_counts,
        )
        schedule = settings.CELERY_BEAT_SCHEDULE["build-market-intelligence-after-analysis"]
        self.assertEqual(schedule["task"], "apps.market_intelligence.tasks.build_daily_market_intelligence")
        self.assertEqual(schedule["schedule"].hour, {19})
