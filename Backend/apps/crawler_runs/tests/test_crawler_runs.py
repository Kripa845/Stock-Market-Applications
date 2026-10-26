# """
# TradingDataSpider: date-driven rolling window and pagination.

# These tests drive the spider's callbacks directly with synthetic
# DataTables payloads, so no network access is involved.
# """

# import json
# from datetime import date, timedelta

# from django.test import SimpleTestCase, TestCase
# from scrapy.http import Request, TextResponse

# from crawlers.crawlers.spiders.trading_data import (
#     TradingDataSpider,
#     parse_number,
#     parse_trading_date,
# )


# SYMBOL = "NABIL"


# def make_row(day, open_="100", high="105", low="99",
#              close="102", quantity="1,000", amount="102,000"):
#     """One row shaped like the ShareSansar price-history payload."""
#     return {
#         "DT_Row_Index": 1,
#         "published_date": day.isoformat() if hasattr(day, "isoformat") else day,
#         "open": open_,
#         "high": high,
#         "low": low,
#         "close": close,
#         "per_change": "0.5",
#         "traded_quantity": quantity,
#         "traded_amount": amount,
#     }


# def make_response(rows, records_total=None):
#     payload = {
#         "draw": 1,
#         "recordsTotal": records_total if records_total is not None else len(rows),
#         "recordsFiltered": records_total if records_total is not None else len(rows),
#         "data": rows,
#     }
#     return TextResponse(
#         url="https://www.sharesansar.com/company-price-history",
#         body=json.dumps(payload),
#         encoding="utf-8",
#         request=Request("https://www.sharesansar.com/company-price-history"),
#     )


# def sessions(count, start=date(2026, 8, 1)):
#     """`count` weekday trading sessions, newest last."""
#     out = []
#     cursor = start
#     while len(out) < count:
#         if cursor.weekday() < 5:
#             out.append(cursor)
#         cursor += timedelta(days=1)
#     return out


# class SpiderHarness:
#     """Drives spider callbacks and collects emitted items."""

#     def __init__(self, **kwargs):
#         self.spider = TradingDataSpider(**kwargs)
#         self.spider.company_state[SYMBOL] = {
#             "company_id": "123",
#             "csrf_token": "token",
#             "referer": "https://www.sharesansar.com/company/nabil",
#             "rows_by_date": {},
#             "rows_fetched": 0,
#             "rows_invalid": 0,
#             "pages_fetched": 0,
#             "target_end_date": None,
#             "target_start_date": None,
#             "retrieval_start_date": None,
#             "oldest_date_seen": None,
#             "records_total": 0,
#             "stop_reason": None,
#         }

#     @property
#     def state(self):
#         return self.spider.company_state.get(SYMBOL)

#     def feed(self, rows, start=0, records_total=None):
#         """Return (items, follow_up_requests) from one page."""
#         results = list(
#             self.spider.parse_history(
#                 make_response(rows, records_total),
#                 symbol=SYMBOL,
#                 start=start,
#             )
#         )
#         items = [r for r in results if not isinstance(r, Request)]
#         requests = [r for r in results if isinstance(r, Request)]
#         return items, requests


# class ParsingTests(SimpleTestCase):

#     def test_iso_date_parsed(self):
#         self.assertEqual(parse_trading_date("2026-09-18"), date(2026, 9, 18))

#     def test_html_wrapped_date_parsed(self):
#         self.assertEqual(
#             parse_trading_date('<a href="#">2026-09-18</a>'),
#             date(2026, 9, 18),
#         )

#     def test_date_with_time_component_parsed(self):
#         self.assertEqual(
#             parse_trading_date("2026-09-18 00:00:00"),
#             date(2026, 9, 18),
#         )

#     def test_garbage_date_returns_none(self):
#         self.assertIsNone(parse_trading_date("not a date"))
#         self.assertIsNone(parse_trading_date(""))
#         self.assertIsNone(parse_trading_date(None))

#     def test_comma_separated_numbers_parsed(self):
#         self.assertEqual(parse_number("1,234,567.89"), __import__(
#             "decimal").Decimal("1234567.89"))

#     def test_placeholder_numbers_return_none(self):
#         self.assertIsNone(parse_number("-"))
#         self.assertIsNone(parse_number("N/A"))
#         self.assertIsNone(parse_number(""))
#         self.assertIsNone(parse_number(None))


