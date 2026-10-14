from datetime import date, datetime
from decimal import Decimal
from unittest import mock

import requests
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from apps.market_data.services.live_prices import NPT
from apps.market_indices.models import IndexDaily
from apps.market_indices.services import aggregates, nepse_indices
from apps.users.models import User


def row(index_id, day, close, turnover, volume, trades, pct=None, open_=None):
    return {"exchangeIndexId": index_id, "businessDate": day, "openIndex": open_, "highIndex": close + 5,
            "lowIndex": close - 5, "closingIndex": close, "turnoverValue": turnover, "turnoverVolume": volume,
            "totalTransaction": trades, "percentageChange": pct}


HISTORY = {
    "NEPSE Index": [row(58, "2026-10-09", 2591.81, 4725e6, 12129e3, 51196),
                    row(58, "2026-10-12", 2595.81, 4391e6, 11840e3, 49040, pct=0.15, open_=2595.12)],
    "Banking": [row(51, "2026-10-09", 1517.26, 973e6, 3643e3, 7771),
                row(51, "2026-10-12", 1532.58, 1264e6, 4813e3, 10548, pct=1.01)],
    # The name differs from the catalogue ("Manufacturing And Processing"); the id matches.
    "Manufacturing": [row(56, "2026-10-12", 10574.95, 517e6, 594e3, 4951, pct=-0.19)],
    "Mutual Fund": [row(66, "2026-10-09", 19.55, 5e6, 5e5, 400),
                    row(66, "2026-10-12", 19.50, 4.7e6, 5.1e5, 447, pct=-0.28)],
}


class IndexHistoryTests(TestCase):

    def setUp(self):
        call_command("seed_market_indices", stdout=mock.Mock())
        self.result = nepse_indices.sync_index_history(date(2026, 10, 1), HISTORY)

    def rows(self, kind, day=None):
        return {r["code"]: r for r in aggregates.index_table(kind, day)}

    def test_every_session_is_stored_and_matched_by_nepse_id(self):
        self.assertEqual((self.result["saved"], self.result["sessions"], self.result["unmatched"]), (7, 2, []))
        self.assertTrue(IndexDaily.objects.filter(index__code="MANUFACTURE", date=date(2026, 10, 12)).exists())

    def test_change_columns_compare_with_the_previous_session(self):
        nepse = self.rows("main")["NEPSE"]
        self.assertEqual(nepse["previous_date"], date(2026, 10, 9))
        self.assertEqual(nepse["ch"], Decimal("4.00"))
        self.assertEqual(nepse["open"], Decimal("2595.12"))
        self.assertEqual(nepse["trans_ch"], 49040 - 51196)
        self.assertAlmostEqual(float(nepse["tu_ch_pct"]), (4391 - 4725) * 100 / 4725, places=4)

    def test_turnover_share_is_of_the_nepse_index_turnover(self):
        self.assertEqual(self.rows("main")["NEPSE"]["turnover_share_pct"], Decimal("100"))
        self.assertAlmostEqual(float(self.rows("sub")["BANKING"]["turnover_share_pct"]), 1264 * 100 / 4391, places=4)

    def test_nepse_percentage_wins_over_rounded_closes(self):
        mutual = self.rows("sub")["MUTUAL"]
        self.assertEqual(mutual["ch"], Decimal("-0.05"))
        self.assertEqual(mutual["ch_pct"], Decimal("-0.28"))       # not -0.26 from 19.50 / 19.55

    def test_first_stored_session_has_no_change(self):
        manufacturing = self.rows("sub")["MANUFACTURE"]
        self.assertIsNone(manufacturing["ch"])
        self.assertIsNone(manufacturing["ch_pct"])
        self.assertIsNone(manufacturing["tu_ch"])

    def test_date_selects_the_session_on_or_before_it(self):
        rows = self.rows("main", date(2026, 10, 11))                # a Sunday
        self.assertEqual(rows["NEPSE"]["date"], date(2026, 10, 9))
        self.assertIsNone(rows["NEPSE"]["ch"])                     # nothing stored before 9 Oct

    def test_api_date_parameter_and_validation(self):
        client = APIClient()
        client.force_authenticate(User.objects.create_user(
            username="idx", email="idx@example.test", password="unused-test-password", role=User.Role.ADMIN))
        response = client.get("/api/market-indices/sub-indices/?date=2026-10-12")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(str(response.data["as_of"]), "2026-10-12")
        self.assertEqual(client.get("/api/market-indices/indices/?date=12-10-2026").status_code, 400)
        self.assertIn(APIClient().get("/api/market-indices/indices/").status_code, (401, 403))

    def test_feed_failure_saves_nothing_new(self):
        before = IndexDaily.objects.count()
        with mock.patch.object(nepse_indices, "_nepse_client") as client:
            client.return_value.get_index_history.return_value = {}
            with self.assertRaises(nepse_indices.IndexFeedError):
                nepse_indices.sync_index_history(date(2026, 10, 1))
        self.assertEqual(IndexDaily.objects.count(), before)


