from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.test import TestCase

from apps.companies.models import Company
from apps.market_data.models import DailyPrice
from apps.market_data.services.trading_days import is_trading_weekday
from apps.market_intelligence.models import CompanyTechnicalSnapshot, SectorRotationSnapshot
from apps.market_intelligence.services.sector_rotation import compute_sector_rotation_snapshots
from apps.market_intelligence.services.technicals import _pattern_matches, compute_company_technical_snapshots


class TechnicalSnapshotTests(TestCase):
    def setUp(self):
        self.bank = Company.objects.create(symbol="BANK", name="Bank Co", sector="Banking")
        self.hydro = Company.objects.create(symbol="HYDRO", name="Hydro Co", sector="Hydropower")
        self.start = date(2025, 1, 6)  # Monday (NEPSE trades Mon-Fri)

    @staticmethod
    def market_days(start, count):
        days = []
        day = start
        while len(days) < count:
            if is_trading_weekday(day):
                days.append(day)
            day += timedelta(days=1)
        return days

    def add_price(self, company, day, close, index, volume=None):
        close = Decimal(str(close))
        return DailyPrice.objects.create(
            company=company, source="crawled", date=day,
            open=close, high=close + 1, low=close - 1, close=close,
            volume=volume if volume is not None else 100 + index,
            turnover=Decimal(1000 + index),
        )

    def test_levels_dma_and_breakout_require_real_window_history(self):
        days = self.market_days(self.start, 200)
        for index, day in enumerate(days):
            close = Decimal("100") + Decimal(index) / 10
            self.add_price(self.bank, day, close, index)
        compute_company_technical_snapshots()

        row = CompanyTechnicalSnapshot.objects.get(company=self.bank, date=days[-1])
        self.assertTrue(row.sufficient_history)
        self.assertIsNotNone(row.support_20)
        self.assertIsNotNone(row.resistance_60)
        self.assertIsNotNone(row.dma_50)
        self.assertIsNotNone(row.dma_200)
        self.assertIsNotNone(row.breakout_20_up)

    def test_corporate_action_day_has_no_technical_levels_or_signal(self):
        days = self.market_days(self.start, 3)
        for index, (day, close) in enumerate(zip(days, (100, 120, 121))):
            self.add_price(self.bank, day, close, index)
        compute_company_technical_snapshots()

        row = CompanyTechnicalSnapshot.objects.get(company=self.bank, date=days[1])
        self.assertTrue(row.possible_corporate_action)
        self.assertEqual(row.signal, "possible_corporate_action")
        self.assertIsNone(row.support_20)
        self.assertIsNone(row.breakout_20_up)
        self.assertEqual(row.patterns, [])

    def test_pattern_list_uses_documented_candle_rules(self):
        doji = SimpleNamespace(open=Decimal("10"), high=Decimal("12"), low=Decimal("8"), close=Decimal("10.1"))
        self.assertIn("doji", _pattern_matches([doji]))
        hammer = SimpleNamespace(open=Decimal("10"), high=Decimal("10.5"), low=Decimal("7"), close=Decimal("10.2"))
        self.assertIn("hammer", _pattern_matches([hammer]))

    def test_sector_rotation_returns_and_rank_changes_are_materialized(self):
        days = self.market_days(self.start, 12)
        for index, day in enumerate(days):
            self.add_price(self.bank, day, Decimal("100") + index, index)
            self.add_price(self.hydro, day, Decimal("200") - index, index)
        compute_sector_rotation_snapshots()

        bank = SectorRotationSnapshot.objects.get(sector="Banking", date=days[-1])
        hydro = SectorRotationSnapshot.objects.get(sector="Hydropower", date=days[-1])
        self.assertEqual(bank.rank_1w, 1)
        self.assertEqual(hydro.rank_1w, 2)
        self.assertEqual(bank.previous_rank_1w, 1)
        self.assertGreater(bank.return_1w, 0)
        self.assertLess(hydro.return_1w, 0)