# class WindowAnchoringTests(SimpleTestCase):

#     def test_window_anchors_to_latest_row_not_today(self):
#         # The source's newest row is old; the window must follow it.
#         stale = date(2026, 6, 15)
#         harness = SpiderHarness()
#         harness.feed([make_row(stale)])

#         # State is cleared on finalise, so assert via the emitted items.
#         harness2 = SpiderHarness()
#         items, _ = harness2.feed([make_row(stale)])

#         self.assertEqual(items[0]["date"], stale.isoformat())

#     def test_target_start_is_end_minus_window_days(self):
#         harness = SpiderHarness()
#         latest = date(2026, 9, 18)

#         # Feed a page that does not yet reach back, so state survives.
#         rows = [make_row(latest - timedelta(days=i)) for i in range(50)]
#         harness.feed(rows[:1], records_total=500)

#         state = harness.state
#         self.assertEqual(state["target_end_date"], latest)
#         self.assertEqual(state["target_start_date"], latest - timedelta(days=31))

#     def test_retrieval_buffer_extends_fetch_floor_only(self):
#         harness = SpiderHarness()
#         latest = date(2026, 9, 18)
#         harness.feed([make_row(latest)], records_total=500)

#         state = harness.state
#         self.assertEqual(
#             state["retrieval_start_date"],
#             state["target_start_date"] - timedelta(days=5),
#         )
#         self.assertLess(state["retrieval_start_date"], state["target_start_date"])


# class PaginationTests(SimpleTestCase):

#     def test_requests_another_page_when_window_not_covered(self):
#         harness = SpiderHarness()
#         latest = date(2026, 9, 18)

#         # 10 consecutive days only reaches back to 2026-09-09, well short
#         # of the 2026-08-18 window start.
#         rows = [make_row(latest - timedelta(days=i)) for i in range(10)]
#         items, requests = harness.feed(rows, records_total=500)

#         self.assertEqual(len(requests), 1)
#         self.assertEqual(items, [])

#     def test_next_page_offset_advances_by_page_size(self):
#         harness = SpiderHarness()
#         latest = date(2026, 9, 18)
#         rows = [make_row(latest - timedelta(days=i)) for i in range(10)]

#         _, requests = harness.feed(rows, start=0, records_total=500)

#         self.assertEqual(requests[0].cb_kwargs["start"], 50)

#     def test_stops_once_window_is_covered(self):
#         harness = SpiderHarness()
#         latest = date(2026, 9, 18)

#         # 45 days back reaches past the 31+5 day retrieval floor.
#         rows = [make_row(latest - timedelta(days=i)) for i in range(45)]
#         items, requests = harness.feed(rows, records_total=500)

#         self.assertEqual(requests, [])
#         self.assertTrue(items)

#     def test_stops_when_source_is_exhausted(self):
#         harness = SpiderHarness()
#         latest = date(2026, 9, 18)
#         rows = [make_row(latest - timedelta(days=i)) for i in range(10)]

#         # recordsTotal equals what we got: nothing more to ask for.
#         items, requests = harness.feed(rows, records_total=10)

#         self.assertEqual(requests, [])
#         self.assertTrue(items)

#     def test_multi_page_response_accumulates_across_pages(self):
#         harness = SpiderHarness()
#         latest = date(2026, 9, 18)

#         # Three pages are genuinely needed: the retrieval floor is
#         # latest - (31 + 5) days, so pages 1 and 2 do not reach it.
#         page1 = [make_row(latest - timedelta(days=i)) for i in range(0, 10)]
#         page2 = [make_row(latest - timedelta(days=i)) for i in range(10, 20)]
#         page3 = [make_row(latest - timedelta(days=i)) for i in range(20, 45)]

#         items, requests = harness.feed(page1, start=0, records_total=500)
#         self.assertEqual(items, [])
#         self.assertEqual(len(requests), 1)

#         items, requests = harness.feed(page2, start=50, records_total=500)
#         self.assertEqual(items, [])
#         self.assertEqual(len(requests), 1)

#         items, requests = harness.feed(page3, start=100, records_total=500)
#         self.assertEqual(requests, [])
#         self.assertTrue(items)

#         # Only rows inside the 31-day window survive.
#         window_start = latest - timedelta(days=31)
#         for item in items:
#             self.assertGreaterEqual(date.fromisoformat(item["date"]), window_start)
#             self.assertLessEqual(date.fromisoformat(item["date"]), latest)

