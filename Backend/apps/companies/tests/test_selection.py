from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.companies.models import Company, TrackedCompany
from apps.companies.services.selection import parse_symbols, select_crawl_companies


class CrawlSelectionTests(TestCase):

    def setUp(self):
        def company(symbol, active=True, tracked=True):
            row = Company.objects.create(symbol=symbol, name=symbol, sector="Banking", is_active=active)
            TrackedCompany.objects.create(company=row, is_tracked=tracked)
            return row

        company("AAA")
        company("BBB")
        company("OFF", active=False)
        company("UNT", tracked=False)
        Company.objects.create(symbol="NOTRACK", name="no tracking row", sector="Banking")

    def test_only_active_and_tracked(self):
        companies, unknown = select_crawl_companies()
        self.assertEqual(list(companies.values_list("symbol", flat=True)), ["AAA", "BBB"])
        self.assertEqual(unknown, [])

    def test_symbols_filter_resolves_against_database(self):
        companies, unknown = select_crawl_companies(" bbb, OFF ,UNT,ZZZ,")
        self.assertEqual(list(companies.values_list("symbol", flat=True)), ["BBB"])
        self.assertEqual(unknown, ["OFF", "UNT", "ZZZ"])  # never crawled

    def test_parse_symbols(self):
        self.assertEqual(parse_symbols("mnbbl, GUFL,,gufl"), ["GUFL", "MNBBL"])
        self.assertEqual(parse_symbols(None), [])


class SeedCompaniesTests(TestCase):

    def run_seed(self):
        call_command("seed_companies", stdout=StringIO())

    def test_creates_twenty_tracked_companies_idempotently(self):
        self.run_seed()
        self.run_seed()
        self.assertEqual(Company.objects.count(), 20)
        self.assertEqual(TrackedCompany.objects.filter(is_tracked=True).count(), 20)
        ntc = Company.objects.get(symbol="NTC")
        self.assertEqual(ntc.sector, "Others")
        self.assertIn("Nepal Telecom", ntc.aliases)

    def test_rerun_never_alters_an_existing_company(self):
        nabil = Company.objects.create(symbol="NABIL", name="Edited name", sector="Edited", aliases=["x"], is_active=True)
        TrackedCompany.objects.create(company=nabil, is_tracked=False)
        self.run_seed()
        nabil.refresh_from_db()
        self.assertEqual((nabil.name, nabil.sector, nabil.aliases), ("Edited name", "Edited", ["x"]))
        self.assertFalse(nabil.tracking.is_tracked)
        self.assertEqual(Company.objects.filter(symbol="NABIL").count(), 1)
