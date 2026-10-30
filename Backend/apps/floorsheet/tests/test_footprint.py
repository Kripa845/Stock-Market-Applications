"""Trade filters (odd lots, pre-open, untimed), the footprint rules, quality checks and the trade-time backfill."""

import json
import tempfile
from datetime import date, datetime, timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.companies.models import Company
from apps.floorsheet.models import FloorsheetTransaction
from apps.floorsheet.services import floorsheet_quality, trade_time_backfill
from apps.floorsheet.services.footprint import footprint, price_row
from apps.floorsheet.services.trade_filters import (
    board_lots, continuous_session, is_odd_lot, is_pre_open, pre_open, untimed_company_days,
)
from apps.market_data.models import DailyPrice

NPT = ZoneInfo("Asia/Kathmandu")
DAY = date(2026, 10, 9)
D = Decimal


def at(hour, minute, second=0, day=DAY):
    return datetime(day.year, day.month, day.day, hour, minute, second, tzinfo=NPT)


class FloorsheetCase(TestCase):
    def setUp(self):
        self.company = Company.objects.create(symbol="NABIL", name="Nabil Bank", sector="Banking")
        self.seq = 0

    def trade(self, when, rate, quantity, day=DAY, company=None):
        self.seq += 1
        return FloorsheetTransaction.objects.create(
            company=company or self.company, date=day, trade_time=when,
            transaction_id=f"{day:%Y%m%d}01{self.seq:06d}", buyer_broker="1", seller_broker="2",
            quantity=quantity, rate=D(rate), amount=D(rate) * quantity,
        )


class TradeFilterTests(FloorsheetCase):
    def test_odd_lots_and_board_lots(self):
        self.trade(at(11, 5), "500", 9)
        self.trade(at(11, 6), "501", 10)
        self.assertTrue(is_odd_lot(9))
        self.assertFalse(is_odd_lot(10))
        self.assertEqual(list(board_lots(FloorsheetTransaction.objects.all()).values_list("quantity", flat=True)), [10])

    def test_pre_open_is_before_the_1100_open(self):
        self.assertTrue(is_pre_open(at(10, 46)))
        self.assertFalse(is_pre_open(at(11, 0)))
        self.assertFalse(is_pre_open(at(15, 0)))
        self.assertFalse(is_pre_open(None))
        self.trade(at(10, 46), "500", 100)
        self.trade(at(11, 0, 1), "501", 100)
        self.trade(None, "502", 100)
        trades = FloorsheetTransaction.objects.all()
        self.assertEqual(list(pre_open(trades).values_list("rate", flat=True)), [D("500")])
        self.assertEqual(list(continuous_session(trades).values_list("rate", flat=True)), [D("501")])

    def test_untimed_company_days(self):
        self.trade(at(11, 5), "500", 10)
        self.trade(None, "500", 10, day=DAY - timedelta(days=1))
        self.assertEqual(untimed_company_days(), [(self.company.pk, DAY - timedelta(days=1))])
        self.assertEqual(untimed_company_days(start=DAY), [])


