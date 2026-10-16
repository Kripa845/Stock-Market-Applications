import importlib
import json
import sys
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.companies.models import Company
from apps.market_data.models import CompanyEarnings, DailyPrice, DividendAnnouncement
from apps.market_data.services import dividends
from apps.market_indices.models import MarketStockDaily
from apps.users.models import User

TODAY = date(2026, 10, 15)
Status = DividendAnnouncement.Status


def row(**overrides):
    data = {
        "symbol": "BHDC", "company_name": "Bindhyabasini Hydropower", "fiscal_year": "2082/2083",
        "source_id": "766", "bonus_pct": Decimal("5.00"), "cash_pct": Decimal("0.2632"),
        "announcement_date": date(2026, 10, 14), "book_closure_date": date(2026, 10, 27),
        "distribution_date": None, "bonus_listing_date": None,
    }
    return {**data, **overrides}


class FiscalYearTests(SimpleTestCase):

    def test_spellings(self):
        for text in ("2081/2082", "2081/82", "081-082", "FY:081-082", " 81/82 "):
            self.assertEqual(dividends.normalise_fiscal_year(text), "2081/2082", text)

    def test_rejects_non_consecutive_and_garbage(self):
        for text in ("2081/2083", "", None, "N/A", "2081"):
            self.assertEqual(dividends.normalise_fiscal_year(text), "", text)


class UpsertTests(TestCase):

    def upsert(self, **overrides):
        return dividends.upsert_dividend(row(**overrides), source="ShareSansar", today=TODAY)

    def test_rerun_updates_not_duplicates(self):
        self.assertEqual(self.upsert(), "created")
        self.assertEqual(self.upsert(cash_pct=Decimal("1"), fiscal_year="2082/83"), "updated")
        saved = DividendAnnouncement.objects.get()
        self.assertEqual((saved.fiscal_year, saved.cash_pct, saved.missing_fields), ("2082/2083", Decimal("1"), []))

    def test_links_company_when_symbol_is_ours(self):
        company = Company.objects.create(symbol="BHDC", name="Bindhyabasini", sector="Hydro")
        self.upsert(symbol="bhdc")
        self.assertEqual(DividendAnnouncement.objects.get().company, company)

    def test_status_from_dates(self):
        cases = [
            ({}, Status.PROPOSED),                                                   # book closure ahead
            ({"book_closure_date": None}, Status.PROPOSED),
            ({"book_closure_date": date(2026, 10, 1)}, Status.AGM_APPROVED),
            ({"book_closure_date": date(2026, 9, 1), "bonus_listing_date": date(2026, 10, 2)}, Status.DISTRIBUTED),
            ({"book_closure_date": date(2026, 9, 1), "bonus_listing_date": date(2026, 11, 2)}, Status.AGM_APPROVED),
        ]
        for overrides, expected in cases:
            DividendAnnouncement.objects.all().delete()
            self.upsert(**overrides)
            self.assertEqual(DividendAnnouncement.objects.get().status, expected, overrides)

    def test_status_never_moves_back(self):
        self.upsert()
        DividendAnnouncement.objects.update(status=Status.SEBON_APPROVED)   # set in the admin
        self.upsert()
        self.assertEqual(DividendAnnouncement.objects.get().status, Status.SEBON_APPROVED)

    def test_row_without_symbol_is_kept_marked_and_keyed_by_source_id(self):
        self.upsert(symbol="", fiscal_year="")
        self.upsert(symbol="", fiscal_year="", cash_pct=Decimal("2"))
        saved = DividendAnnouncement.objects.get()
        self.assertEqual((saved.missing_fields, saved.cash_pct), (["symbol", "fiscal_year"], Decimal("2")))
        # Once the source publishes the symbol, the incomplete copy goes away.
        self.upsert()
        self.assertEqual(list(DividendAnnouncement.objects.values_list("symbol", "missing_fields")), [("BHDC", [])])

    def test_nothing_to_key_on_is_skipped(self):
        self.assertEqual(self.upsert(symbol="", source_id=""), "skipped")
        self.assertFalse(DividendAnnouncement.objects.exists())

    def test_face_value_fills_rows_and_carries_to_later_rows(self):
        self.upsert()
        self.assertEqual(dividends.save_face_value("bhdc", Decimal("100")), 1)
        self.upsert(fiscal_year="2081/2082", source_id="12")
        self.assertEqual(set(DividendAnnouncement.objects.values_list("face_value", flat=True)), {Decimal("100")})

    def test_eps_upsert(self):
        self.assertTrue(dividends.save_eps("NABIL", "082-083", 4, Decimal("27.01"), source="Merolagani"))
        self.assertTrue(dividends.save_eps("NABIL", "082-083", 4, Decimal("27.50"), source="Merolagani"))
        self.assertFalse(dividends.save_eps("NABIL", "bad", 4, Decimal("1"), source="Merolagani"))
        self.assertEqual(list(CompanyEarnings.objects.values_list("fiscal_year", "quarter", "eps")),
                         [("2082/2083", 4, Decimal("27.50"))])