class LiveIndexSnapshotTests(TestCase):
    # Shape of /api/nots/nepse-index after the 2026-10-12 close: "previousClose" equals the
    # current value there, so the stored previous close must come from value - change.
    FEED = [
        {"id": 58, "generatedTime": "2026-10-12T15:16:00.91", "index": "NEPSE Index", "close": 2591.81,
         "previousClose": 2595.8106, "change": 4.0, "perChange": 0.15, "currentValue": 2595.81},
        {"id": 57, "generatedTime": "2026-10-12T15:16:00.91", "index": "Sensitive Index",
         "change": 1.96, "perChange": 0.42, "currentValue": 467.81},
        {"id": 999, "generatedTime": "2026-10-12T15:16:00.91", "currentValue": 1},  # not catalogued
    ]

    def setUp(self):
        call_command("seed_market_indices", stdout=mock.Mock())

    def test_saves_one_point_per_catalogued_index(self):
        from apps.market_indices.models import IndexIntradayPoint

        result = nepse_indices.snapshot_live_index(self.FEED)
        self.assertEqual((result["saved"], result["updated"], result["unchanged"]), (2, 0, 0))
        self.assertEqual(result["nepse"]["value"], "2595.81")
        point = IndexIntradayPoint.objects.get(index__code="NEPSE")
        self.assertEqual(point.value, Decimal("2595.81"))
        self.assertEqual(point.previous_close, Decimal("2591.81"))
        self.assertEqual(point.change_pct, Decimal("0.15"))
        self.assertEqual(point.recorded_at, datetime(2026, 10, 12, 15, 16, 0, 910000, tzinfo=NPT))  # NEPSE time

    def test_same_timestamp_and_value_is_skipped(self):
        from apps.market_indices.models import IndexIntradayPoint

        nepse_indices.snapshot_live_index(self.FEED)
        result = nepse_indices.snapshot_live_index(self.FEED)
        self.assertEqual((result["saved"], result["updated"], result["unchanged"]), (0, 0, 2))
        self.assertEqual(IndexIntradayPoint.objects.count(), 2)

    def test_changed_value_under_same_timestamp_updates_the_row(self):
        from apps.market_indices.models import IndexIntradayPoint

        nepse_indices.snapshot_live_index(self.FEED)
        corrected = [dict(self.FEED[0], currentValue=2596.5, change=4.69)] + self.FEED[1:]
        result = nepse_indices.snapshot_live_index(corrected)
        self.assertEqual((result["saved"], result["updated"], result["unchanged"]), (0, 1, 1))
        self.assertEqual(IndexIntradayPoint.objects.get(index__code="NEPSE").value, Decimal("2596.50"))

    def test_new_timestamp_adds_a_tick(self):
        from apps.market_indices.models import IndexIntradayPoint

        nepse_indices.snapshot_live_index(self.FEED)
        later = [dict(item, generatedTime="2026-10-12T15:17:00.10") for item in self.FEED]
        self.assertEqual(nepse_indices.snapshot_live_index(later)["saved"], 2)
        self.assertEqual(IndexIntradayPoint.objects.filter(index__code="NEPSE").count(), 2)

    def test_empty_feed_raises(self):
        with self.assertRaises(nepse_indices.IndexFeedError):
            nepse_indices.snapshot_live_index([])


def http_error(status):
    response = requests.Response()
    response.status_code = status
    return requests.HTTPError(f"{status} error", response=response)