class FootprintTests(FloorsheetCase):
    def test_pre_open_is_its_own_group_and_never_classified(self):
        self.trade(at(10, 46), "500", 300)
        self.trade(at(11, 0, 5), "502", 100)
        fp = footprint(self.company, DAY, "5m")
        self.assertEqual(fp["pre_open"], {"volume": 300, "trades": 1, "levels": [
            {"price": D("500"), "buy": 0, "sell": 0, "unclassified": 300, "volume": 300, "delta": 0}]})
        bar = fp["bars"][0]
        self.assertEqual((bar["open"], bar["volume"], bar["unclassified"]), (D("502"), 100, 100))

    def test_tick_rule_carries_direction_across_bars(self):
        self.trade(at(11, 1), "500", 100)       # first trade: unclassified
        self.trade(at(11, 2), "501", 50)        # uptick: buy
        self.trade(at(11, 3), "501", 20)        # same price: still buy
        self.trade(at(11, 6), "500.5", 30)      # next 5m bar, downtick: sell
        self.trade(at(11, 7), "500.5", 10)      # carried: sell
        first, second = footprint(self.company, DAY, "5m")["bars"]
        self.assertEqual((first["buy"], first["sell"], first["unclassified"], first["delta"]), (70, 0, 100, 70))
        self.assertEqual((second["buy"], second["sell"], second["delta"]), (0, 40, -40))
        self.assertEqual(second["start"], at(11, 5))

    def test_bar_close_is_the_last_continuous_trade_not_the_official_close(self):
        DailyPrice.objects.create(company=self.company, date=DAY, open=D("500"), high=D("503"), low=D("499"),
                                  close=D("499.9"), volume=300, turnover=D("0"), source="crawled")
        self.trade(at(14, 50), "503", 100)
        self.trade(at(14, 59, 59), "501", 100)
        self.trade(at(15, 0), "502", 100)       # the 15:00:00 print closes the last bucket
        bar = footprint(self.company, DAY, "1h")["bars"][-1]
        self.assertEqual((bar["open"], bar["high"], bar["close"]), (D("503"), D("503"), D("502")))

    def test_odd_lots_are_left_out(self):
        self.trade(at(11, 1), "500", 100)
        self.trade(at(11, 2), "480", 5)
        bar = footprint(self.company, DAY, "5m")["bars"][0]
        self.assertEqual((bar["low"], bar["volume"], bar["trades"]), (D("500"), 100, 1))

    def test_price_rows(self):
        self.assertEqual(price_row(D("340.17"), D("0.1")), D("340.1"))
        self.assertEqual(price_row(D("340.17"), D("0.5")), D("340.0"))
        self.trade(at(11, 1), "340.1", 10)
        self.trade(at(11, 2), "340.4", 20)
        self.trade(at(11, 3), "340.6", 30)
        levels = footprint(self.company, DAY, "15m", row_size="0.5")["bars"][0]["levels"]
        self.assertEqual([(lv["price"], lv["volume"]) for lv in levels], [(D("340.5"), 30), (D("340.0"), 30)])

    def test_untimed_day_is_one_daily_bar_in_contract_order(self):
        self.trade(None, "500", 100)
        self.trade(None, "499", 50)
        fp = footprint(self.company, DAY, "5m")
        self.assertTrue(fp["untimed"])
        self.assertIsNone(fp["pre_open"])
        [bar] = fp["bars"]
        self.assertEqual((bar["start"], bar["open"], bar["close"], bar["sell"], bar["unclassified"]),
                         (None, D("500"), D("499"), 50, 100))

    def test_bad_arguments(self):
        with self.assertRaises(ValueError):
            footprint(self.company, DAY, "2m")
        with self.assertRaises(ValueError):
            footprint(self.company, DAY, "5m", row_size=0)


class QualityTests(FloorsheetCase):
    def test_board_lot_high_low_matches_daily_price_on_99_percent_of_days(self):
        # 100 sessions; on half of them an odd lot prints below the official low, and one day is
        # genuinely off.  With odd lots left out, 99 of 100 days match.
        for i in range(100):
            day = DAY - timedelta(days=i)
            self.trade(at(11, 5, day=day), "500", 100, day=day)
            self.trade(at(12, 5, day=day), "505", 100, day=day)
            if i % 2:
                self.trade(at(13, 5, day=day), "490", 3, day=day)
            DailyPrice.objects.create(company=self.company, date=day, open=D("500"), high=D("505"),
                                      low=D("500") if i else D("499"), close=D("505"),
                                      volume=200 + (3 if i % 2 else 0), turnover=D("0"), source="crawled")
        board = floorsheet_quality.compare_with_daily_prices()
        everything = floorsheet_quality.compare_with_daily_prices(odd_lots=True)
        self.assertEqual(board["company_days"], 100)
        self.assertEqual(board["volume_matched"], 100)
        self.assertGreaterEqual(board["high_low_matched"] / board["company_days"], 0.99)
        self.assertEqual(everything["high_low_matched"], 49)

    def test_report_command_runs(self):
        self.trade(at(10, 46), "500", 100)
        self.trade(None, "500", 5)
        out = StringIO()
        call_command("floorsheet_quality_report", "--candles", stdout=out, stderr=out)
        self.assertIn("untimed (trade_time NULL): 1", out.getvalue())
        self.assertIn("pre-open auction fills", out.getvalue())