class MetricsTests(TestCase):

    def setUp(self):
        dividends.upsert_dividend(row(), source="ShareSansar", today=TODAY)
        dividends.save_face_value("BHDC", Decimal("100"))

    def market_close(self, day, close, symbol="BHDC"):
        MarketStockDaily.objects.create(symbol=symbol, date=day, close=Decimal(close))

    def only_row(self):
        [result] = dividends.dividend_rows()
        return result

    def test_calculations_from_crawled_inputs(self):
        self.market_close(date(2026, 10, 13), "400")
        self.market_close(date(2026, 10, 14), "421.50")          # latest wins
        CompanyEarnings.objects.create(symbol="BHDC", fiscal_year="2082/2083", quarter=4,
                                       eps=Decimal("20"), scraped_at="2026-10-15T00:00Z")
        result = self.only_row()
        self.assertEqual(result["price"], Decimal("421.50"))
        self.assertEqual(result["cash_dps"], Decimal("0.2632"))                        # 0.2632% of Rs 100
        self.assertEqual(result["dividend_yield_pct"], Decimal("0.06"))                # 0.2632 / 421.50
        self.assertEqual(result["cash_payout_pct"], Decimal("1.32"))                   # 0.2632 / 20
        self.assertEqual(result["payout_pct"], Decimal("26.32"))                       # 5.2632 / 20
        self.assertEqual(result["ex_bonus_price"], Decimal("401.43"))                  # 421.50 / 1.05
        self.assertEqual(result["flags"], [])

    def test_quarterly_or_other_year_eps_gives_no_payout(self):
        self.market_close(date(2026, 10, 14), "421.50")
        CompanyEarnings.objects.create(symbol="BHDC", fiscal_year="2082/2083", quarter=2,
                                       eps=Decimal("9"), scraped_at="2026-10-15T00:00Z")
        CompanyEarnings.objects.create(symbol="BHDC", fiscal_year="2081/2082", quarter=4,
                                       eps=Decimal("18"), scraped_at="2026-10-15T00:00Z")
        result = self.only_row()
        self.assertIsNone(result["payout_pct"])
        self.assertIn("no_eps", result["flags"])

    def test_no_ex_bonus_price_once_the_price_is_already_ex(self):
        self.market_close(date(2026, 10, 28), "402")             # after the 27 Oct book closure
        self.assertIsNone(self.only_row()["ex_bonus_price"])

    def test_newer_tracked_close_beats_older_market_close(self):
        company = Company.objects.create(symbol="BHDC", name="Bindhyabasini", sector="Hydro")
        dividends.upsert_dividend(row(), source="ShareSansar", today=TODAY)     # links the company
        self.market_close(date(2026, 10, 13), "400")
        DailyPrice.objects.create(company=company, date=date(2026, 10, 14), open=1, high=1, low=1,
                                  close=Decimal("410"), volume=1, turnover=1, source="crawled")
        DailyPrice.objects.create(company=company, date=date(2026, 10, 15), open=1, high=1, low=1,
                                  close=Decimal("999"), volume=1, turnover=1, source="unverified")
        result = self.only_row()
        self.assertEqual((result["price"], result["price_date"]), (Decimal("410"), date(2026, 10, 14)))

    def test_missing_inputs_are_flagged_not_guessed(self):
        dividends.upsert_dividend(row(symbol="", fiscal_year="", source_id="9"), source="ShareSansar", today=TODAY)
        flags = {r["symbol"]: r["flags"] for r in dividends.dividend_rows()}
        self.assertEqual(flags[""], ["missing_symbol", "missing_fiscal_year", "no_price", "no_face_value", "no_eps"])
        self.assertEqual(flags["BHDC"], ["no_price", "no_eps"])


