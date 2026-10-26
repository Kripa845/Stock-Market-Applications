import importlib
import sys
from datetime import date
from unittest import mock

import requests
from django.test import SimpleTestCase, TestCase, override_settings

from apps.market_data import tasks
from apps.market_data.services import live_prices
from apps.market_data.services.circuit_breaker import CircuitBreaker


class FakeRedis:
    def __init__(self):
        self.data = {}

    def exists(self, key):
        return int(key in self.data)

    def ttl(self, key):
        return 1800

    def incr(self, key):
        self.data[key] = self.data.get(key, 0) + 1
        return self.data[key]

    def set(self, key, value, ex=None):
        self.data[key] = value

    def delete(self, key):
        self.data.pop(key, None)


def feed(*symbols):
    return [{"symbol": s, "lastTradedPrice": 100, "previousClose": 99,
             "lastUpdatedDateTime": "2026-10-12 11:59:17.628619"} for s in symbols]


class SharedClientTests(SimpleTestCase):

    def setUp(self):
        live_prices.discard_shared_nepse_client()
        self.addCleanup(live_prices.discard_shared_nepse_client)

    @override_settings(NEPSE_CLIENT_REUSE_SECONDS=600)
    def test_client_is_reused_between_runs(self):
        client = mock.Mock()
        client.get_stocks.return_value = feed("NABIL")
        with mock.patch.object(live_prices, "_nepse_client", return_value=client) as login:
            live_prices.fetch_live_rows()
            live_prices.fetch_live_rows()
        self.assertEqual(login.call_count, 1)
        self.assertEqual(client.get_stocks.call_count, 2)

    @override_settings(NEPSE_CLIENT_REUSE_SECONDS=600)
    def test_expired_reused_login_logs_in_again_once(self):
        expired, fresh = mock.Mock(), mock.Mock()
        expired.get_stocks.side_effect = [feed("NABIL"), []]   # [] is what the library returns on a 401
        fresh.get_stocks.return_value = feed("SCB")
        with mock.patch.object(live_prices, "_nepse_client", side_effect=[expired, fresh]) as login:
            live_prices.fetch_live_rows()
            rows = live_prices.fetch_live_rows()
        self.assertEqual(set(rows), {"SCB"})
        self.assertEqual(login.call_count, 2)

    @override_settings(NEPSE_CLIENT_REUSE_SECONDS=600)
    def test_empty_feed_on_a_fresh_login_is_not_retried(self):
        client = mock.Mock()
        client.get_stocks.return_value = []
        with mock.patch.object(live_prices, "_nepse_client", return_value=client) as login:
            with self.assertRaises(live_prices.LivePriceError):
                live_prices.fetch_live_rows()
        self.assertEqual(login.call_count, 1)

    @override_settings(NEPSE_CLIENT_REUSE_SECONDS=600)
    def test_error_drops_the_shared_client(self):
        broken, fresh = mock.Mock(), mock.Mock()
        broken.get_stocks.side_effect = requests.ConnectionError("reset")
        fresh.get_stocks.return_value = feed("NABIL")
        with mock.patch.object(live_prices, "_nepse_client", side_effect=[broken, fresh]) as login:
            with self.assertRaises(live_prices.LivePriceError):
                live_prices.fetch_live_rows()
            live_prices.fetch_live_rows()
        self.assertEqual(login.call_count, 2)

    @override_settings(NEPSE_CLIENT_REUSE_SECONDS=1)
    def test_old_client_is_replaced(self):
        client = mock.Mock()
        client.get_stocks.return_value = feed("NABIL")
        with mock.patch.object(live_prices, "_nepse_client", return_value=client) as login, \
                mock.patch.object(live_prices.time, "monotonic", side_effect=[0.0, 5.0]):
            live_prices.fetch_live_rows()
            live_prices.fetch_live_rows()
        self.assertEqual(login.call_count, 2)

    def test_live_index_retries_401_with_a_fresh_login(self):
        from apps.market_indices.services import nepse_indices

        unauthorized = requests.HTTPError(response=mock.Mock(status_code=401))
        self.assertTrue(nepse_indices._retryable(unauthorized))
        self.assertFalse(nepse_indices._retryable(requests.HTTPError(response=mock.Mock(status_code=404))))


