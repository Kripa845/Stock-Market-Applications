import math
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest import mock
from zoneinfo import ZoneInfo

from django.test import TestCase
from rest_framework.test import APIClient

from apps.companies.models import Company, TrackedCompany
from apps.comparison.services import compare as compare_service
from apps.comparison.services.compare import compare_companies, company_profile, parse_symbols, ComparisonError
from apps.comparison.services.coverage import coverage_report
from apps.floorsheet.models import Broker, FloorsheetTransaction
from apps.market_data.models import DailyPrice
from apps.market_data.services.trading_days import is_trading_weekday
from apps.market_intelligence.services.technicals import compute_company_technical_snapshots
from apps.reports.models import DividendAnnouncement, QuarterlyReport
from apps.users.models import CustomRole, User, UserCompanyAccess

NPT = ZoneInfo("Asia/Kathmandu")
LAST_SESSION = date(2026, 10, 29)
SESSIONS = 270            # > 365 calendar days, > 200 sessions
REASONS = {
    "no_data", "insufficient_history", "needs_more_quarterly_data", "no_source_column", "no_dividend_history",
    "negative_eps", "no_price", "possible_corporate_action", "not_computed", "no_price_movement",
    "non_positive_book_value", "missing_price", "missing_previous_session", "not_traded",
}

# symbol, sector, listed shares, eps, book value, (cash %, bonus %) or None
UNIVERSE = [
    ("ADBL", "Commercial Bank", 143055192, "16.11", "233.99", ("9.75", "3.25")),
    ("AKJCL", "Hydropower", 20000000, "3.18", "93.69", None),
    ("CBBL", "Microfinance", 36172643, "35.91", "251.06", ("12.5", "12.5")),
    ("CHCL", "Hydropower", 94849892, "7.59", "123.90", ("4", "8")),
    ("GUFL", "Finance", 8679938, "25.28", "167.43", ("5", "0")),
    ("HDL", "Manufacturing", 36880822, "32.71", "141.43", ("5", "20")),
    ("HIDCL", "Investment", 249282106, "2.73", "112.65", ("2", "1.5")),
    ("LICN", "Life Insurance", 55000000, "7.38", "177.87", ("21.05", "0")),
    ("MNBBL", "Development Bank", 80003890, "18.98", "161.82", ("4.67", "13.53")),
    ("NABIL", "Commercial Bank", 284098483, "27.74", "247.28", ("10.8", "5")),
    ("NICA", "Commercial Bank", 149175670, "1.22", "172.32", ("0", "0")),
    ("NLG", "Non Life Insurance", 26678336, "2.17", "166.36", ("3.3684", "4")),
    ("NLIC", "Life Insurance", 94802016, "4.91", "126.07", ("16.05", "5")),
    ("NTC", "Others", 180000000, "49.25", "557.54", ("30", "0")),
    ("SANIMA", "Commercial Bank", 135815256, "24.92", "188.42", ("10", "0")),
    ("SCB", "Commercial Bank", 100423684, "28.38", "225.77", ("19", "0")),
    ("SHIVM", "Manufacturing", 55932288, "14.03", "188.76", ("10", "2.5")),
    ("STC", "Trading", 3511851, "38.83", "507.67", ("0.5", "9.5")),
    ("TRH", "Hotels and Tourism", 19621202, "-35.97", "118.71", ("5", "0")),
    ("UPPER", "Hydropower", 211800000, "4.37", "44.48", None),
]
SYMBOLS = [row[0] for row in UNIVERSE]


def _sessions():
    days, day = [], LAST_SESSION
    while len(days) < SESSIONS:
        if is_trading_weekday(day):
            days.append(day)
        day -= timedelta(days=1)
    return days[::-1]


