import importlib
import json
import sys
from datetime import date
from decimal import Decimal
from unittest import mock

from django.test import SimpleTestCase, TestCase

from apps.companies.models import Company
from apps.reports.models import IpoIssue
from apps.reports.services import ipo_issues


def issue(**overrides):
    data = {
        "issue_type": "ipo", "source_id": "ipo-1171-5915000", "symbol": "hphl",
        "company_name": "Him Parbat Hydropower Limited", "units": 5915000, "price": Decimal("100"),
        "ratio": "", "issue_manager": "Citizens Capital Limited", "open_date": None, "close_date": None,
        "final_date": None, "listing_date": None, "source_status": -2, "announcement_url": "",
    }
    return {**data, **overrides}


class UpsertIssueTests(TestCase):
    def test_creates_then_fills_dates_in_place(self):
        self.assertEqual(ipo_issues.upsert_issue(issue(), source="ShareSansar"), "created")
        outcome = ipo_issues.upsert_issue(
            issue(open_date=date(2026, 11, 18), close_date=date(2026, 11, 23), final_date=date(2026, 12, 2), source_status=-1),
            source="ShareSansar",
        )
        self.assertEqual(outcome, "updated")
        row = IpoIssue.objects.get()
        self.assertEqual((row.symbol, row.open_date, row.final_date, row.source_status), ("HPHL", date(2026, 11, 18), date(2026, 12, 2), -1))
        self.assertIsNotNone(row.scraped_at)

    def test_links_company_when_the_symbol_is_ours(self):
        company = Company.objects.create(symbol="HPHL", name="Him Parbat", sector="Hydropower")
        ipo_issues.upsert_issue(issue(), source="ShareSansar")
        self.assertEqual(IpoIssue.objects.get().company, company)

    def test_skips_rows_without_key_or_known_type(self):
        self.assertEqual(ipo_issues.upsert_issue(issue(source_id=""), source="ShareSansar"), "skipped")
        self.assertEqual(ipo_issues.upsert_issue(issue(issue_type="warrant"), source="ShareSansar"), "skipped")
        self.assertFalse(IpoIssue.objects.exists())

    def test_two_issues_with_the_same_key_stay_separate(self):
        # API Power issued two right shares of 5,670,000 units (2020 and 2021).
        first = issue(issue_type="right", source_id="right-527-5670000", open_date=date(2021, 6, 3))
        second = issue(issue_type="right", source_id="right-527-5670000", open_date=date(2020, 10, 30))
        for _ in range(2):      # a re-crawl updates both, creates nothing
            ipo_issues.upsert_issue(first, source="ShareSansar")
            ipo_issues.upsert_issue(second, source="ShareSansar")
        self.assertEqual(
            sorted(IpoIssue.objects.values_list("source_id", "open_date")),
            [("right-527-5670000", date(2021, 6, 3)), ("right-527-5670000-2020-10-30", date(2020, 10, 30))],
        )

    def test_a_new_issue_under_a_used_key_keeps_its_row_once_dated(self):
        ipo_issues.upsert_issue(issue(open_date=date(2021, 6, 3)), source="ShareSansar")
        self.assertEqual(ipo_issues.upsert_issue(issue(), source="ShareSansar"), "created")        # announced, no dates
        self.assertEqual(ipo_issues.upsert_issue(issue(open_date=date(2026, 11, 18)), source="ShareSansar"), "updated")
        self.assertEqual(
            sorted(IpoIssue.objects.values_list("source_id", "open_date")),
            [("ipo-1171-5915000", date(2021, 6, 3)), ("ipo-1171-5915000-pending", date(2026, 11, 18))],
        )

    def test_key_prefix_does_not_match_a_longer_unit_count(self):
        ipo_issues.upsert_issue(issue(source_id="ipo-1-1000", open_date=date(2026, 1, 1)), source="ShareSansar")
        self.assertEqual(ipo_issues.upsert_issue(issue(source_id="ipo-1-100", open_date=date(2025, 1, 1)), source="ShareSansar"), "created")
        self.assertEqual(IpoIssue.objects.filter(source_id="ipo-1-100").count(), 1)

    def test_source_id(self):
        self.assertEqual(ipo_issues.issue_source_id("right", 961, 5750000), "right-961-5750000")
        self.assertIsNone(ipo_issues.issue_source_id("ipo", None, 100))
        self.assertIsNone(ipo_issues.issue_source_id("ipo", 961, None))