#     def test_max_pages_is_respected(self):
#         harness = SpiderHarness(max_pages=2)
#         latest = date(2026, 9, 18)

#         # Pages that never reach back far enough.
#         page = [make_row(latest)]

#         _, requests = harness.feed(page, start=0, records_total=10000)
#         self.assertEqual(len(requests), 1)

#         items, requests = harness.feed(page, start=50, records_total=10000)
#         # Page cap hit: stop and emit what we have.
#         self.assertEqual(requests, [])
#         self.assertTrue(items)

#     def test_does_not_fetch_unlimited_history(self):
#         spider = TradingDataSpider()
#         self.assertLessEqual(spider.MAX_PAGES * spider.PAGE_SIZE, 500)

#     def test_page_size_is_not_the_window_definition(self):
#         spider = TradingDataSpider()
#         self.assertEqual(spider.PAGE_SIZE, 50)
#         self.assertEqual(spider.WINDOW_DAYS, 31)
#         self.assertNotEqual(spider.PAGE_SIZE, spider.WINDOW_DAYS)


# class DateFilteringTests(SimpleTestCase):

#     def test_rows_outside_the_window_are_discarded(self):
#         harness = SpiderHarness()
#         latest = date(2026, 9, 18)

#         rows = [make_row(latest - timedelta(days=i)) for i in range(60)]
#         items, _ = harness.feed(rows, records_total=60)

#         window_start = latest - timedelta(days=31)
#         emitted = {date.fromisoformat(item["date"]) for item in items}

#         self.assertTrue(all(d >= window_start for d in emitted))
#         # Buffered rows beyond the window were fetched but not emitted.
#         self.assertLess(len(items), 60)

#     def test_buffer_rows_are_not_emitted(self):
#         harness = SpiderHarness()
#         latest = date(2026, 9, 18)
#         window_start = latest - timedelta(days=31)

#         rows = [make_row(latest - timedelta(days=i)) for i in range(40)]
#         items, _ = harness.feed(rows, records_total=40)

#         buffered = [
#             item for item in items
#             if date.fromisoformat(item["date"]) < window_start
#         ]
#         self.assertEqual(buffered, [])

#     def test_unique_trading_dates_not_row_count(self):
#         # 21 sessions is a valid month; so is 22. Neither is forced to 20 or 30.
#         harness = SpiderHarness()
#         trading_days = sessions(21, start=date(2026, 8, 20))
#         latest = trading_days[-1]

#         rows = [make_row(day) for day in reversed(trading_days)]
#         rows.append(make_row(latest - timedelta(days=40)))  # outside window

#         items, _ = harness.feed(rows, records_total=len(rows))
#         unique = {item["date"] for item in items}

#         self.assertEqual(len(unique), 21)

#     def test_twenty_two_sessions_also_valid(self):
#         harness = SpiderHarness()
#         trading_days = sessions(22, start=date(2026, 8, 19))
#         rows = [make_row(day) for day in reversed(trading_days)]

#         items, _ = harness.feed(rows, records_total=len(rows))

#         self.assertEqual(len({item["date"] for item in items}), 22)


# class DuplicateAndMissingDataTests(SimpleTestCase):

#     def test_duplicate_dates_are_collapsed(self):
#         harness = SpiderHarness()
#         latest = date(2026, 9, 18)

#         rows = [make_row(latest), make_row(latest), make_row(latest)]
#         items, _ = harness.feed(rows, records_total=3)

#         self.assertEqual(len(items), 1)

#     def test_duplicates_across_page_boundaries_are_collapsed(self):
#         harness = SpiderHarness()
#         latest = date(2026, 9, 18)

#         page1 = [make_row(latest - timedelta(days=i)) for i in range(10)]
#         harness.feed(page1, start=0, records_total=500)

#         # Page 2 repeats the last row of page 1, as DataTables can.
#         page2 = [make_row(latest - timedelta(days=9))] + [
#             make_row(latest - timedelta(days=i)) for i in range(10, 45)
#         ]
#         items, _ = harness.feed(page2, start=50, records_total=500)

#         emitted = [item["date"] for item in items]
#         self.assertEqual(len(emitted), len(set(emitted)))

#     def test_row_with_missing_close_is_skipped_not_fatal(self):
#         harness = SpiderHarness()
#         latest = date(2026, 9, 18)

