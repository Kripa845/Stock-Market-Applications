from datetime import date
from decimal import Decimal
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from apps.market_indices.models import IndexDaily, MarketIndex
from apps.market_indices.services import aggregates, nepse_indices, sharesansar_indices
from apps.users.models import User


def ss_row(day, close, open_="2621.49", turnover="4717028104.35", pct="0.17"):
    # Shape of ShareSansar's /index-history-data JSON rows.
    return {"index_id": 12, "open": open_, "high": "2630.57", "low": "2615.71", "current": close,
            "per_change": pct, "change_": "4.67", "turnover": turnover, "published_date": day}


class BackfillTests(TestCase):

    def setUp(self):
        call_command("seed_market_indices", stdout=mock.Mock())
        self.nepse = MarketIndex.objects.get(code="NEPSE")

    def backfill(self, rows, since=date(2026, 10, 1)):
        return sharesansar_indices.backfill_index_history(since, {"NEPSE": rows})

    def test_fills_missing_sessions_marked_as_sharesansar(self):
        result = self.backfill([ss_row("2026-10-15", "2625.93")])
        self.assertEqual((result["saved"], result["sessions"]), (1, ["2026-10-15"]))
        row = IndexDaily.objects.get(index=self.nepse, date=date(2026, 10, 15))
        self.assertEqual((row.close, row.source, row.volume, row.source_change_pct),
                         (Decimal("2625.93"), "sharesansar", None, Decimal("0.17")))

    def test_never_overwrites_nepse_rows(self):
        IndexDaily.objects.create(index=self.nepse, date=date(2026, 10, 15), open=Decimal("2621.41"),
                                  close=Decimal("2625.93"), turnover=Decimal("4643563830.60"), source="crawled")
        result = self.backfill([ss_row("2026-10-15", "2625.93")])
        self.assertEqual((result["saved"], result["kept_nepse"]), (0, 1))
        self.assertEqual(IndexDaily.objects.get(index=self.nepse, date=date(2026, 10, 15)).open, Decimal("2621.41"))

    def test_nepse_sync_later_replaces_the_fallback_row(self):
        self.backfill([ss_row("2026-10-15", "2625.93")])
        nepse_indices.sync_index_history(date(2026, 10, 1), {"NEPSE Index": [{
            "exchangeIndexId": 58, "businessDate": "2026-10-15", "openIndex": 2621.41, "highIndex": 2630.57,
            "lowIndex": 2615.71, "closingIndex": 2625.93, "turnoverValue": 4643563830.6,
            "turnoverVolume": 125e5, "totalTransaction": 38300, "percentageChange": 0.17}]})
        row = IndexDaily.objects.get(index=self.nepse, date=date(2026, 10, 15))
        self.assertEqual((row.source, row.volume), ("crawled", 12500000))

    def test_unfinished_and_garbage_rows_are_skipped(self):
        result = self.backfill([ss_row("2026-10-16", "0"), ss_row("bad", "1"), ss_row("2026-10-15", "")])
        self.assertEqual((result["saved"], result["skipped"]), (0, 3))
        self.assertFalse(IndexDaily.objects.exists())

    def test_index_table_reports_the_source(self):
        self.backfill([ss_row("2026-10-14", "2621.26"), ss_row("2026-10-15", "2625.93")])
        nepse = next(r for r in aggregates.index_table("main") if r["code"] == "NEPSE")
        self.assertEqual((nepse["source"], nepse["close"]), ("sharesansar", Decimal("2625.93")))


class FetchTests(TestCase):

    def test_requests_every_mapped_index_with_all_columns(self):
        session = mock.Mock()
        session.get.return_value.json.return_value = {"data": [ss_row("2026-10-15", "2625.93")]}
        history = sharesansar_indices.fetch_index_history(date(2026, 10, 6), date(2026, 10, 16),
                                                          session=session, sleep=lambda _: None)
        self.assertEqual(set(history), set(sharesansar_indices.SHARESANSAR_INDEX_IDS.values()))
        params = session.get.call_args_list[1].kwargs["params"]
        self.assertEqual((params["from"], params["to"], params["columns[4][data]"]), ("2026-10-06", "2026-10-16", "current"))

    def test_no_rows_at_all_raises(self):
        session = mock.Mock()
        session.get.return_value.json.return_value = {"data": []}
        with self.assertRaises(sharesansar_indices.ShareSansarIndexError):
            sharesansar_indices.fetch_index_history(date(2026, 10, 6), session=session, sleep=lambda _: None)


class ResyncFallbackTests(TestCase):

    def setUp(self):
        call_command("seed_market_indices", stdout=mock.Mock())
        self.client = APIClient()
        self.client.force_authenticate(User.objects.create_user(
            username="idx-admin", email="idx-admin@example.test", password="unused-test-password", role=User.Role.ADMIN))

    def test_resync_falls_back_to_sharesansar_when_nepse_fails(self):
        failure = nepse_indices.IndexFeedError("NEPSE index feed failed: 403")
        with mock.patch.object(nepse_indices, "fetch_index_history", side_effect=failure), \
             mock.patch("apps.market_indices.services.index_verification.fetch_index_history", side_effect=failure), \
             mock.patch.object(sharesansar_indices, "fetch_index_history",
                               return_value={"NEPSE": [ss_row("2026-10-15", "2625.93")]}):
            response = self.client.post("/api/market-indices/verify/")
        self.assertEqual(response.status_code, 200, response.content[:300])
        self.assertEqual(response.data["sync"]["fallback"], "sharesansar")
        self.assertFalse(response.data["feed_ok"])            # not verified against NEPSE: says so
        self.assertEqual(IndexDaily.objects.get().source, "sharesansar")
