from datetime import date
from decimal import Decimal
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from apps.market_indices.models import CompanyDaily, IndexCalibration, IndexCheck, IndexDaily, MarketIndex
from apps.market_indices.services import index_replication as rep

D1, D2 = date(2026, 10, 13), date(2026, 10, 14)

# Field names as returned by NEPSE's company/list, today-price and security/{id} (2026-10-15).
COMPANIES = [
    {"id": 131, "symbol": "NABIL", "sectorName": "Commercial Banks", "instrumentType": "Equity", "status": "A"},
    {"id": 300, "symbol": "SCB", "sectorName": "Commercial Banks", "instrumentType": "Equity", "status": "A"},
    {"id": 357, "symbol": "PCBL", "sectorName": "Commercial Banks", "instrumentType": "Equity", "status": "A"},
    {"id": 900, "symbol": "BOKL", "sectorName": "Commercial Banks", "instrumentType": "Equity", "status": "D"},
    {"id": 901, "symbol": "NABILD87", "sectorName": "Commercial Banks",
     "instrumentType": "Non-Convertible Debentures", "status": "A"},
    {"id": 902, "symbol": "NBF2", "sectorName": "Commercial Banks", "instrumentType": "Mutual Funds", "status": "A"},
    {"id": 903, "symbol": "UPPER", "sectorName": "Hydro Power", "instrumentType": "Equity", "status": "A"},
]
SHARES = {"NABIL": (284098483, 118071330, "A"), "SCB": (100423684, 29915883, "A"),
          "PCBL": (209547818, 102678432, "B"), "NBF2": (100000000, 0, "Z"), "UPPER": (200000000, 100000000, "B")}


def price(symbol, day, close, prev, shares=None):
    shares = shares or SHARES[symbol][0]
    return {"businessDate": day.isoformat(), "symbol": symbol, "closePrice": close,
            "previousDayClosePrice": prev, "marketCapitalization": round(close * shares / 1e6, 2)}


PRICES = {
    D1: {"NABIL": price("NABIL", D1, 539.0, 537.1), "SCB": price("SCB", D1, 670.0, 668.0),
         "PCBL": price("PCBL", D1, 272.5, 270.0), "NBF2": price("NBF2", D1, 9.5, 9.4),
         "UPPER": price("UPPER", D1, 200.0, 198.0)},
    # PCBL does not trade on D2: its last close (D1) must be kept.
    D2: {"NABIL": price("NABIL", D2, 541.0, 539.0), "SCB": price("SCB", D2, 676.5, 670.0),
         "NBF2": price("NBF2", D2, 9.6, 9.5), "UPPER": price("UPPER", D2, 202.0, 200.0)},
}


class FakeSource:
    def __init__(self, prices=PRICES, shares=SHARES, last_trade=None, broken=()):
        self.prices, self.shares, self.broken = prices, shares, broken
        self.last_trade = last_trade or {"PCBL": ("2026-10-13", 272.5)}

    def company_list(self):
        return COMPANIES

    def day_prices(self, day):
        return self.prices.get(day, {})

    def security_detail(self, security_id, symbol):
        if symbol in self.broken:
            raise rep.ReplicationError(f"NEPSE security detail for {symbol} returned nothing usable")
        listed, public, group = self.shares[symbol]
        traded_on, close = self.last_trade.get(symbol, ("2026-10-14", 1.0))
        return {"stockListedShares": float(listed), "publicShares": public,
                "security": {"symbol": symbol, "shareGroupId": {"name": group}},
                "securityDailyTradeDto": {"businessDate": traded_on, "closePrice": close}}


def banking_mcap(day):
    return sum(Decimal(str(PRICES[D1 if day == D1 or s not in PRICES[day] else day][s]["closePrice"]))
               * SHARES[s][0] for s in ("NABIL", "SCB", "PCBL"))