#         bad = make_row(latest - timedelta(days=1))
#         bad["close"] = None

#         rows = [make_row(latest), bad]
#         items, _ = harness.feed(rows, records_total=2)

#         self.assertEqual(len(items), 1)
#         self.assertEqual(items[0]["date"], latest.isoformat())

#     def test_row_with_missing_turnover_is_skipped(self):
#         harness = SpiderHarness()
#         latest = date(2026, 9, 18)

#         bad = make_row(latest - timedelta(days=1))
#         bad["traded_amount"] = ""

#         items, _ = harness.feed([make_row(latest), bad], records_total=2)
#         self.assertEqual(len(items), 1)

#     def test_unparseable_date_row_is_skipped(self):
#         harness = SpiderHarness()
#         latest = date(2026, 9, 18)

#         bad = make_row(latest)
#         bad["published_date"] = "garbage"

#         items, _ = harness.feed([make_row(latest), bad], records_total=2)
#         self.assertEqual(len(items), 1)

#     def test_entire_page_of_bad_rows_does_not_crash(self):
#         harness = SpiderHarness()
#         rows = [make_row("garbage") for _ in range(5)]

#         items, requests = harness.feed(rows, records_total=5)

#         self.assertEqual(items, [])
#         self.assertEqual(requests, [])

#     def test_empty_response_is_handled(self):
#         harness = SpiderHarness()
#         items, requests = harness.feed([], records_total=0)

#         self.assertEqual(items, [])
#         self.assertEqual(requests, [])

#     def test_invalid_json_is_handled(self):
#         harness = SpiderHarness()
#         response = TextResponse(
#             url="https://www.sharesansar.com/company-price-history",
#             body="<html>error</html>",
#             encoding="utf-8",
#             request=Request("https://www.sharesansar.com/company-price-history"),
#         )

#         results = list(
#             harness.spider.parse_history(response, symbol=SYMBOL, start=0)
#         )
#         self.assertEqual(results, [])


# class IncompleteDatasetTests(SimpleTestCase):

#     def test_short_history_company_still_emits_what_exists(self):
#         # A newly listed company with only 4 sessions is not an error.
#         harness = SpiderHarness()
#         trading_days = sessions(4, start=date(2026, 9, 14))
#         rows = [make_row(day) for day in reversed(trading_days)]

#         items, requests = harness.feed(rows, records_total=4)

#         self.assertEqual(len(items), 4)
#         self.assertEqual(requests, [])

#     def test_company_with_no_rows_emits_nothing(self):
#         harness = SpiderHarness()
#         items, _ = harness.feed([], records_total=0)
#         self.assertEqual(items, [])

#     def test_partial_window_marked_by_stop_reason(self):
#         harness = SpiderHarness(max_pages=1)
#         latest = date(2026, 9, 18)

#         # One page that does not reach the window floor, page cap = 1.
#         rows = [make_row(latest - timedelta(days=i)) for i in range(5)]
#         items, requests = harness.feed(rows, records_total=10000)

#         self.assertEqual(requests, [])
#         self.assertEqual(len(items), 5)


# class FormDataTests(SimpleTestCase):

#     def test_length_is_page_size_not_twenty(self):
#         spider = TradingDataSpider()
#         data = spider.build_form_data(company_id="123", start=0)

#         self.assertEqual(data["length"], "50")
#         self.assertNotEqual(data["length"], "20")

#     def test_start_offset_is_sent(self):
#         spider = TradingDataSpider()
#         data = spider.build_form_data(company_id="123", start=100)

#         self.assertEqual(data["start"], "100")

#     def test_company_id_is_preserved(self):
#         spider = TradingDataSpider()
#         data = spider.build_form_data(company_id="987", start=0)

#         self.assertEqual(data["company"], "987")

#     def test_window_days_overridable_from_cli(self):
#         spider = TradingDataSpider(window_days="14")
#         self.assertEqual(spider.WINDOW_DAYS, 14)

#     def test_bad_cli_values_fall_back_to_defaults(self):
#         spider = TradingDataSpider(window_days="abc", max_pages="xyz")
#         self.assertEqual(spider.WINDOW_DAYS, 31)
#         self.assertEqual(spider.MAX_PAGES, 6)


# class CompanySymbolMappingTests(TestCase):

#     def test_emitted_items_carry_the_company_symbol(self):
#         harness = SpiderHarness()
#         items, _ = harness.feed([make_row(date(2026, 9, 18))], records_total=1)