def build_universe():
    """20 tracked companies with ~13 months of prices, one Q4 report each, dividends for 18."""
    sessions = _sessions()
    for k, (symbol, sector, shares, eps, bv, dividend) in enumerate(UNIVERSE):
        company = Company.objects.create(symbol=symbol, name=f"{symbol} Ltd", sector=sector, listed_shares=shares)
        TrackedCompany.objects.create(company=company, is_tracked=True)
        base = Decimal(347) if symbol == "ADBL" else Decimal(150 + 40 * k)
        previous = None
        for i, day in enumerate(sessions):
            wave = Decimal(str(round(math.sin(i / 9 + k) * 0.08, 4)))
            close = (base * (1 + wave - Decimal("0.08") * Decimal(SESSIONS - 1 - i) / SESSIONS)).quantize(Decimal("0.01"))
            if i == len(sessions) - 1 and symbol == "ADBL":
                close = Decimal("347.00")
            change = ((close - previous) / previous * 100).quantize(Decimal("0.01")) if previous else None
            # HDL: a book closure 30 sessions ago; the source's % is against an adjusted previous close.
            if symbol == "HDL" and i == len(sessions) - 30:
                change = change + Decimal("15")
            DailyPrice.objects.create(
                company=company, source="crawled", date=day, open=close, high=close + 2, low=close - 2,
                close=close, volume=10000 + i * 10 + k, turnover=close * 10000, source_change_pct=change,
            )
            previous = close
        QuarterlyReport.objects.create(company=company, fiscal_year="2082/2083", quarter=4,
                                       eps=Decimal(eps), book_value=Decimal(bv), source="nepsetrading")
        if dividend:
            DividendAnnouncement.objects.create(
                symbol=symbol, company=company, company_name=company.name, fiscal_year="2081/2082",
                cash_pct=Decimal(dividend[0]), bonus_pct=Decimal(dividend[1]), face_value=Decimal("100"),
                status="distributed", source="ShareSansar", source_id=str(k),
            )
    # SANIMA's latest report is a Q1 with annualized EPS.
    QuarterlyReport.objects.create(company=Company.objects.get(symbol="SANIMA"), fiscal_year="2083/2084",
                                   quarter=1, eps=Decimal("26.11"), book_value=Decimal("185.54"))
    compute_company_technical_snapshots()


class ComparisonServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        build_universe()
        adbl = Company.objects.get(symbol="ADBL")
        for number, name in ((58, "Naasa"), (65, "Sharepro"), (33, "Dakshinkali")):
            Broker.objects.create(broker_no=number, broker_code=f"B{number}", name=name)
        for i, (buyer, seller, qty) in enumerate([("65", "33", 600), ("58", "33", 300), ("65", "58", 100)]):
            FloorsheetTransaction.objects.create(company=adbl, date=LAST_SESSION, transaction_id=f"T{i}",
                                                 buyer_broker=buyer, seller_broker=seller, quantity=qty,
                                                 rate=Decimal("347"), amount=Decimal("347") * qty)
        # Synthetic rows never count.
        FloorsheetTransaction.objects.create(company=adbl, date=LAST_SESSION, transaction_id="TX-1",
                                             buyer_broker="99", seller_broker="98", quantity=5000, rate=Decimal("347"))
        cls.profiles = {p["symbol"]: p for p in compare_companies(list(Company.objects.order_by("symbol")))}

    # ---- every company ----

    def test_database_universe_is_the_twenty_tracked_companies(self):
        self.assertEqual(sorted(self.profiles), sorted(SYMBOLS))

    def test_every_company_builds_and_every_null_has_a_reason(self):
        for symbol, profile in self.profiles.items():
            with self.subTest(symbol=symbol):
                self.assertNotIn("error", profile)
                listed = {entry["field"]: entry["reason"] for entry in profile["data_quality"]["null_fields"]}
                for section in ("general", "fundamentals", "technicals"):
                    for field, value in profile[section].items():
                        if value is None:
                            self.assertIn(f"{section}.{field}", listed)
                for reason in listed.values():
                    self.assertIn(reason, REASONS)
                self.assertEqual(profile["data_quality"]["price_as_of"], LAST_SESSION)
                self.assertEqual(profile["data_quality"]["snapshot_as_of"], LAST_SESSION)

    def test_sanity_across_all_companies(self):
        for symbol, profile in self.profiles.items():
            g, f, t = profile["general"], profile["fundamentals"], profile["technicals"]
            with self.subTest(symbol=symbol):
                if g["eps_ttm"] is not None and g["eps_ttm"] > 0:
                    self.assertGreater(f["pe"], 0)
                self.assertTrue(0 < t["rsi"] < 100)
                self.assertGreater(g["market_cap"], 0)
                self.assertLessEqual(g["week52_low"], g["ltp"])
                self.assertLessEqual(g["ltp"], g["week52_high"])
                if f["dividend"]:
                    d = f["dividend"]
                    self.assertEqual(d["total_pct"], d["cash_pct"] + d["bonus_pct"])
                self.assertIn(t["macd_label"], ("Bullish", "Bearish"))
                self.assertEqual(len(t["volume_trend"]), 10)
                self.assertIsNotNone(t["sma200"])

    def test_missing_source_columns_are_null_with_reason_never_zero(self):
        for profile in self.profiles.values():
            reasons = {e["field"]: e["reason"] for e in profile["data_quality"]["null_fields"]}
            for field in ("ps", "roa", "debt_equity"):
                self.assertIsNone(profile["fundamentals"][field])
                self.assertEqual(reasons[f"fundamentals.{field}"], "no_source_column")
            for field in ("yoy_profit_growth", "earning_trend_5q", "peg"):
                self.assertEqual(reasons[f"fundamentals.{field}"], "needs_more_quarterly_data")

    def test_sector_note_only_on_financial_companies(self):
        def note(symbol):
            entry = next(e for e in self.profiles[symbol]["data_quality"]["null_fields"]
                         if e["field"] == "fundamentals.debt_equity")
            return entry.get("note")
        self.assertIn("not comparable", note("ADBL"))
        self.assertIn("not comparable", note("NLIC"))
        self.assertIsNone(note("CHCL"))

    # ---- ADBL reference (LTP 347) ----

    def test_adbl_reference_figures(self):
        g, f = self.profiles["ADBL"]["general"], self.profiles["ADBL"]["fundamentals"]
        self.assertEqual(g["ltp"], Decimal("347.00"))
        self.assertAlmostEqual(float(g["market_cap"]) / 1e9, 49.64, delta=0.01)
        self.assertAlmostEqual(float(g["paid_up_capital"]) / 1e9, 14.31, delta=0.01)
        self.assertAlmostEqual(float(g["reserve_surplus"]) / 1e9, 19.17, delta=0.01)
        self.assertAlmostEqual(float(f["pe"]), 21.5, delta=0.1)
        self.assertAlmostEqual(float(f["pb"]), 1.5, delta=0.05)
        self.assertAlmostEqual(float(f["roe"]), 6.9, delta=0.05)
        self.assertEqual(f["dividend"]["cash_pct"], Decimal("9.75"))
        self.assertEqual(f["dividend"]["bonus_pct"], Decimal("3.25"))
        self.assertEqual(f["dividend"]["total_pct"], Decimal("13"))
        self.assertAlmostEqual(float(f["dividend_yield"]), 3.75, delta=0.02)
        self.assertEqual(g["face_value_source"], "dividend_announcement")

    def test_adbl_top_brokers_exclude_synthetic_rows(self):
        g = self.profiles["ADBL"]["general"]
        self.assertEqual(g["brokers_date"], LAST_SESSION)
        self.assertEqual([(b["broker_no"], b["quantity"]) for b in g["top_buy_brokers"]], [(65, 700), (58, 300)])
        self.assertEqual(g["top_buy_brokers"][0]["pct_of_day_volume"], Decimal("70.00"))
        self.assertEqual(g["top_sell_brokers"][0], {"broker_no": 33, "broker_name": "Dakshinkali",
                                                     "quantity": 900, "pct_of_day_volume": Decimal("90.00")})

    # ---- company-specific gaps, same code path ----

    def test_sanima_q1_has_no_ttm_eps(self):
        g, f = self.profiles["SANIMA"]["general"], self.profiles["SANIMA"]["fundamentals"]
        reasons = {e["field"]: e["reason"] for e in self.profiles["SANIMA"]["data_quality"]["null_fields"]}
        self.assertIsNone(g["eps_ttm"])
        self.assertEqual(reasons["general.eps_ttm"], "needs_more_quarterly_data")
        self.assertEqual(reasons["fundamentals.pe"], "needs_more_quarterly_data")
        self.assertEqual(g["eps_reported"], Decimal("26.11"))
        self.assertEqual(f["report_period"], "2083/2084 Q1")
        self.assertIsNotNone(f["pb"])

    def test_q1_ttm_eps_with_prior_year_quarters(self):
        sanima = Company.objects.get(symbol="SANIMA")
        QuarterlyReport.objects.create(company=sanima, fiscal_year="2082/2083", quarter=1, eps=Decimal("20.00"))
        # cum Q1 now 26.11/4 + prior Q4 24.92 - prior cum Q1 20/4
        eps, reason = compare_service.ttm_eps(sanima, QuarterlyReport.objects.get(company=sanima, fiscal_year="2083/2084"))
        self.assertIsNone(reason)
        self.assertEqual(eps, Decimal("26.11") / 4 + Decimal("24.92") - Decimal("5"))

    def test_companies_without_dividends(self):
        for symbol in ("AKJCL", "UPPER"):
            profile = self.profiles[symbol]
            reasons = {e["field"]: e["reason"] for e in profile["data_quality"]["null_fields"]}
            self.assertEqual(reasons["fundamentals.dividend"], "no_dividend_history")
            self.assertEqual(reasons["fundamentals.dividend_yield"], "no_dividend_history")
            self.assertEqual(profile["general"]["face_value_source"], "default_100")
            self.assertIsNotNone(profile["general"]["paid_up_capital"])

    def test_negative_eps_has_no_pe(self):
        reasons = {e["field"]: e["reason"] for e in self.profiles["TRH"]["data_quality"]["null_fields"]}
        self.assertEqual(reasons["fundamentals.pe"], "negative_eps")
        self.assertLess(self.profiles["TRH"]["fundamentals"]["roe"], 0)

    def test_unadjusted_bonus_is_reported(self):
        warning = next(w for w in self.profiles["HDL"]["data_quality"]["warnings"]
                       if w["code"] == "unadjusted_price_adjustment")
        fields = warning["sessions"][0]["fields"]
        self.assertIn("technicals.sma50", fields)
        self.assertIn("technicals.rsi", fields)
        self.assertIn("general.week52_high", fields)
        self.assertEqual(len(self.profiles["HDL"]["data_quality"]["price_adjustment_sessions"]), 1)

    def test_failure_in_one_company_does_not_break_the_others(self):
        real = compare_service.company_profile

        def flaky(company, *args, **kwargs):
            if company.symbol == "CHCL":
                raise RuntimeError("boom")
            return real(company, *args, **kwargs)

        with mock.patch.object(compare_service, "company_profile", side_effect=flaky):
            results = compare_companies(list(Company.objects.filter(symbol__in=["ADBL", "CHCL", "SCB"]).order_by("symbol")))
        self.assertEqual([r.get("error") for r in results], [None, "computation_failed", None])

    def test_live_feed_fallback_only_without_daily_prices(self):
        company = Company.objects.create(symbol="NOPRICE", name="No price", sector="Hydropower",
                                         ltp=Decimal("100"), previous_close=Decimal("98"))
        profile = company_profile(company)
        self.assertEqual(profile["general"]["ltp_source"], "company_live_feed")
        self.assertEqual(profile["general"]["change_pct"], Decimal("2.04"))
        reasons = {e["field"]: e["reason"] for e in profile["data_quality"]["null_fields"]}
        self.assertEqual(reasons["technicals.rsi"], "no_data")
        self.assertEqual(reasons["general.market_cap"], "no_data")

    def test_coverage_report_covers_all_twenty(self):
        report = coverage_report(now=datetime(2026, 10, 29, 19, 0, tzinfo=NPT))
        rows = {row["symbol"]: row for row in report["companies"]}
        self.assertEqual(sorted(rows), sorted(SYMBOLS))
        self.assertEqual(report["expected_latest_session"], LAST_SESSION)
        for symbol, row in rows.items():
            with self.subTest(symbol=symbol):
                self.assertEqual(row["price_sessions"], SESSIONS)
                self.assertEqual(row["sanity_checks_failed"], [])
                self.assertNotIn("stale_last_price", row["problems"])
        self.assertIn("no_dividend_record", rows["AKJCL"]["problems"])
        self.assertIn("unadjusted_bonus_in_lookback", rows["HDL"]["problems"])
        self.assertEqual(rows["SANIMA"]["quarters_in_quarterly_report"], 2)
        self.assertEqual(report["assumptions"]["quarterly_report_null_fields"]["ADBL"],
                         ["net_profit", "net_worth", "share_count"])

    def test_stale_price_after_a_missed_session(self):
        report = coverage_report(now=datetime(2026, 11, 1, 10, 0, tzinfo=NPT))   # Sunday; Friday 10-30 missing
        self.assertEqual(report["expected_latest_session"], date(2026, 10, 30))
        self.assertTrue(all("stale_last_price" in row["problems"] for row in report["companies"]))