def sharehub_item(txn, quantity, rate, when="2026-10-09T13:05:07.250000Z", symbol="NABIL"):
    return {"contractId": txn, "symbol": symbol, "businessDate": "2026-10-09T00:00:00",
            "contractQuantity": quantity, "contractRate": rate, "tradeTime": when}


class TradeTimeBackfillTests(FloorsheetCase):
    def setUp(self):
        super().setUp()
        self.a = self.trade(None, "500", 100)
        self.b = self.trade(None, "501", 50)
        self.c = self.trade(None, "502", 10)
        self.items = [
            sharehub_item(self.a.transaction_id, 100, 500),
            sharehub_item(self.b.transaction_id, 55, 501),          # quantity differs: left alone
        ]                                                           # c is not at ShareHub

    def test_plan_matches_on_contract_quantity_and_rate(self):
        plan = trade_time_backfill.plan_company_day(self.company, DAY, fetch=lambda day, symbol: self.items)
        self.assertEqual(plan["untimed"], 3)
        self.assertEqual([(pk, when) for pk, _, when in plan["changes"]],
                         [(self.a.pk, datetime(2026, 10, 9, 13, 5, 7, 250000, tzinfo=NPT))])
        self.assertEqual(plan["mismatched"], [self.b.transaction_id])
        self.assertEqual(plan["missing"], [self.c.transaction_id])

    def test_apply_is_idempotent_and_never_overwrites_a_time(self):
        plan = trade_time_backfill.plan_company_day(self.company, DAY, fetch=lambda day, symbol: self.items)
        self.assertEqual(trade_time_backfill.apply_changes(plan["changes"]), 1)
        self.assertEqual(trade_time_backfill.apply_changes(plan["changes"]), 0)
        later = [(self.a.pk, self.a.transaction_id, at(14, 0))]
        self.assertEqual(trade_time_backfill.apply_changes(later), 0)
        self.a.refresh_from_db()
        self.assertEqual(self.a.trade_time, datetime(2026, 10, 9, 13, 5, 7, 250000, tzinfo=NPT))

    def test_command_dry_run_writes_nothing_then_apply_and_undo(self):
        fetch = mock.patch("apps.floorsheet.services.trade_time_backfill.fetch_company_day",
                           side_effect=lambda day, symbol: self.items)
        with tempfile.TemporaryDirectory() as tmp, override_settings(BASE_DIR=tmp), fetch, \
                mock.patch("apps.floorsheet.management.commands.fill_floorsheet_trade_times.time.sleep"):
            out = StringIO()
            call_command("fill_floorsheet_trade_times", stdout=out)
            self.assertIn("DRY RUN", out.getvalue())
            self.assertEqual(FloorsheetTransaction.objects.filter(trade_time__isnull=True).count(), 3)
            self.assertFalse((Path(tmp) / "backups").exists())

            call_command("fill_floorsheet_trade_times", "--apply", stdout=out)
            self.assertEqual(FloorsheetTransaction.objects.filter(trade_time__isnull=True).count(), 2)
            [backup] = (Path(tmp) / "backups").glob("floorsheet_trade_times_*.json")
            self.assertEqual([row["id"] for row in json.loads(backup.read_text())], [self.a.pk])

            call_command("fill_floorsheet_trade_times", "--undo", str(backup), stdout=out)   # dry run
            self.assertEqual(FloorsheetTransaction.objects.filter(trade_time__isnull=True).count(), 2)
            call_command("fill_floorsheet_trade_times", "--undo", str(backup), "--apply", stdout=out)
            self.assertEqual(FloorsheetTransaction.objects.filter(trade_time__isnull=True).count(), 3)