#         self.assertEqual(items[0]["company"], SYMBOL)
#         self.assertEqual(items[0]["source"], "ShareSansar")
#         self.assertEqual(items[0]["item_type"], "daily_price")

#     def test_emitted_date_is_iso_for_the_pipeline(self):
#         # The pipeline parses with strptime("%Y-%m-%d").
#         harness = SpiderHarness()
#         items, _ = harness.feed([make_row(date(2026, 9, 18))], records_total=1)

#         self.assertEqual(items[0]["date"], "2026-09-18")
"""
TradingDataSpider: date-driven rolling window and pagination.

These tests drive the spider's callbacks directly with synthetic
DataTables payloads, so no network access is involved.
"""

import json
from datetime import date, timedelta

from django.test import SimpleTestCase, TestCase
from scrapy.http import Request, TextResponse

from crawlers.crawlers.spiders.trading_data import (
    TradingDataSpider,
    parse_number,
    parse_trading_date,
)


SYMBOL = "NABIL"


def make_row(day, open_="100", high="105", low="99",
             close="102", quantity="1,000", amount="102,000"):
    """One row shaped like the ShareSansar price-history payload."""
    return {
        "DT_Row_Index": 1,
        "published_date": day.isoformat() if hasattr(day, "isoformat") else day,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "per_change": "0.5",
        "traded_quantity": quantity,
        "traded_amount": amount,
    }


def make_response(rows, records_total=None):
    payload = {
        "draw": 1,
        "recordsTotal": records_total if records_total is not None else len(rows),
        "recordsFiltered": records_total if records_total is not None else len(rows),
        "data": rows,
    }
    return TextResponse(
        url="https://www.sharesansar.com/company-price-history",
        body=json.dumps(payload),
        encoding="utf-8",
        request=Request("https://www.sharesansar.com/company-price-history"),
    )


def sessions(count, start=date(2026, 8, 1)):
    """`count` weekday trading sessions, newest last."""
    out = []
    cursor = start
    while len(out) < count:
        if cursor.weekday() < 5:
            out.append(cursor)
        cursor += timedelta(days=1)
    return out


class SpiderHarness:
    """Drives spider callbacks and collects emitted items."""

    def __init__(self, **kwargs):
        self.spider = TradingDataSpider(**kwargs)
        self.spider.company_state[SYMBOL] = {
            "company_id": "123",
            "csrf_token": "token",
            "referer": "https://www.sharesansar.com/company/nabil",
            "rows_by_date": {},
            "rows_fetched": 0,
            "rows_invalid": 0,
            "pages_fetched": 0,
            "target_end_date": None,
            "target_start_date": None,
            "retrieval_start_date": None,
            "oldest_date_seen": None,
            "records_total": 0,
            "stop_reason": None,
        }

    @property
    def state(self):
        return self.spider.company_state.get(SYMBOL)

    def feed(self, rows, start=0, records_total=None):
        """Return (items, follow_up_requests) from one page."""
        results = list(
            self.spider.parse_history(
                make_response(rows, records_total),
                symbol=SYMBOL,
                start=start,
            )
        )
        items = [r for r in results if not isinstance(r, Request)]
        requests = [r for r in results if isinstance(r, Request)]
        return items, requests


class ParsingTests(SimpleTestCase):

    def test_iso_date_parsed(self):
        self.assertEqual(parse_trading_date("2026-09-18"), date(2026, 9, 18))

    def test_html_wrapped_date_parsed(self):
        self.assertEqual(
            parse_trading_date('<a href="#">2026-09-18</a>'),
            date(2026, 9, 18),
        )

    def test_date_with_time_component_parsed(self):
        self.assertEqual(
            parse_trading_date("2026-09-18 00:00:00"),
            date(2026, 9, 18),
        )

    def test_garbage_date_returns_none(self):
        self.assertIsNone(parse_trading_date("not a date"))
        self.assertIsNone(parse_trading_date(""))
        self.assertIsNone(parse_trading_date(None))

    def test_comma_separated_numbers_parsed(self):
        self.assertEqual(parse_number("1,234,567.89"), __import__(
            "decimal").Decimal("1234567.89"))

    def test_placeholder_numbers_return_none(self):
        self.assertIsNone(parse_number("-"))
        self.assertIsNone(parse_number("N/A"))
        self.assertIsNone(parse_number(""))
        self.assertIsNone(parse_number(None))