class SymbolValidationTests(TestCase):
    def setUp(self):
        for symbol in ("ADBL", "CHCL", "SCB", "NABIL", "NICA", "NTC"):
            company = Company.objects.create(symbol=symbol, name=symbol, sector="Commercial Bank")
            TrackedCompany.objects.create(company=company, is_tracked=True)
        untracked = Company.objects.create(symbol="OLDCO", name="Old", sector="Finance")
        TrackedCompany.objects.create(company=untracked, is_tracked=False)

    def assertCode(self, raw, code):
        with self.assertRaises(ComparisonError) as ctx:
            parse_symbols(raw)
        self.assertEqual(ctx.exception.code, code)
        return ctx.exception

    def test_rules(self):
        self.assertEqual([c.symbol for c in parse_symbols("adbl, CHCL")], ["ADBL", "CHCL"])
        self.assertCode("", "symbols_required")
        self.assertCode("ADBL", "symbol_count")
        self.assertCode("ADBL,CHCL,SCB,NABIL,NICA,NTC", "symbol_count")
        self.assertCode("ADBL,adbl", "duplicate_symbols")
        self.assertEqual(self.assertCode("ADBL,XYZ,OLDCO", "unknown_symbols").details["invalid_symbols"], ["XYZ", "OLDCO"])


