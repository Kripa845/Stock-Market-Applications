import json
from decimal import Decimal
from io import StringIO

import requests
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from apps.companies.models import Company, TrackedCompany
from apps.reports.models import QuarterlyReport, YearlyDPPS
from apps.reports.services import nepsetrading

D = Decimal

ROWS = [
    {"symbol": "ADBL", "name": "Agricultural Development Bank Limited", "eps": 16.11, "book_value": 233.99,
     "pe": 19.18, "pb": 1.32, "dpps": 8.82, "dpps_avg5": 14.413999999999998, "dpps_avg5_years": 5,
     "dpps_yield": 2.66, "dpps_yoy": -43.39, "dpps_prev": 15.58, "ltp": 332.1},
    {"symbol": "HBL", "name": "Himalayan Bank Limited", "eps": 6.56, "book_value": 177.48, "pe": 29.67,
     "pb": 1.1, "dpps": -43.58, "dpps_avg5": -17.458, "dpps_avg5_years": 4, "dpps_yield": -21.57,
     "dpps_yoy": None, "dpps_prev": -32.79, "ltp": 202},
    {"symbol": "OTHER", "name": "Not tracked", "eps": 1, "book_value": 100, "dpps": 1, "dpps_avg5": 1,
     "dpps_avg5_years": 5, "dpps_prev": 1, "ltp": 100},
]


def page(rows=ROWS, period="Q4 2082/83"):
    """A page shaped like nepsetrading's: the flight data split across push() chunks."""
    payload = (f'1:["$","p",null,{{"children":[["$","strong",null,{{"children":"{period}"}}]," · ",19]}}]\n'
               f'2:["$","$L56",null,{{"rows":{json.dumps(rows)}}}]\n')
    middle = len(payload) // 2
    chunks = [payload[:middle], payload[middle:]]
    scripts = "".join(f"<script>self.__next_f.push([1,{json.dumps(chunk)}])</script>" for chunk in chunks)
    return f"<html><body><table></table>{scripts}</body></html>"


class ParsePageTests(SimpleTestCase):

    def test_period_and_rows(self):
        fiscal_year, quarter, rows = nepsetrading.parse_page(page())
        self.assertEqual((fiscal_year, quarter), ("2082/2083", 4))
        self.assertEqual([row["symbol"] for row in rows], ["ADBL", "HBL", "OTHER"])

    def test_missing_period_or_rows(self):
        with self.assertRaises(nepsetrading.PageError):
            nepsetrading.parse_page(page(period="Latest"))
        with self.assertRaises(nepsetrading.PageError):
            nepsetrading.parse_page("<html></html>")

    def test_row_defaults_round_and_drop_bad_years(self):
        defaults = nepsetrading.row_defaults({**ROWS[0], "dpps_avg5_years": 0}, None)
        self.assertEqual((defaults["dpps_avg"], defaults["previous_dpps"]), (D("14.41"), D("15.58")))
        self.assertIsNone(defaults["dpps_avg_years"])


class CrawlTests(TestCase):

    def setUp(self):
        for symbol in ("ADBL", "HBL", "UPPER"):
            company = Company.objects.create(symbol=symbol, name=symbol, sector="Commercial Bank")
            TrackedCompany.objects.create(company=company)

    def fetch(self, pages):
        def fetch(sector, session):
            if isinstance(pages.get(sector), Exception):
                raise pages[sector]
            return pages.get(sector, page(rows=[]))
        return fetch

    def test_saves_only_tracked_companies_and_keeps_csv_columns(self):
        adbl = Company.objects.get(symbol="ADBL")
        QuarterlyReport.objects.create(company=adbl, fiscal_year="2082/2083", quarter=4, net_profit=D("123"))

        results = nepsetrading.crawl(["BANKING"], fetch=self.fetch({"BANKING": page()}))

        self.assertEqual((results[0].created, results[0].updated, results[0].listed), (1, 1, 3))
        self.assertEqual(QuarterlyReport.objects.count(), 2)
        saved = QuarterlyReport.objects.get(company=adbl)
        self.assertEqual((saved.eps, saved.dpps, saved.dpps_avg, saved.dpps_avg_years, saved.previous_dpps),
                         (D("16.11"), D("8.82"), D("14.41"), 5, D("15.58")))
        self.assertEqual((saved.source, saved.net_profit), ("nepsetrading", D("123")))
        self.assertEqual(YearlyDPPS.objects.get(company=adbl).dpps, D("8.82"))        # Q4 fills the year

    def test_a_failing_page_does_not_stop_the_others(self):
        pages = {"BANKING": requests.ConnectionError("down"), "FINANCE": page(rows=ROWS[1:2], period="Q1 2083/84")}
        results = {r.sector: r for r in nepsetrading.crawl(["BANKING", "FINANCE"], fetch=self.fetch(pages))}
        self.assertEqual(results["BANKING"].error, "down")
        self.assertEqual(QuarterlyReport.objects.get().fiscal_year, "2083/2084")
        self.assertFalse(YearlyDPPS.objects.exists())                                  # not a Q4

    def test_dry_run_saves_nothing(self):
        nepsetrading.crawl(["BANKING"], dry_run=True, fetch=self.fetch({"BANKING": page()}))
        self.assertFalse(QuarterlyReport.objects.exists())

    def test_command_rejects_unknown_sector(self):
        with self.assertRaises(Exception):
            call_command("crawl_quarterly_reports", "--sector", "MUTUAL", stdout=StringIO())