class WindowAnchoringTests(SimpleTestCase):

    def test_window_anchors_to_latest_row_not_today(self):
        # The source's newest row is old; the window must follow it.
        stale = date(2026, 6, 15)
        harness = SpiderHarness()
        harness.feed([make_row(stale)])

        # State is cleared on finalise, so assert via the emitted items.
        harness2 = SpiderHarness()
        items, _ = harness2.feed([make_row(stale)])

        self.assertEqual(items[0]["date"], stale.isoformat())

    def test_target_start_is_end_minus_window_days(self):
        harness = SpiderHarness()
        latest = date(2026, 9, 18)

        # Feed a page that does not yet reach back, so state survives.
        rows = [make_row(latest - timedelta(days=i)) for i in range(50)]
        harness.feed(rows[:1], records_total=500)

        state = harness.state
        self.assertEqual(state["target_end_date"], latest)
        self.assertEqual(state["target_start_date"], latest - timedelta(days=31))

    def test_retrieval_buffer_extends_fetch_floor_only(self):
        harness = SpiderHarness()
        latest = date(2026, 9, 18)
        harness.feed([make_row(latest)], records_total=500)

        state = harness.state
        self.assertEqual(
            state["retrieval_start_date"],
            state["target_start_date"] - timedelta(days=5),
        )
        self.assertLess(state["retrieval_start_date"], state["target_start_date"])


class PaginationTests(SimpleTestCase):

    def test_requests_another_page_when_window_not_covered(self):
        harness = SpiderHarness()
        latest = date(2026, 9, 18)

        # 10 consecutive days only reaches back to 2026-09-09, well short
        # of the 2026-08-18 window start.
        rows = [make_row(latest - timedelta(days=i)) for i in range(10)]
        items, requests = harness.feed(rows, records_total=500)

        self.assertEqual(len(requests), 1)
        self.assertEqual(items, [])

    def test_next_page_offset_advances_by_page_size(self):
        harness = SpiderHarness()
        latest = date(2026, 9, 18)
        rows = [make_row(latest - timedelta(days=i)) for i in range(10)]

        _, requests = harness.feed(rows, start=0, records_total=500)

        self.assertEqual(requests[0].cb_kwargs["start"], 50)

    def test_stops_once_window_is_covered(self):
        harness = SpiderHarness()
        latest = date(2026, 9, 18)

        # 45 days back reaches past the 31+5 day retrieval floor.
        rows = [make_row(latest - timedelta(days=i)) for i in range(45)]
        items, requests = harness.feed(rows, records_total=500)

        self.assertEqual(requests, [])
        self.assertTrue(items)

    def test_stops_when_source_is_exhausted(self):
        harness = SpiderHarness()
        latest = date(2026, 9, 18)
        rows = [make_row(latest - timedelta(days=i)) for i in range(10)]

        # recordsTotal equals what we got: nothing more to ask for.
        items, requests = harness.feed(rows, records_total=10)

        self.assertEqual(requests, [])
        self.assertTrue(items)

    def test_multi_page_response_accumulates_across_pages(self):
        harness = SpiderHarness()
        latest = date(2026, 9, 18)

        # Three pages are genuinely needed: the retrieval floor is
        # latest - (31 + 5) days, so pages 1 and 2 do not reach it.
        page1 = [make_row(latest - timedelta(days=i)) for i in range(0, 10)]
        page2 = [make_row(latest - timedelta(days=i)) for i in range(10, 20)]
        page3 = [make_row(latest - timedelta(days=i)) for i in range(20, 45)]

        items, requests = harness.feed(page1, start=0, records_total=500)
        self.assertEqual(items, [])
        self.assertEqual(len(requests), 1)

        items, requests = harness.feed(page2, start=50, records_total=500)
        self.assertEqual(items, [])
        self.assertEqual(len(requests), 1)

        items, requests = harness.feed(page3, start=100, records_total=500)
        self.assertEqual(requests, [])
        self.assertTrue(items)

        # Only rows inside the 31-day window survive.
        window_start = latest - timedelta(days=31)
        for item in items:
            self.assertGreaterEqual(date.fromisoformat(item["date"]), window_start)
            self.assertLessEqual(date.fromisoformat(item["date"]), latest)

    def test_max_pages_is_respected(self):
        harness = SpiderHarness(max_pages=2)
        latest = date(2026, 9, 18)

        # Pages that never reach back far enough.
        page = [make_row(latest)]

        _, requests = harness.feed(page, start=0, records_total=10000)
        self.assertEqual(len(requests), 1)

        items, requests = harness.feed(page, start=50, records_total=10000)
        # Page cap hit: stop and emit what we have.
        self.assertEqual(requests, [])
        self.assertTrue(items)

    def test_does_not_fetch_unlimited_history(self):
        spider = TradingDataSpider()
        self.assertLessEqual(spider.MAX_PAGES * spider.PAGE_SIZE, 500)

    def test_page_size_is_not_the_window_definition(self):
        spider = TradingDataSpider()
        self.assertEqual(spider.PAGE_SIZE, 50)
        self.assertEqual(spider.WINDOW_DAYS, 31)
        self.assertNotEqual(spider.PAGE_SIZE, spider.WINDOW_DAYS)