class ComparisonApiTests(TestCase):
    def setUp(self):
        self.companies = {}
        for symbol, sector in (("ADBL", "Commercial Bank"), ("CHCL", "Hydropower"), ("SCB", "Commercial Bank")):
            company = Company.objects.create(symbol=symbol, name=f"{symbol} Ltd", sector=sector, listed_shares=1000)
            TrackedCompany.objects.create(company=company, is_tracked=True)
            self.companies[symbol] = company
        self.admin = User.objects.create_user(username="cmp-admin", email="cmp-admin@example.test",
                                              password="unused-test-password", role=User.Role.ADMIN)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def _viewer(self, symbols):
        viewer = User.objects.create_user(username="cmp-viewer", email="cmp-viewer@example.test",
                                          password="unused-test-password", role=User.Role.VIEWER)
        viewer.custom_role = CustomRole.objects.create(name="Compare viewer", permissions=["view_analysis"])
        viewer.save(update_fields=["custom_role"])
        for symbol in symbols:
            UserCompanyAccess.objects.create(user=viewer, company=self.companies[symbol], status=1)
        client = APIClient()
        client.force_authenticate(viewer)
        return client

    def test_compare_returns_one_object_per_symbol_in_order(self):
        response = self.client.get("/api/compare/", {"symbols": "SCB,ADBL"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([r["symbol"] for r in response.data["results"]], ["SCB", "ADBL"])
        reasons = {e["field"]: e["reason"] for e in response.data["results"][0]["data_quality"]["null_fields"]}
        self.assertEqual(reasons["general.ltp"], "no_data")

    def test_compare_rejects_bad_requests(self):
        cases = {"ADBL": "symbol_count", "ADBL,ADBL": "duplicate_symbols", "ADBL,NOPE": "unknown_symbols"}
        for raw, code in cases.items():
            response = self.client.get("/api/compare/", {"symbols": raw})
            self.assertEqual((response.status_code, response.data["code"]), (400, code))
        response = self.client.get("/api/compare/", {"symbols": "ADBL,CHCL", "date": "29-10-2026"})
        self.assertEqual(response.data["code"], "invalid_date")

    def test_company_access_is_enforced(self):
        client = self._viewer(["ADBL"])
        response = client.get("/api/compare/", {"symbols": "ADBL,CHCL"})
        self.assertEqual((response.status_code, response.data["denied_symbols"]), (403, ["CHCL"]))
        picker = client.get("/api/compare/companies/")
        self.assertEqual([c["symbol"] for c in picker.data["results"]], ["ADBL"])
        coverage = client.get("/api/compare/coverage/")
        self.assertEqual([c["symbol"] for c in coverage.data["companies"]], ["ADBL"])

    def test_picker_lists_tracked_companies_and_filters_by_sector(self):
        response = self.client.get("/api/compare/companies/")
        self.assertEqual([c["symbol"] for c in response.data["results"]], ["ADBL", "CHCL", "SCB"])
        self.assertEqual(response.data["sectors"], ["Commercial Bank", "Hydropower"])
        hydro = self.client.get("/api/compare/companies/", {"sector": "hydropower"})
        self.assertEqual(hydro.data["results"], [{"symbol": "CHCL", "name": "CHCL Ltd", "sector": "Hydropower"}])

    def test_requires_authentication(self):
        self.assertIn(APIClient().get("/api/compare/", {"symbols": "ADBL,CHCL"}).status_code, (401, 403))