# ----------------------------------------------------------------------
# Spider (Scrapy project layout: ``crawlers.*`` is crawlers/crawlers/*)
# ----------------------------------------------------------------------

def _spider(**kwargs):
    from crawlers.crawlers import items, market_wide_pipeline

    modules = {"crawlers.items": items, "crawlers.market_wide_pipeline": market_wide_pipeline}
    with mock.patch.dict(sys.modules, modules):
        return importlib.import_module("crawlers.crawlers.spiders.ipo_issues").IpoIssuesSpider(**kwargs)


# Trimmed from https://www.sharesansar.com/existing-issues?type=8 on 2026-10-28.
API_ROW = {
    "companyid": 1171, "ratio_value": None, "total_units": "422500.00", "issue_price": "100.00",
    "opening_date": "2026-10-28", "closing_date": "2026-11-02", "final_date": "2026-11-11",
    "announcement_link": "https://www.sharesansar.com/announcementdetail/him-parbat-ipo-foreign-employees",
    "issue_manager": "Citizens Capital Limited", "listing_date": "", "status": 0, "bkstatus": -1,
    "company": {
        "id": 1171,
        "symbol": "<a href='https://www.sharesansar.com/company/hphl'>HPHL</a>",
        "companyname": "<a href='https://www.sharesansar.com/company/hphl'>Him Parbat Hydropower Limited</a>",
    },
}


def _response(payload):
    from scrapy.http import TextResponse

    body = payload if isinstance(payload, str) else json.dumps(payload)
    return TextResponse(url="https://www.sharesansar.com/existing-issues", body=body.encode(), encoding="utf-8")


class IpoIssuesSpiderTests(SimpleTestCase):
    def test_asks_every_issue_type_as_json(self):
        requests = list(_spider().start_requests())
        self.assertEqual([r.cb_kwargs["type_id"] for r in requests], list(ipo_issues.SHARESANSAR_TYPES))
        self.assertIn("type=8", requests[6].url)
        self.assertEqual(requests[0].headers[b"X-Requested-With"], b"XMLHttpRequest")

    def test_page_yields_items(self):
        output = list(_spider().parse_page(_response({"recordsTotal": 1, "data": [API_ROW]}), type_id=8, start=0))
        self.assertEqual(len(output), 1)
        item = output[0]
        self.assertEqual(
            {k: item[k] for k in ("issue_type", "source_id", "symbol", "company_name", "units", "price", "source_status")},
            {"issue_type": "ipo_migrant", "source_id": "ipo_migrant-1171-422500", "symbol": "HPHL",
             "company_name": "Him Parbat Hydropower Limited", "units": 422500, "price": "100.00", "source_status": 0},
        )
        self.assertEqual((item["open_date"], item["close_date"], item["final_date"]), (date(2026, 10, 28), date(2026, 11, 2), date(2026, 11, 11)))
        self.assertIsNone(item["listing_date"])
        self.assertEqual(item["ratio"], "")

    def test_upcoming_issue_without_dates(self):
        row = {**API_ROW, "opening_date": "", "closing_date": "", "final_date": "", "issue_price": None}
        item = next(iter(_spider().parse_page(_response({"recordsTotal": 1, "data": [row]}), type_id=1, start=0)))
        self.assertEqual((item["open_date"], item["close_date"], item["price"]), (None, None, None))
        self.assertEqual(item["source_id"], "ipo-1171-422500")

    def test_paging_is_limited_unless_all(self):
        def next_pages(spider):
            output = spider.parse_page(_response({"recordsTotal": 269, "data": []}), type_id=1, start=0)
            return [o.cb_kwargs["start"] for o in output if hasattr(o, "url")]

        self.assertEqual(next_pages(_spider()), [50])                       # 2 pages by default
        self.assertEqual(next_pages(_spider(pages="all")), [50, 100, 150, 200, 250])
        self.assertEqual(next_pages(_spider(pages="1")), [])

    def test_unexpected_response_yields_nothing(self):
        self.assertEqual(list(_spider().parse_page(_response('{"message": "Server Error"}'), type_id=1, start=0)), [])
        self.assertEqual(list(_spider().parse_page(_response("<html>"), type_id=1, start=0)), [])