class DateFilteringTests(SimpleTestCase):

    def test_rows_outside_the_window_are_discarded(self):
        harness = SpiderHarness()
        latest = date(2026, 9, 18)

        rows = [make_row(latest - timedelta(days=i)) for i in range(60)]
        items, _ = harness.feed(rows, records_total=60)

        window_start = latest - timedelta(days=31)
        emitted = {date.fromisoformat(item["date"]) for item in items}

        self.assertTrue(all(d >= window_start for d in emitted))
        # Buffered rows beyond the window were fetched but not emitted.
        self.assertLess(len(items), 60)

    def test_buffer_rows_are_not_emitted(self):
        harness = SpiderHarness()
        latest = date(2026, 9, 18)
        window_start = latest - timedelta(days=31)

        rows = [make_row(latest - timedelta(days=i)) for i in range(40)]
        items, _ = harness.feed(rows, records_total=40)

        buffered = [
            item for item in items
            if date.fromisoformat(item["date"]) < window_start
        ]
        self.assertEqual(buffered, [])

    def test_unique_trading_dates_not_row_count(self):
        # 21 sessions is a valid month; so is 22. Neither is forced to 20 or 30.
        harness = SpiderHarness()
        trading_days = sessions(21, start=date(2026, 8, 20))
        latest = trading_days[-1]

        rows = [make_row(day) for day in reversed(trading_days)]
        rows.append(make_row(latest - timedelta(days=40)))  # outside window

        items, _ = harness.feed(rows, records_total=len(rows))
        unique = {item["date"] for item in items}

        self.assertEqual(len(unique), 21)

    def test_twenty_two_sessions_also_valid(self):
        harness = SpiderHarness()
        trading_days = sessions(22, start=date(2026, 8, 19))
        rows = [make_row(day) for day in reversed(trading_days)]

        items, _ = harness.feed(rows, records_total=len(rows))

        self.assertEqual(len({item["date"] for item in items}), 22)


