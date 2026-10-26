import json
import tempfile
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.companies.models import Company, TrackedCompany
from apps.market_data.models import DailyPrice, QuarterlyReport, YearlyDPPS
from apps.market_data.services import quarterly_metrics as m
from apps.market_data.services import quarterly_reports
from apps.market_indices.models import MarketStockDaily
from apps.users.models import User

D = Decimal
URL = "/api/market/quarterly-report/"


def report(**overrides):
    data = {"company": SimpleNamespace(symbol="NABIL", name="Nabil Bank"), "fiscal_year": "2082/2083", "quarter": 4,
            "reported_on": None, "net_profit": None, "net_worth": None, "distributable_profit": None,
            "share_count": None, "eps": D("30"), "book_value": D("200"), "dpps": D("8.82")}
    return SimpleNamespace(**{**data, **overrides})


class RatioTests(SimpleTestCase):

    def test_yield(self):
        self.assertEqual(m.calc_yield(8.82, 339.30), D("2.60"))
        self.assertEqual(m.calc_yield(14.41, 339.30), D("4.25"))
        self.assertIsNone(m.calc_yield(5, 0))
        self.assertIsNone(m.calc_yield(5, None))
        self.assertEqual(m.calc_yield(-3, 300), D("-1.00"))        # negative DPPS keeps its sign

    def test_pe_pb_not_meaningful_for_non_positive_denominator(self):
        self.assertEqual(m.calc_pe(339.30, 30), D("11.31"))
        self.assertIsNone(m.calc_pe(339.30, -4.5))
        self.assertIsNone(m.calc_pe(339.30, 0))
        self.assertIsNone(m.calc_pe(None, 30))
        self.assertEqual(m.calc_pb(339.30, 200), D("1.70"))
        self.assertIsNone(m.calc_pb(339.30, -1))


class AverageTests(SimpleTestCase):

    def test_window_limits_to_newest_years(self):
        result = m.n_year_average([10, 20, 30, 1000])
        self.assertEqual((result.average, result.years_used), (D("20.00"), 3))

    def test_fewer_years_than_window_divides_by_years_present(self):
        result = m.n_year_average([10, None, 20])
        self.assertEqual((result.average, result.years_used), (D("15.00"), 2))

    def test_below_minimum_is_not_meaningful(self):
        result = m.n_year_average([10])
        self.assertEqual((result.average, result.years_used), (None, 1))
        self.assertIsNone(m.n_year_average([]).average)

    def test_negative_years_are_kept(self):
        self.assertEqual(m.n_year_average([12, -6, 3]).average, D("3.00"))

    def test_window_and_minimum_are_parameters(self):
        self.assertEqual(m.n_year_average([1, 2, 3, 4, 5], window=5, min_years=5).average, D("3.00"))

    def test_dpps_window_anchors_on_newest_year_on_file(self):
        by_year = {"2081/2082": 9, "2080/2081": 8, "2078/2079": 6, "2083/2084": 99}
        # Viewing 2082/83 Q2: 2082/83 has no full-year DPPS yet, 2083/84 is in the future.
        self.assertEqual(m.dpps_window(by_year, "2082/2083"), [9, 8, None])
        self.assertEqual(m.dpps_window({}, "2082/2083"), [])


class YoyTests(SimpleTestCase):

    def test_growth_and_decline(self):
        self.assertEqual(m.calc_yoy(30, 20), D("50.00"))
        self.assertEqual(m.calc_yoy(15, 20), D("-25.00"))
        self.assertEqual(m.calc_yoy(-5, 20), D("-125.00"))

    def test_missing_zero_or_negative_base(self):
        self.assertIsNone(m.calc_yoy(30, None))
        self.assertIsNone(m.calc_yoy(30, 0))
        self.assertIsNone(m.calc_yoy(30, -10))
        self.assertIsNone(m.calc_yoy(None, 10))


class RowTests(SimpleTestCase):

    def test_eps_derived_from_cumulative_profit_is_annualized(self):
        q2 = report(quarter=2, eps=None, net_profit=D("500000"), share_count=100000)
        self.assertEqual(m.report_eps(q2), D("10.00"))           # 5 per share for 6 months

    def test_per_share_figures_fall_back_to_raw_totals(self):
        raw = report(book_value=None, dpps=None, net_worth=D("25000000"), distributable_profit=D("-150000"),
                     share_count=100000)
        self.assertEqual((m.report_book_value(raw), m.report_dpps(raw)), (D("250.00"), D("-1.50")))

    def test_row_uses_ltp_and_previous_eps(self):
        row = m.build_report_row(report(), D("339.30"), {"2082/2083": D("8.82"), "2081/2082": D("5")},
                                 report(fiscal_year="2081/2082", eps=D("24")))
        self.assertEqual(row["dpps_yield"], D("2.60"))
        self.assertEqual((row["avg_dpps"], row["avg_years_used"]), (D("6.91"), 2))
        self.assertEqual(row["yoy"], D("25.00"))
        self.assertIsNone(m.build_report_row(report(), None, {})["pe"])


