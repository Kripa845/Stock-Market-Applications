from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.test import TestCase

from apps.companies.models import Company
from apps.market_data.models import DailyPrice
from apps.market_data.services.trading_days import is_trading_weekday
from apps.market_intelligence.models import CompanyTechnicalSnapshot
from apps.market_intelligence.services import momentum
from apps.market_intelligence.services.momentum import (
    MIN_SESSIONS,
    compute_momentum_snapshots,
    macd,
    momentum_series,
    wilder_rsi,
)

# StockCharts' published Wilder RSI worked example (cs-rsi.xls).
WILDER_CLOSES = (
    "44.3389 44.0902 44.1497 43.6124 44.3278 44.8264 45.0955 45.4245 45.8433 46.0826 "
    "45.8931 46.0328 45.6140 46.2820 46.2820 46.0028 46.0328 46.4116 46.2222 45.6439"
).split()
WILDER_RSI = [Decimal(v) for v in ("70.53", "66.32", "66.55", "69.41", "66.36", "57.97")]


class FormulaTests(TestCase):
    def test_rsi_matches_wilder_reference(self):
        values = wilder_rsi(WILDER_CLOSES)
        self.assertEqual(values[:14], [None] * 14)
        self.assertEqual([v.quantize(Decimal("0.01")) for v in values[14:]], WILDER_RSI)

    def test_rsi_is_100_without_losses_and_null_without_movement(self):
        self.assertEqual(wilder_rsi([str(10 + i) for i in range(20)])[-1], Decimal("100"))
        self.assertIsNone(wilder_rsi(["10"] * 20)[-1])

    def test_macd_of_a_linear_series_is_the_lag_difference(self):
        # SMA-seeded EMA(N) of x_i = i lags by (N - 1) / 2, so MACD = 12.5 - 5.5 = 7 and the signal settles at 7.
        line, signal, hist = macd([str(i) for i in range(60)])
        self.assertIsNone(line[24])
        self.assertEqual(line[25], Decimal("7"))
        self.assertIsNone(signal[32])
        self.assertEqual(signal[33].quantize(Decimal("0.0001")), Decimal("7.0000"))
        self.assertEqual(hist[-1].quantize(Decimal("0.0001")), Decimal("0.0000"))

    def test_values_are_null_before_min_sessions(self):
        rows = momentum_series([str(100 + (i % 7)) for i in range(MIN_SESSIONS + 1)])
        self.assertTrue(all(v is None for row in rows[:MIN_SESSIONS - 1] for v in row.values()))
        self.assertIsNotNone(rows[MIN_SESSIONS - 1]["macd_signal"])


class SnapshotBackfillTests(TestCase):
    def setUp(self):
        self.companies = [Company.objects.create(symbol=s, name=s, sector="Hydropower") for s in ("AAA", "BBB")]
        day, sessions = date(2026, 6, 1), []
        while len(sessions) < 40:
            if is_trading_weekday(day):
                sessions.append(day)
            day += timedelta(days=1)
        for k, company in enumerate(self.companies):
            for i, session in enumerate(sessions):
                close = Decimal(100 + k * 10 + (i % 5) - (i % 3))
                DailyPrice.objects.create(company=company, source="crawled", date=session, open=close,
                                          high=close + 1, low=close - 1, close=close, volume=1000 + i,
                                          turnover=close * 1000)
                CompanyTechnicalSnapshot.objects.create(company=company, date=session)

    def test_backfill_fills_every_row_and_is_idempotent(self):
        first = compute_momentum_snapshots()
        self.assertEqual(first["rows_updated"], 2 * (40 - MIN_SESSIONS + 1))
        self.assertEqual(first["failed"], [])
        self.assertEqual(CompanyTechnicalSnapshot.objects.filter(rsi_14__isnull=True).count(), 2 * (MIN_SESSIONS - 1))
        latest = CompanyTechnicalSnapshot.objects.filter(company=self.companies[0]).order_by("-date").first()
        self.assertTrue(0 < latest.rsi_14 < 100)
        self.assertAlmostEqual(latest.macd_hist, latest.macd - latest.macd_signal, delta=Decimal("0.0002"))
        self.assertEqual(compute_momentum_snapshots()["rows_updated"], 0)

    def test_one_company_failing_does_not_stop_the_others(self):
        real = momentum.momentum_series
        calls = []

        def flaky(closes):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("boom")
            return real(closes)

        with mock.patch.object(momentum, "momentum_series", side_effect=flaky):
            result = compute_momentum_snapshots()
        self.assertEqual(result["failed"], [self.companies[0].id])
        self.assertTrue(CompanyTechnicalSnapshot.objects.filter(company=self.companies[1], rsi_14__isnull=False).exists())