class DuplicateAndMissingDataTests(SimpleTestCase):

    def test_duplicate_dates_are_collapsed(self):
        harness = SpiderHarness()
        latest = date(2026, 9, 18)

        rows = [make_row(latest), make_row(latest), make_row(latest)]
        items, _ = harness.feed(rows, records_total=3)

        self.assertEqual(len(items), 1)

    def test_duplicates_across_page_boundaries_are_collapsed(self):
        harness = SpiderHarness()
        latest = date(2026, 9, 18)

        page1 = [make_row(latest - timedelta(days=i)) for i in range(10)]
        harness.feed(page1, start=0, records_total=500)

        # Page 2 repeats the last row of page 1, as DataTables can.
        page2 = [make_row(latest - timedelta(days=9))] + [
            make_row(latest - timedelta(days=i)) for i in range(10, 45)
        ]
        items, _ = harness.feed(page2, start=50, records_total=500)

        emitted = [item["date"] for item in items]
        self.assertEqual(len(emitted), len(set(emitted)))

    def test_row_with_missing_close_is_skipped_not_fatal(self):
        harness = SpiderHarness()
        latest = date(2026, 9, 18)

        bad = make_row(latest - timedelta(days=1))
        bad["close"] = None

        rows = [make_row(latest), bad]
        items, _ = harness.feed(rows, records_total=2)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["date"], latest.isoformat())

    def test_row_with_missing_turnover_is_skipped(self):
        harness = SpiderHarness()
        latest = date(2026, 9, 18)

        bad = make_row(latest - timedelta(days=1))
        bad["traded_amount"] = ""

        items, _ = harness.feed([make_row(latest), bad], records_total=2)
        self.assertEqual(len(items), 1)

    def test_unparseable_date_row_is_skipped(self):
        harness = SpiderHarness()
        latest = date(2026, 9, 18)

        bad = make_row(latest)
        bad["published_date"] = "garbage"

        items, _ = harness.feed([make_row(latest), bad], records_total=2)
        self.assertEqual(len(items), 1)

    def test_entire_page_of_bad_rows_does_not_crash(self):
        harness = SpiderHarness()
        rows = [make_row("garbage") for _ in range(5)]

        items, requests = harness.feed(rows, records_total=5)

        self.assertEqual(items, [])
        self.assertEqual(requests, [])

    def test_empty_response_is_handled(self):
        harness = SpiderHarness()
        items, requests = harness.feed([], records_total=0)

        self.assertEqual(items, [])
        self.assertEqual(requests, [])

    def test_invalid_json_is_handled(self):
        harness = SpiderHarness()
        response = TextResponse(
            url="https://www.sharesansar.com/company-price-history",
            body="<html>error</html>",
            encoding="utf-8",
            request=Request("https://www.sharesansar.com/company-price-history"),
        )

        results = list(
            harness.spider.parse_history(response, symbol=SYMBOL, start=0)
        )
        self.assertEqual(results, [])


class IncompleteDatasetTests(SimpleTestCase):

    def test_short_history_company_still_emits_what_exists(self):
        # A newly listed company with only 4 sessions is not an error.
        harness = SpiderHarness()
        trading_days = sessions(4, start=date(2026, 9, 14))
        rows = [make_row(day) for day in reversed(trading_days)]

        items, requests = harness.feed(rows, records_total=4)

        self.assertEqual(len(items), 4)
        self.assertEqual(requests, [])

    def test_company_with_no_rows_emits_nothing(self):
        harness = SpiderHarness()
        items, _ = harness.feed([], records_total=0)
        self.assertEqual(items, [])

    def test_partial_window_marked_by_stop_reason(self):
        harness = SpiderHarness(max_pages=1)
        latest = date(2026, 9, 18)

        # One page that does not reach the window floor, page cap = 1.
        rows = [make_row(latest - timedelta(days=i)) for i in range(5)]
        items, requests = harness.feed(rows, records_total=10000)

        self.assertEqual(requests, [])
        self.assertEqual(len(items), 5)


class FormDataTests(SimpleTestCase):

    def test_length_is_page_size_not_twenty(self):
        spider = TradingDataSpider()
        data = spider.build_form_data(company_id="123", start=0)

        self.assertEqual(data["length"], "50")
        self.assertNotEqual(data["length"], "20")

    def test_start_offset_is_sent(self):
        spider = TradingDataSpider()
        data = spider.build_form_data(company_id="123", start=100)

        self.assertEqual(data["start"], "100")

    def test_company_id_is_preserved(self):
        spider = TradingDataSpider()
        data = spider.build_form_data(company_id="987", start=0)

        self.assertEqual(data["company"], "987")

    def test_window_days_overridable_from_cli(self):
        spider = TradingDataSpider(window_days="14")
        self.assertEqual(spider.WINDOW_DAYS, 14)

    def test_bad_cli_values_fall_back_to_defaults(self):
        spider = TradingDataSpider(window_days="abc", max_pages="xyz")
        self.assertEqual(spider.WINDOW_DAYS, 31)
        self.assertEqual(spider.MAX_PAGES, 6)


class CompanySymbolMappingTests(TestCase):

    def test_emitted_items_carry_the_company_symbol(self):
        harness = SpiderHarness()
        items, _ = harness.feed([make_row(date(2026, 9, 18))], records_total=1)

        self.assertEqual(items[0]["company"], SYMBOL)
        self.assertEqual(items[0]["source"], "ShareSansar")
        self.assertEqual(items[0]["item_type"], "daily_price")

    def test_emitted_date_is_iso_for_the_pipeline(self):
        # The pipeline parses with strptime("%Y-%m-%d").
        harness = SpiderHarness()
        items, _ = harness.feed([make_row(date(2026, 9, 18))], records_total=1)

        self.assertEqual(items[0]["date"], "2026-09-18")