class ReplicationTests(TestCase):

    def setUp(self):
        call_command("seed_market_indices", stdout=mock.Mock())
        self.banking = MarketIndex.objects.get(code="BANKING")
        for day in (D1, D2):
            rep.snapshot_company_daily(day, source=FakeSource())

    def publish(self, day, close, code="BANKING"):
        IndexDaily.objects.create(index=MarketIndex.objects.get(code=code), date=day, close=close)

    def test_snapshot_keeps_active_equities_and_funds_with_normalised_sectors(self):
        rows = {r.symbol: r for r in CompanyDaily.objects.filter(date=D1)}
        self.assertEqual(set(rows), {"NABIL", "SCB", "PCBL", "NBF2", "UPPER"})  # no delisted, no debenture
        self.assertEqual(rows["NABIL"].sector, "Banking")
        self.assertEqual(rows["UPPER"].sector, "HydroPower")
        self.assertEqual(rows["NBF2"].sector, "Mutual Fund")  # filed under its sponsor bank by NEPSE
        self.assertEqual((rows["NABIL"].listed_shares, rows["NABIL"].public_shares, rows["NABIL"].share_class),
                         (284098483, 118071330, "A"))

    def test_untraded_security_keeps_its_last_close(self):
        pcbl = CompanyDaily.objects.get(date=D2, symbol="PCBL")
        self.assertFalse(pcbl.traded)
        self.assertEqual((pcbl.close, pcbl.prev_close), (Decimal("272.50"), Decimal("272.50")))

    def test_market_cap_is_close_times_listed_shares_of_members_only(self):
        self.assertEqual(rep.market_cap(D1, "BANKING"), banking_mcap(D1))
        self.assertEqual(rep.market_cap(D2, "BANKING"), banking_mcap(D2))

    def test_membership_rules(self):
        self.assertEqual({r.symbol for r in rep.constituents(D1, "SENSITIVE")}, {"NABIL", "SCB"})
        self.assertEqual({r.symbol for r in rep.constituents(D1, "NEPSE")}, {"NABIL", "SCB", "PCBL", "UPPER"})
        self.assertEqual({r.symbol for r in rep.constituents(D1, "MUTUAL")}, {"NBF2"})
        self.assertEqual(rep.market_cap(D1, "SENSITIVE_FLOAT"),
                         Decimal("539.0") * 118071330 + Decimal("670.0") * 29915883)

    def test_calibrate_then_compute_on_another_day(self):
        self.publish(D1, Decimal("1543.23"))
        calibration = rep.calibrate("BANKING", D1)
        self.assertEqual(calibration.constituents, 3)
        self.assertEqual((rep.market_cap(D1, "BANKING") * calibration.k).quantize(Decimal("0.01")),
                         Decimal("1543.23"))
        expected = (Decimal("1543.23") * banking_mcap(D2) / banking_mcap(D1)).quantize(Decimal("0.01"))
        self.assertEqual(rep.compute_index(D2, "BANKING"), expected)

    def test_verify_stores_difference_and_flags_above_half_a_point(self):
        self.publish(D1, Decimal("1543.23"))
        rep.calibrate("BANKING", D1)
        computed = rep.compute_index(D2, "BANKING")
        self.publish(D2, computed + Decimal("0.40"))
        check = rep.verify_day(D2)[0]
        self.assertEqual((check.diff, check.flagged, check.needs_recalibration), (Decimal("-0.40"), False, False))

        IndexDaily.objects.filter(index=self.banking, date=D2).update(close=computed - Decimal("0.60"))
        check = rep.verify_index(D2, "BANKING")
        self.assertTrue(check.flagged)
        self.assertEqual(IndexCheck.objects.count(), 1)  # re-running updates the day's row

    def test_listed_share_change_flags_recalibration(self):
        self.publish(D1, Decimal("1543.23"))
        rep.calibrate("BANKING", D1)
        bonus = dict(SHARES, SCB=(110466052, 29915883, "A"))  # 10% bonus listed on D2
        prices = {D2: dict(PRICES[D2], SCB=price("SCB", D2, 676.5, 670.0, shares=110466052))}
        rep.snapshot_company_daily(D2, source=FakeSource(prices=prices, shares=bonus))
        self.publish(D2, Decimal("1565.68"))
        check = rep.verify_index(D2, "BANKING")
        self.assertTrue(check.needs_recalibration)
        self.assertIn("SCB listed_shares 100,423,684 -> 110,466,052", check.recalibration_reason)

    def test_past_day_uses_shares_implied_by_same_day_market_cap(self):
        # The detail endpoint only has today's count (after a bonus); D1's NEPSE market cap has the old one.
        bonus = dict(SHARES, SCB=(110466052, 29915883, "A"))
        rep.snapshot_company_daily(D1, source=FakeSource(shares=bonus))
        scb = CompanyDaily.objects.get(date=D1, symbol="SCB")
        self.assertEqual(scb.listed_shares_source, CompanyDaily.SHARES_SAME_DAY_MCAP)
        self.assertAlmostEqual(scb.listed_shares, 100423684, delta=10)

    def test_failed_detail_saves_nothing_for_the_day(self):
        CompanyDaily.objects.all().delete()
        with self.assertRaises(rep.ReplicationError):
            rep.snapshot_company_daily(D1, source=FakeSource(broken=("SCB",)))
        self.assertFalse(CompanyDaily.objects.exists())

    def test_non_trading_day_raises(self):
        with self.assertRaisesMessage(rep.ReplicationError, "no end-of-day prices"):
            rep.snapshot_company_daily(date(2026, 10, 17), source=FakeSource())

    def test_missing_published_close_or_calibration_is_logged_not_raised_by_the_job(self):
        self.assertEqual(rep.verify_day(D2, ["BANKING"])[0]["index"], "BANKING")  # no calibration
        self.publish(D1, Decimal("1543.23"))
        rep.calibrate("BANKING", D1)
        result = rep.verify_day(D2)[0]  # D2 close not synced
        self.assertIn("not stored", result["error"])
        self.assertFalse(IndexCheck.objects.exists())

    def test_sectors_for(self):
        self.assertEqual(rep.sectors_for(["BANKING", "HYDROPOWER"]), ["Banking", "HydroPower"])
        self.assertIsNone(rep.sectors_for(["BANKING", "SENSITIVE"]))
        self.assertEqual(IndexCalibration.objects.count(), 0)


class NepseSourceTests(SimpleTestCase):

    def test_unusable_detail_is_retried_after_a_fresh_login_then_raises(self):
        client = mock.Mock()
        client.get_security_details.side_effect = [[], {"stockListedShares": 5.0, "security": {}}]
        source = rep.NepseSource(client_factory=lambda: client, pause=lambda _: None)
        self.assertEqual(source.security_detail(357, "PCBL")["stockListedShares"], 5.0)

        client.get_security_details.side_effect = [{}, {}]
        with self.assertRaisesMessage(rep.ReplicationError, "PCBL (id 357)"):
            source.security_detail(357, "PCBL")

    def test_empty_company_list_raises(self):
        client = mock.Mock()
        client.get_company_list.return_value = {"message": "Unauthorized"}
        with self.assertRaisesMessage(rep.ReplicationError, "company list"):
            rep.NepseSource(client_factory=lambda: client).company_list()


class NepseClientTlsTests(SimpleTestCase):

    def test_client_verifies_tls_even_though_the_library_disables_it(self):
        from apps.market_data.services.live_prices import _nepse_client

        with mock.patch("nepse_data_api.Nepse.authenticate"):
            client = _nepse_client()
        self.assertIs(client.session.verify, True)