class LiveIndexRetryTests(TestCase):
    def fetch(self, *outcomes):
        sleep = mock.Mock()
        with mock.patch.object(nepse_indices, "_get_live_index", side_effect=outcomes) as get:
            try:
                return nepse_indices.fetch_live_index(sleep=sleep), get.call_count, sleep
            except nepse_indices.IndexFeedError as exc:
                return exc, get.call_count, sleep

    def test_retries_throttling_then_succeeds(self):
        result, calls, sleep = self.fetch(http_error(429), [{"id": 58}])
        self.assertEqual((result, calls), ([{"id": 58}], 2))
        self.assertGreaterEqual(sleep.call_args[0][0], nepse_indices.LIVE_INDEX_BACKOFF_SECONDS)

    def test_backoff_doubles_and_stops_after_two_retries(self):
        result, calls, sleep = self.fetch(requests.Timeout("read"), http_error(503), http_error(403), [])
        self.assertIsInstance(result, nepse_indices.IndexFeedError)
        self.assertEqual(calls, 3)
        first, second = (call[0][0] for call in sleep.call_args_list)
        self.assertTrue(5 <= first < 6 and 10 <= second < 11)

    def test_other_errors_are_not_retried(self):
        result, calls, sleep = self.fetch(http_error(404))
        self.assertIsInstance(result, nepse_indices.IndexFeedError)
        self.assertEqual(calls, 1)
        sleep.assert_not_called()


class FakeRedis:
    def __init__(self):
        self.data = {}

    def exists(self, key):
        return key in self.data

    def ttl(self, key):
        return 1800

    def incr(self, key):
        self.data[key] = self.data.get(key, 0) + 1
        return self.data[key]

    def set(self, key, value, ex=None):
        self.data[key] = value

    def delete(self, key):
        self.data.pop(key, None)


class SnapshotTaskLoggingTests(TestCase):
    def setUp(self):
        from apps.market_indices import tasks

        self.redis = FakeRedis()
        patcher = mock.patch.object(tasks, "_breaker", return_value=self.redis)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_task(self, **snapshot):
        from apps.market_indices import tasks

        with mock.patch.object(tasks, "market_closed_reason", return_value=None),                 mock.patch.object(nepse_indices, "snapshot_live_index", **snapshot) as patched:
            return tasks.snapshot_live_index_task(), patched

    def test_three_failures_in_a_row_open_the_circuit(self):
        from apps.market_indices import tasks

        failing = {"side_effect": nepse_indices.IndexFeedError("503")}
        with self.assertLogs("apps.market_indices.tasks", "WARNING"):
            for _ in range(3):
                self.run_task(**failing)
            self.assertTrue(self.redis.exists(tasks.BREAKER_OPEN_KEY))
            result, snapshot = self.run_task(**failing)
        self.assertEqual(result["reason"], "circuit breaker open")
        snapshot.assert_not_called()

    def test_a_success_resets_the_failure_count(self):
        from apps.market_indices import tasks

        ok = {"return_value": {"saved": 1, "updated": 0, "unchanged": 0, "nepse": None}}
        with self.assertLogs("apps.market_indices.tasks", "WARNING"):
            self.run_task(side_effect=nepse_indices.IndexFeedError("timeout"))
            self.run_task(side_effect=nepse_indices.IndexFeedError("timeout"))
        self.run_task(**ok)
        with self.assertLogs("apps.market_indices.tasks", "WARNING"):
            self.run_task(side_effect=nepse_indices.IndexFeedError("timeout"))
        self.assertFalse(self.redis.exists(tasks.BREAKER_OPEN_KEY))

    def test_logs_and_skips_when_market_closed(self):
        from apps.market_indices import tasks

        with mock.patch.object(tasks, "market_closed_reason", return_value="Saturday is not a NEPSE trading day"),                 mock.patch.object(nepse_indices, "snapshot_live_index") as snapshot,                 self.assertLogs("apps.market_indices.tasks", "INFO") as logs:
            result = tasks.snapshot_live_index_task()
        self.assertTrue(result["skipped"])
        snapshot.assert_not_called()
        self.assertIn("market closed (Saturday is not a NEPSE trading day)", logs.output[0])

    def test_logs_warning_when_fetch_fails(self):
        from apps.market_indices import tasks

        with mock.patch.object(tasks, "market_closed_reason", return_value=None),                 mock.patch.object(nepse_indices, "snapshot_live_index",
                                  side_effect=nepse_indices.IndexFeedError("NEPSE live index failed: timeout")),                 self.assertLogs("apps.market_indices.tasks", "WARNING") as logs:
            result = tasks.snapshot_live_index_task()
        self.assertTrue(result["skipped"])
        self.assertIn("fetch failed, no ticks saved: NEPSE live index failed: timeout", logs.output[0])