class QuarterlyReportApiTests(TestCase):

    def setUp(self):
        cache.clear()
        self.nabil = self.company("NABIL", "Commercial Bank")
        self.nica = self.company("NICA", "Commercial Bank")
        self.loss = self.company("LOSSB", "Commercial Bank")
        self.company("LATE", "Commercial Bank")                    # has not reported yet
        self.company("UPPER", "Hydropower")
        untracked = Company.objects.create(symbol="GONE", name="Untracked", sector="Commercial Bank")
        TrackedCompany.objects.create(company=untracked, is_tracked=False)

        self.file(self.nabil, eps="30", book_value="200", dpps="8.82")
        self.file(self.nabil, fiscal_year="2081/2082", eps="24", book_value="190", dpps="5")
        self.file(self.nica, eps="12", book_value="150", dpps="14.41")
        self.file(self.loss, eps="-4.5", book_value="-10", dpps="-2")
        self.file(self.loss, fiscal_year="2081/2082", eps="-1", book_value="10", dpps="1")
        self.file(self.nabil, quarter=3, eps="28")
        YearlyDPPS.objects.create(company=self.nabil, fiscal_year="2082/2083", dpps=D("8.82"))
        YearlyDPPS.objects.create(company=self.nabil, fiscal_year="2081/2082", dpps=D("5"))
        YearlyDPPS.objects.create(company=self.nabil, fiscal_year="2080/2081", dpps=D("-1"))
        YearlyDPPS.objects.create(company=self.nica, fiscal_year="2082/2083", dpps=D("14.41"))

        MarketStockDaily.objects.create(symbol="NABIL", date=date(2026, 10, 20), close=D("300"))
        MarketStockDaily.objects.create(symbol="NABIL", date=date(2026, 10, 22), close=D("339.30"))
        DailyPrice.objects.create(company=self.nica, date=date(2026, 10, 22), open=1, high=1, low=1,
                                  close=D("339.30"), volume=1, turnover=1, source="crawled")
        DailyPrice.objects.create(company=self.nica, date=date(2026, 10, 23), open=1, high=1, low=1,
                                  close=D("999"), volume=1, turnover=1, source="unverified")   # never used

        user = User.objects.create_user(username="qr-admin", email="qr-admin@example.test",
                                        password="unused-test-password", role=User.Role.ADMIN)
        self.client = APIClient()
        self.client.force_authenticate(user)

    def company(self, symbol, sector):
        company = Company.objects.create(symbol=symbol, name=f"{symbol} Ltd", sector=sector)
        TrackedCompany.objects.create(company=company)
        return company

    def file(self, company, fiscal_year="2082/2083", quarter=4, **figures):
        QuarterlyReport.objects.create(company=company, fiscal_year=fiscal_year, quarter=quarter,
                                       **{k: D(v) for k, v in figures.items()})

    def get(self, **params):
        return self.client.get(URL, {"sector": "BANKING", **params})

    def rows(self, response):
        return {row["symbol"]: row for row in json.loads(response.content)["results"]}

    def test_meta_counts_and_numbers_are_json_numbers(self):
        response = self.get(fiscal_year="2082/83", quarter="4")
        self.assertEqual(response.status_code, 200)
        meta = response.data["meta"]
        self.assertEqual({k: meta[k] for k in ("sector", "fiscal_year", "quarter", "reported_count",
                                                "total_companies", "avg_window")},
                         {"sector": "BANKING", "fiscal_year": "2082/2083", "quarter": 4, "reported_count": 3,
                          "total_companies": 4, "avg_window": 3})
        nabil = self.rows(response)["NABIL"]
        self.assertEqual((nabil["ltp"], nabil["pe"], nabil["pb"], nabil["dpps_yield"]), (339.3, 11.31, 1.7, 2.6))
        self.assertEqual((nabil["avg_dpps"], nabil["avg_years_used"], nabil["avg_yield"]), (4.27, 3, 1.26))

    def test_previous_year_lookup_and_not_meaningful_cases(self):
        rows = self.rows(self.get(fiscal_year="2082/2083", quarter="4"))
        self.assertEqual(rows["NABIL"]["yoy"], 25.0)
        self.assertEqual(rows["NICA"]["ltp"], 339.3)                     # crawled DailyPrice, not unverified
        self.assertEqual(rows["NICA"]["dpps_yield"], 4.25)
        self.assertIsNone(rows["NICA"]["yoy"])                           # no report last year
        self.assertIsNone(rows["NICA"]["avg_dpps"])                      # 1 year < minimum
        loss = rows["LOSSB"]
        self.assertEqual((loss["pe"], loss["pb"], loss["yoy"], loss["ltp"]), (None, None, None, None))
        self.assertEqual(loss["dpps"], -2.0)

    def test_defaults_to_latest_period(self):
        meta = self.get().data["meta"]
        self.assertEqual((meta["fiscal_year"], meta["quarter"]), ("2082/2083", 4))
        meta = self.get(fiscal_year="2082/83", quarter="3").data["meta"]
        self.assertEqual(meta["reported_count"], 1)

    def test_price_is_fresh_while_filed_figures_are_cached(self):
        self.get()
        MarketStockDaily.objects.create(symbol="NABIL", date=date(2026, 10, 23), close=D("600"))
        self.assertEqual(self.rows(self.get())["NABIL"]["pe"], 20.0)

    def test_bad_params(self):
        for params in ({"sector": "BANK"}, {"sector": ""}, {"fiscal_year": "2082"}, {"fiscal_year": "2082/2084"},
                       {"fiscal_year": "82/83"}, {"quarter": "5"}, {"quarter": "x"}):
            response = self.client.get(URL, {"sector": "BANKING", **params})
            self.assertEqual(response.status_code, 400, params)
            self.assertIn("detail", response.data)

    def test_periods(self):
        response = self.client.get(URL + "periods/", {"sector": "banking"})
        self.assertEqual(response.data["periods"], [{"fiscal_year": "2082/2083", "quarters": [4, 3]},
                                                    {"fiscal_year": "2081/2082", "quarters": [4]}])
        self.assertEqual(self.client.get(URL + "periods/", {"sector": "nope"}).status_code, 400)

    def test_requires_login(self):
        self.assertIn(APIClient().get(URL, {"sector": "BANKING"}).status_code, (401, 403))


