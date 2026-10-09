from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase

from crawlers.crawlers.utils.dates import parse_bikram_sambat, parse_datetime

NPT = ZoneInfo("Asia/Kathmandu")
NOW = datetime(2026, 10, 2, 12, 0, tzinfo=NPT)


class BikramSambatDateTests(SimpleTestCase):

    def test_arthakhabar_header_dates_convert_to_ad(self):
        # Real header text from the two articles that were stored with year 2083.
        self.assertEqual(parse_datetime("१२ श्रावण २०८३, मंगलवार १५:५०", now=NOW), datetime(2026, 7, 28, 15, 50, tzinfo=NPT))
        self.assertEqual(parse_datetime("१० भाद्र २०८३, बुधबार १६:०४", now=NOW), datetime(2026, 8, 26, 16, 4, tzinfo=NPT))

    def test_ascii_digits_and_no_time(self):
        self.assertEqual(parse_bikram_sambat("16 असोज 2083"), datetime(2026, 10, 2, 0, 0, tzinfo=NPT))

    def test_gregorian_dates_still_parse(self):
        self.assertEqual(parse_datetime("2026-09-30T08:15:00+05:45", now=NOW).date().isoformat(), "2026-09-30")

    def test_future_dates_are_rejected_not_stored(self):
        self.assertIsNone(parse_datetime("2083-12-04 15:50", now=NOW))
        self.assertIsNotNone(parse_datetime((NOW + timedelta(hours=6)).isoformat(), now=NOW))

    def test_text_without_a_bs_date(self):
        self.assertIsNone(parse_bikram_sambat("अर्थ खबर"))