class DividendApiTests(TestCase):

    def setUp(self):
        cache.clear()
        for overrides in ({}, {"symbol": "NABIL", "source_id": "1", "book_closure_date": date(2026, 10, 1)},
                          {"symbol": "OLD", "source_id": "2", "fiscal_year": "2081/2082"},
                          {"symbol": "NOFY", "source_id": "3", "fiscal_year": ""}):
            dividends.upsert_dividend(row(**overrides), source="ShareSansar", today=TODAY)
        user = User.objects.create_user(username="div-admin", email="div-admin@example.test",
                                        password="unused-test-password", role=User.Role.ADMIN)
        self.client = APIClient()
        self.client.force_authenticate(user)

    def symbols(self, response):
        return sorted(r["symbol"] for r in response.data["rows"])

    def test_defaults_to_latest_fiscal_year_and_keeps_rows_without_one(self):
        response = self.client.get("/api/market/dividends/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual((response.data["scope"], response.data["fiscal_year"]), ("tracked_companies", "2082/2083"))
        self.assertEqual(response.data["fiscal_years"], ["2082/2083", "2081/2082"])
        self.assertEqual(self.symbols(response), ["BHDC", "NABIL", "NOFY"])
        self.assertIsNotNone(response.data["last_scraped_at"])

    def test_filters(self):
        self.assertEqual(self.symbols(self.client.get("/api/market/dividends/", {"fiscal_year": "all"})),
                         ["BHDC", "NABIL", "NOFY", "OLD"])
        self.assertEqual(self.symbols(self.client.get("/api/market/dividends/", {"status": "agm_approved"})), ["NABIL"])
        self.assertEqual(self.client.get("/api/market/dividends/", {"status": "nope"}).status_code, 400)


# ----------------------------------------------------------------------
# Spider + pipeline (Scrapy project layout: ``crawlers.*`` is crawlers/crawlers/*)
# ----------------------------------------------------------------------

def _scrapy_modules():
    from crawlers.crawlers import items, market_wide_pipeline

    return {"crawlers.items": items, "crawlers.market_wide_pipeline": market_wide_pipeline}


def _spider(**kwargs):
    with mock.patch.dict(sys.modules, _scrapy_modules()):
        return importlib.import_module("crawlers.crawlers.spiders.dividends").DividendsSpider(**kwargs)


PAGE = """<html><body><select name="year" id="year">
<option selected value="32">
    2082/2083</option>
<option value="31">2081/2082</option>
<option value="30">2080/2081</option>
</select></body></html>"""

API_ROW = {
    "id": 766, "symbol": "<a href='https://www.sharesansar.com/company/bhdc'>BHDC</a>",
    "companyname": "<a href='https://www.sharesansar.com/company/bhdc'>Bindhyabasini Hydropower</a>",
    "bonus_share": "5.00", "cash_dividend": "0.2632", "total_dividend": "5.2632",
    "announcement_date": "2026-10-14", "bookclose_date": "2026-07-03 [Closed]",
    "distribution_date": None, "bonus_listing_date": "", "year": "2082/2083", "status": 1,
}


class DividendsSpiderTests(SimpleTestCase):

    def html(self, url, body):
        from scrapy.http import HtmlResponse

        return HtmlResponse(url=url, body=body.encode(), encoding="utf-8")

    def test_reads_latest_fiscal_years_and_asks_the_json_endpoint(self):
        requests = list(_spider().parse(self.html("https://www.sharesansar.com/proposed-dividend", PAGE)))
        self.assertEqual([r.cb_kwargs["label"] for r in requests], ["2082/2083", "2081/2082"])
        self.assertIn("type=YEARWISE", requests[0].url)
        self.assertIn("year=32", requests[0].url)
        self.assertEqual(requests[0].headers[b"X-Requested-With"], b"XMLHttpRequest")
        self.assertLess(len(requests[0].url), 2083)           # Scrapy's URLLENGTH_LIMIT drops longer ones
        self.assertEqual(len(list(_spider(years="all").parse(self.html("https://x/", PAGE)))), 3)

    def test_page_yields_rows_fundamentals_and_next_pages(self):
        from scrapy.http import TextResponse

        body = json.dumps({"recordsTotal": 120, "recordsFiltered": 120, "data": [API_ROW, {**API_ROW, "symbol": ""}]})
        response = TextResponse(url="https://www.sharesansar.com/proposed-dividend", body=body.encode(), encoding="utf-8")
        output = list(_spider().parse_page(response, year_id="32", label="2082/2083", start=0))
        items = [o for o in output if not hasattr(o, "url")]
        urls = [o.url for o in output if hasattr(o, "url")]

        self.assertEqual(items[0]["symbol"], "BHDC")
        self.assertEqual(items[0]["company_name"], "Bindhyabasini Hydropower")
        self.assertEqual(items[0]["book_closure_date"], date(2026, 7, 3))
        self.assertIsNone(items[0]["bonus_listing_date"])
        self.assertEqual(items[1]["symbol"], "")                  # still yielded, stored marked
        self.assertIn("https://www.sharesansar.com/company/bhdc", urls)
        self.assertIn("https://merolagani.com/CompanyDetail.aspx?symbol=BHDC", urls)
        self.assertEqual(sum("start=" in u for u in urls), 2)    # 50 and 100

    def test_tracked_scope_drops_other_companies(self):
        from scrapy.http import TextResponse

        body = json.dumps({"recordsTotal": 3, "recordsFiltered": 3,
                           "data": [API_ROW, {**API_ROW, "symbol": "NABIL"}, {**API_ROW, "symbol": ""}]})
        response = TextResponse(url="https://www.sharesansar.com/proposed-dividend", body=body.encode(), encoding="utf-8")
        spider = _spider()
        spider.tracked_symbols = {"NABIL"}                       # what start() loads in tracked scope
        output = list(spider.parse_page(response, year_id="32", label="2082/2083", start=0))
        self.assertEqual([o["symbol"] for o in output if not hasattr(o, "url")], ["NABIL"])
        self.assertEqual({o.cb_kwargs["symbol"] for o in output if hasattr(o, "url")}, {"NABIL"})
        self.assertTrue(spider.tracked_only)
        self.assertFalse(_spider(scope="all").tracked_only)

    def test_unexpected_json_saves_nothing(self):
        from scrapy.http import TextResponse

        response = TextResponse(url="https://x/", body=b'{"message": "Server Error"}', encoding="utf-8")
        self.assertEqual(list(_spider().parse_page(response, year_id="32", label="2082/2083", start=0)), [])

    def test_face_value_and_eps(self):
        company = self.html("https://www.sharesansar.com/company/nabil", """<table id="myTableCInfo"><tbody>
            <tr><td class="text-bold">Paid Up</td><td class="text-bold">Rs. 100.00</td></tr></tbody></table>""")
        [face] = _spider().parse_face_value(company, symbol="NABIL")
        self.assertEqual(face["face_value"], "100.00")

        detail = self.html("https://merolagani.com/CompanyDetail.aspx?symbol=NABIL", """<table><tbody><tr>
            <th style="width: 200px;">EPS </th><td> 27.01 <span class="text-primary"> (FY:082-083, Q:4)</span></td>
            </tr></tbody></table>""")
        [eps] = _spider().parse_eps(detail, symbol="NABIL")
        self.assertEqual((eps["eps"], eps["fiscal_year"], eps["quarter"]), ("27.01", "082-083", 4))


class DividendPipelineTests(TestCase):

    def test_saves_each_item_type(self):
        with mock.patch.dict(sys.modules, _scrapy_modules()):
            module = importlib.import_module("crawlers.crawlers.dividend_pipeline")
        pipeline = module.DividendPipeline()
        pipeline._setup()
        spider = SimpleNamespace(source="ShareSansar", logger=mock.Mock())
        for item in (
            {**row(), "item_type": "dividend", "bonus_pct": "5.00", "cash_pct": "", "source": "ShareSansar"},
            {"item_type": "company_face_value", "symbol": "BHDC", "face_value": "100.00"},
            {"item_type": "company_eps", "symbol": "BHDC", "fiscal_year": "082-083", "quarter": 4, "eps": "1,234.5"},
        ):
            pipeline._process_sync(item, spider)
        saved = DividendAnnouncement.objects.get()
        self.assertEqual((saved.bonus_pct, saved.cash_pct, saved.face_value), (Decimal("5"), Decimal("0"), Decimal("100")))
        self.assertEqual(CompanyEarnings.objects.get().eps, Decimal("1234.50"))
        self.assertEqual(pipeline.counters["created"], 1)
