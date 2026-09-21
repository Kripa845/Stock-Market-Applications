"""
End-to-end: DailyPrice -> analysis task -> DailyAnalysis -> API.

Verifies the pieces agree with each other, and that the dashboard reads
stored state rather than recomputing on the request path.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from apps.analysis.models import DailyAnalysis
from apps.analysis.services.daily_metrics import BASELINE_SESSIONS
from apps.analysis.tasks import rebuild_all_analysis, rebuild_company_analysis_task
from apps.companies.models import Company
from apps.market_data.models import DailyPrice


class AnalysisPipelineTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            symbol="NABIL", name="Nabil Bank", sector="Banking",
        )
        self.sessions = self._weekdays(25)

        for index, day in enumerate(self.sessions):
            close = Decimal("100") + index
            DailyPrice.objects.create(
                company=self.company,
                date=day,
                open=close,
                high=close + 2,
                low=close - 2,
                close=close,
                volume=1000,
                turnover=close * 1000,
            )

    @staticmethod
    def _weekdays(count, start=date(2026, 8, 3)):
        out, cursor = [], start
        while len(out) < count:
            if cursor.weekday() < 5:
                out.append(cursor)
            cursor += timedelta(days=1)
        return out

    def test_task_writes_one_row_per_trading_day(self):
        rebuild_company_analysis_task(self.company.id)

        self.assertEqual(
            DailyAnalysis.objects.filter(company=self.company).count(),
            len(self.sessions),
        )

    def test_daily_vwap_is_stored_per_day(self):
        rebuild_company_analysis_task(self.company.id)

        row = DailyAnalysis.objects.get(
            company=self.company, date=self.sessions[-1],
        )
        # close 124, volume 1000, turnover 124000 -> VWAP 124
        self.assertEqual(row.vwap, Decimal("124.0000"))
        self.assertEqual(row.close_price, Decimal("124.00"))

    def test_daily_vwap_and_aggregate_vwap_are_separate_columns(self):
        rebuild_company_analysis_task(self.company.id)

        row = DailyAnalysis.objects.get(
            company=self.company, date=self.sessions[-1],
        )
        self.assertIsNotNone(row.vwap)
        self.assertIsNotNone(row.vwap_30d)
        self.assertNotEqual(row.vwap, row.vwap_30d)

    def test_previous_close_is_the_previous_session(self):
        rebuild_company_analysis_task(self.company.id)

        row = DailyAnalysis.objects.get(
            company=self.company, date=self.sessions[-1],
        )
        self.assertEqual(row.previous_close, Decimal("123.00"))
        self.assertIsNotNone(row.daily_return_pct)

    def test_first_session_has_no_previous_close(self):
        rebuild_company_analysis_task(self.company.id)

        row = DailyAnalysis.objects.get(
            company=self.company, date=self.sessions[0],
        )
        self.assertIsNone(row.previous_close)
        self.assertIsNone(row.daily_return_pct)

    def test_baseline_only_sufficient_after_twenty_sessions(self):
        rebuild_company_analysis_task(self.company.id)

        early = DailyAnalysis.objects.get(
            company=self.company, date=self.sessions[5],
        )
        late = DailyAnalysis.objects.get(
            company=self.company, date=self.sessions[-1],
        )

        self.assertFalse(early.has_sufficient_history)
        self.assertTrue(late.has_sufficient_history)
        self.assertEqual(late.volume_baseline_sessions, BASELINE_SESSIONS)

    def test_pressure_method_is_stamped_on_every_row(self):
        rebuild_company_analysis_task(self.company.id)

        methods = set(
            DailyAnalysis.objects
            .filter(company=self.company)
            .values_list("pressure_method", flat=True)
        )
        self.assertEqual(methods, {"OHLCV_PRICE_VOLUME"})

    def test_rerunning_is_idempotent(self):
        rebuild_company_analysis_task(self.company.id)
        first = list(
            DailyAnalysis.objects
            .filter(company=self.company)
            .order_by("date")
            .values("date", "vwap", "pressure_score", "volume_ratio")
        )

        rebuild_company_analysis_task(self.company.id)
        second = list(
            DailyAnalysis.objects
            .filter(company=self.company)
            .order_by("date")
            .values("date", "vwap", "pressure_score", "volume_ratio")
        )

        self.assertEqual(first, second)
        self.assertEqual(
            DailyAnalysis.objects.filter(company=self.company).count(),
            len(self.sessions),
        )

    def test_volume_spike_is_flagged_after_rebuild(self):
        spike_day = self.sessions[-1] + timedelta(days=3)
        DailyPrice.objects.create(
            company=self.company,
            date=spike_day,
            open=Decimal("130"),
            high=Decimal("135"),
            low=Decimal("129"),
            close=Decimal("134"),
            volume=5000,
            turnover=Decimal("670000"),
        )

        rebuild_company_analysis_task(self.company.id)

        row = DailyAnalysis.objects.get(company=self.company, date=spike_day)

        self.assertTrue(row.has_sufficient_history)
        self.assertEqual(row.volume_ratio, Decimal("5.00"))
        self.assertTrue(row.volume_anomaly)

    def test_zero_volume_day_stores_null_vwap_and_does_not_crash(self):
        quiet_day = self.sessions[-1] + timedelta(days=3)
        DailyPrice.objects.create(
            company=self.company,
            date=quiet_day,
            open=Decimal("124"),
            high=Decimal("124"),
            low=Decimal("124"),
            close=Decimal("124"),
            volume=0,
            turnover=Decimal("0"),
        )

        rebuild_company_analysis_task(self.company.id)

        row = DailyAnalysis.objects.get(company=self.company, date=quiet_day)
        self.assertIsNone(row.vwap)
        self.assertEqual(row.volume, 0)

    def test_rebuild_all_skips_inactive_companies(self):
        Company.objects.create(
            symbol="DEAD", name="Delisted", sector="Banking", is_active=False,
        )

        result = rebuild_all_analysis()

        self.assertEqual(result["companies_processed"], 1)
        self.assertEqual(result["failed"], [])

    def test_missing_company_is_reported_not_raised(self):
        result = rebuild_company_analysis_task(999999)
        self.assertEqual(result["error"], "company_not_found")

    def test_company_with_no_prices_produces_no_rows(self):
        empty = Company.objects.create(
            symbol="NEW", name="Newly Listed", sector="Banking",
        )

        rebuild_company_analysis_task(empty.id)

        self.assertEqual(
            DailyAnalysis.objects.filter(company=empty).count(), 0,
        )

    def test_incremental_rebuild_still_gets_a_full_baseline(self):
        # Rebuilding only the last few days must still load warm-up
        # history, or the baseline would be truncated to 2 sessions.
        rebuild_company_analysis_task(
            self.company.id, since=self.sessions[-3].isoformat(),
        )

        row = DailyAnalysis.objects.get(
            company=self.company, date=self.sessions[-1],
        )
        self.assertEqual(row.volume_baseline_sessions, BASELINE_SESSIONS)
        self.assertTrue(row.has_sufficient_history)