class ImportCommandTests(TestCase):

    HEADER = "symbol,fiscal_year,quarter,reported_on,net_profit,share_count,eps,book_value,dpps\n"

    def setUp(self):
        for symbol, sector in (("NABIL", "Commercial Bank"), ("UPPER", "Hydropower")):
            TrackedCompany.objects.create(company=Company.objects.create(symbol=symbol, name=symbol, sector=sector))

    def run_import(self, body, *args):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "reports.csv"
            path.write_text(self.HEADER + body, encoding="utf-8")
            out, err = StringIO(), StringIO()
            call_command("import_quarterly_reports", "--file", str(path), *args, stdout=out, stderr=err)
        return out.getvalue(), err.getvalue()

    def test_reimport_updates_instead_of_duplicating(self):
        self.run_import("nabil,2082/83,4,2026-08-10,\"1,00,000\",1000,30,200,8.82\n")
        out, _ = self.run_import("NABIL,2082/2083,4,2026-09-01,,,31.5,201,9\n")
        self.assertIn("0 created, 1 updated", out)
        saved = QuarterlyReport.objects.get()
        self.assertEqual((saved.eps, saved.net_profit, saved.reported_on), (D("31.50"), None, date(2026, 9, 1)))
        self.assertEqual(YearlyDPPS.objects.get().dpps, D("9.00"))      # Q4 fills the yearly DPPS

    def test_invalid_rows_are_skipped_with_reason(self):
        out, err = self.run_import(
            "NABIL,2082/83,5,,,,1,1,1\n"
            "NABIL,2082-83,1,,,,1,1,1\n"
            "NABIL,2082/83,1,,,,abc,1,1\n"
            "NABIL,2082/83,1,10/08/2026,,,1,1,1\n"
            "NABIL,2082/83,1,,,12.5,1,1,1\n"
            "XYZ,2082/83,1,,,,1,1,1\n"
            "NABIL,2082/83,1,,,,-2.5,1,1\n"
        )
        self.assertIn("1 created, 0 updated, 6 skipped", out)
        for reason in ("quarter must be 1-4", "fiscal_year must look like", "eps is not a number",
                       "reported_on must use", "share_count must be", "XYZ is not an active tracked company"):
            self.assertIn(reason, err)
        self.assertEqual(QuarterlyReport.objects.get().eps, D("-2.50"))

    def test_dry_run_and_sector_filter(self):
        body = "NABIL,2082/83,4,,,,30,200,8\nUPPER,2082/83,4,,,,5,110,1\n"
        out, _ = self.run_import(body, "--dry-run")
        self.assertIn("dry run", out)
        self.assertFalse(QuarterlyReport.objects.exists() or YearlyDPPS.objects.exists())
        self.run_import(body, "--sector", "HYDROPOWER")
        self.assertEqual(list(QuarterlyReport.objects.values_list("company__symbol", flat=True)), ["UPPER"])

    def test_import_invalidates_cached_report(self):
        self.run_import("NABIL,2082/83,4,,,,30,200,8\n")
        self.assertEqual(quarterly_reports.quarterly_report("BANKING")["results"][0]["eps"], D("30"))
        self.run_import("NABIL,2082/83,4,,,,35,200,8\n")
        self.assertEqual(quarterly_reports.quarterly_report("BANKING")["results"][0]["eps"], D("35"))
