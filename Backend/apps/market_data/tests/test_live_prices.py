from datetime import datetime, timedelta
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.test import TestCase

from apps.companies.models import Company, TrackedCompany
from apps.market_data.models import TradingHoliday
from apps.market_data.services import live_prices


def feed_row(symbol, ltp, previous_close, at="2026-10-12 11:59:17.628619"):
    return {"symbol": symbol, "lastTradedPrice": ltp, "previousClose": previous_close, "lastUpdatedDateTime": at}


class LivePricesTests(TestCase):

    def setUp(self):
        cache.clear()
        for symbol in ("UP", "DOWN", "FLAT", "IDLE", "OLD"):
            company = Company.objects.create(symbol=symbol, name=f"{symbol} Ltd", sector="Banking")
            TrackedCompany.objects.create(company=company, is_tracked=True)
        untracked = Company.objects.create(symbol="OTHER", name="Other Ltd", sector="Banking")
        TrackedCompany.objects.create(company=untracked, is_tracked=False)

    def sync(self, rows):
        return live_prices.sync_live_prices(rows={row["symbol"]: row for row in rows})

    def test_sync_stores_ltp_previous_close_and_trade_time(self):
        result = self.sync([feed_row("UP", 105, 100), feed_row("OTHER", 50, 40)])
        self.assertEqual(result["updated"], 1)
        self.assertEqual(result["not_in_feed"], ["DOWN", "FLAT", "IDLE", "OLD"])
        up = Company.objects.get(symbol="UP")
        self.assertEqual(up.ltp, Decimal("105"))
        self.assertEqual(up.previous_close, Decimal("100"))
        self.assertEqual(up.prices_updated_at.astimezone(live_prices.NPT).strftime("%H:%M"), "11:59")
        self.assertIsNone(Company.objects.get(symbol="OTHER").ltp)  # untracked companies are not touched

    def test_sync_stores_session_volume_and_turnover(self):
        self.sync([{**feed_row("UP", 105, 100), "totalTradeQuantity": 6151, "totalTradeValue": 3355875.5}])
        up = Company.objects.get(symbol="UP")
        self.assertEqual((up.session_volume, up.session_turnover), (6151, Decimal("3355875.50")))

    def test_movers_rank_only_companies_that_traded_in_the_latest_session(self):
        self.sync([
            feed_row("OLD", 90, 80, at="2026-10-09 14:59:00"),   # last traded on an earlier session
            feed_row("UP", 105, 100), feed_row("DOWN", 95, 100), feed_row("FLAT", 100, 100),
        ])
        result = live_prices.live_movers()
        self.assertEqual(str(result["session_date"]), "2026-10-12")
        self.assertEqual([row["symbol"] for row in result["gainers"]], ["UP"])
        self.assertEqual([row["symbol"] for row in result["losers"]], ["DOWN"])
        self.assertEqual(result["unchanged_count"], 1)
        self.assertEqual(result["not_traded"], ["IDLE", "OLD"])
        up = result["gainers"][0]
        self.assertEqual((up["change"], up["change_pct"]), (Decimal("5.00"), Decimal("5.00")))

    def test_no_live_prices_yet_gives_reason_not_numbers(self):
        result = live_prices.live_movers()
        self.assertIsNone(result["as_of"])
        self.assertEqual(result["gainers"], [])
        self.assertIn("No live prices", result["reason"])

    def test_empty_feed_raises_and_keeps_old_prices(self):
        self.sync([feed_row("UP", 105, 100)])
        fetched = live_prices.last_successful_fetch()
        with mock.patch("nepse_data_api.Nepse") as nepse:
            nepse.return_value.get_stocks.return_value = []
            with self.assertRaises(live_prices.LivePriceError):
                live_prices.sync_live_prices()
        self.assertEqual(Company.objects.get(symbol="UP").ltp, Decimal("105"))
        self.assertEqual(live_prices.last_successful_fetch(), fetched)  # a failed fetch is not recorded

    def test_client_sets_timeout_and_user_agent_on_every_request(self):
        with mock.patch("nepse_data_api.Nepse.authenticate"):     # no network
            client = live_prices._nepse_client()
        self.assertEqual(client.session.headers["User-Agent"], live_prices.USER_AGENT)
        with mock.patch("requests.Session.request") as request:
            request.return_value.json.return_value = []
            client.get_stocks()
        self.assertEqual(request.call_args.kwargs["timeout"], live_prices.TIMEOUT_SECONDS)

    def test_timeout_or_changed_format_raises_live_price_error(self):
        import requests
        with mock.patch("nepse_data_api.Nepse.authenticate", side_effect=requests.Timeout("slow")):
            with self.assertRaises(live_prices.LivePriceError):
                live_prices.fetch_live_rows()
        with mock.patch.object(live_prices, "_nepse_client") as client:
            client.return_value.get_stocks.return_value = ["not", "a", "dict"]
            with self.assertRaises(live_prices.LivePriceError):
                live_prices.fetch_live_rows()

    def test_successful_sync_records_fetch_time(self):
        self.assertIsNone(live_prices.last_successful_fetch())
        self.sync([feed_row("UP", 105, 100)])
        self.assertIsNotNone(live_prices.last_successful_fetch())


class StaleLivePricesTests(TestCase):
    # Monday 2026-10-12 is a Monday-Friday trading day.
    OPEN = datetime(2026, 10, 12, 12, 0, tzinfo=live_prices.NPT)

    def test_fresh_fetch_is_not_stale(self):
        self.assertFalse(live_prices.is_stale(self.OPEN - timedelta(minutes=3), now=self.OPEN))

    def test_old_fetch_is_stale(self):
        self.assertTrue(live_prices.is_stale(self.OPEN - timedelta(minutes=11), now=self.OPEN))

    def test_no_fetch_is_stale(self):
        self.assertTrue(live_prices.is_stale(None, now=self.OPEN))

    def test_market_closed_is_never_stale(self):
        after_close = self.OPEN.replace(hour=16)
        saturday = datetime(2026, 10, 17, 12, 0, tzinfo=live_prices.NPT)
        for now in (after_close, saturday):
            self.assertFalse(live_prices.is_stale(None, now=now))

    def test_trading_holiday_is_never_stale(self):
        TradingHoliday.objects.create(date=self.OPEN.date(), name="Test holiday")
        self.assertFalse(live_prices.is_stale(None, now=self.OPEN))


class DaySummaryFetcherTests(TestCase):

    def test_empty_day_is_retried_once_with_a_fresh_login(self):
        from datetime import date
        day = date(2026, 10, 12)
        expired, fresh = mock.Mock(), mock.Mock()
        expired.get_today_price.return_value = []          # what the library returns on a 401
        fresh.get_today_price.return_value = [{"symbol": "NABIL", "businessDate": "2026-10-12", "totalTrades": 401}]
        with mock.patch.object(live_prices, "_nepse_client", side_effect=[expired, fresh]) as login:
            rows = live_prices.day_summary_fetcher()(day)
        self.assertEqual(rows["NABIL"]["totalTrades"], 401)
        self.assertEqual(login.call_count, 2)