class LivePricesBreakerTests(TestCase):

    def setUp(self):
        self.redis = FakeRedis()
        for patcher in (mock.patch.object(tasks, "_breaker_redis", return_value=self.redis),
                        mock.patch("apps.market_data.services.trading_days.market_closed_reason", return_value=None)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_task(self, **sync):
        with mock.patch.object(live_prices, "sync_live_prices", **sync) as patched:
            return tasks.update_live_prices(), patched

    def test_three_failures_in_a_row_stop_calling_nepse(self):
        failing = {"side_effect": live_prices.LivePriceError("NEPSE live feed returned no rows")}
        for _ in range(3):
            self.run_task(**failing)
        self.assertTrue(self.redis.exists("update_live_prices:paused"))
        result, sync = self.run_task(**failing)
        self.assertEqual(result["reason"], "circuit breaker open")
        sync.assert_not_called()

    def test_a_success_resets_the_failure_count(self):
        ok = {"return_value": {"feed_rows": 1, "tracked": 1, "updated": 1, "not_in_feed": []}}
        self.run_task(side_effect=live_prices.LivePriceError("timeout"))
        self.run_task(side_effect=live_prices.LivePriceError("timeout"))
        self.run_task(**ok)
        self.run_task(side_effect=live_prices.LivePriceError("timeout"))
        self.assertFalse(self.redis.exists("update_live_prices:paused"))

    def test_breaker_keys(self):
        breaker = CircuitBreaker(self.redis, "update_live_prices")
        self.assertEqual((breaker.failures_key, breaker.open_key),
                         ("update_live_prices:consecutive_failures", "update_live_prices:paused"))


def _market_stocks_spider():
    # The spider imports ``crawlers.items`` (Scrapy project layout); from Backend that is crawlers.crawlers.items.
    from crawlers.crawlers import items

    with mock.patch.dict(sys.modules, {"crawlers.items": items}):
        return importlib.import_module("crawlers.crawlers.spiders.merolagani").MarketStocksSpider


PAGE = """<html><head><meta property="article:published_time" content="2016-12-15T05:55:55-05:00" /></head>
<body>
<p>Published 2026-01-01</p>
<input type="text" name="date" id="fromdate" value="2026-10-13">
<h5>As of : <span class="text-org">2026-10-14</span></h5>
<table id="headFixed"><thead><tr>
<th>S.No</th><th>Symbol</th><th>Close</th><th>LTP</th><th>Vol</th><th>Prev. Close</th><th>Turnover</th><th>Trans.</th>
</tr></thead><tbody>
<tr><td>1</td><td>NABIL</td><td>541.00</td><td>541.00</td><td>55,494.00</td><td>539.00</td><td>29,977,823.40</td><td>336</td></tr>
</tbody></table>
</body></html>"""


class MarketStocksSpiderTests(SimpleTestCase):

    def parse(self, html):
        from scrapy.http import HtmlResponse

        response = HtmlResponse(url="https://www.sharesansar.com/today-share-price", body=html.encode(), encoding="utf-8")
        return list(_market_stocks_spider()().parse(response))

    def test_reads_the_headfixed_table_and_the_as_of_date(self):
        [item] = self.parse(PAGE)
        self.assertEqual(item["date"], date(2026, 10, 14))  # not the earlier dates elsewhere on the page
        self.assertEqual((item["symbol"], item["close"], item["prev_close"], item["transactions"]),
                         ("NABIL", "541.00", "539.00", "336"))
        self.assertEqual(item["item_type"], "market_stock_daily")

    def test_ignores_other_tables(self):
        banner = '<table><thead><tr><th>Symbol</th><th>Close</th><th>Vol</th><th>Turnover</th></tr></thead>' \
                 '<tbody><tr><td>FAKE</td><td>1</td><td>1</td><td>1</td></tr></tbody></table>'
        items = self.parse(PAGE.replace("<h5>", banner + "<h5>"))
        self.assertEqual([i["symbol"] for i in items], ["NABIL"])

    def test_changed_layout_saves_nothing(self):
        with self.assertLogs(level="ERROR"):
            self.assertEqual(self.parse(PAGE.replace('id="headFixed"', 'id="prices"')), [])
        with self.assertLogs(level="ERROR"):
            self.assertEqual(self.parse(PAGE.replace("As of", "Updated")), [])
