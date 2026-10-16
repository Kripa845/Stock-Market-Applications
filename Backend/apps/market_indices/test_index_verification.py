from copy import deepcopy
from datetime import date
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from apps.market_indices.models import IndexDaily
from apps.market_indices.services import index_verification, nepse_indices
from apps.market_indices.test_nepse_indices import HISTORY
from apps.users.models import User

SESSION = date(2026, 10, 12)


class IndexVerificationTests(TestCase):

    def setUp(self):
        cache.clear()
        call_command("seed_market_indices", stdout=mock.Mock())
        nepse_indices.sync_index_history(date(2026, 10, 1), HISTORY)

    def by_code(self, result):
        return {row["code"]: row for row in result["rows"]}

    def test_stored_rows_matching_the_feed_are_scraped(self):
        result = index_verification.verify_session(history=HISTORY)
        rows = self.by_code(result)
        self.assertEqual(result["session"], SESSION)
        self.assertTrue(result["feed_ok"])
        self.assertEqual(rows["NEPSE"]["status"], "scraped")
        self.assertTrue(rows["NEPSE"]["verified"])
        # Manufacturing has no 2026-10-09 row: change columns cannot be computed.
        self.assertEqual(rows["MANUFACTURE"]["status"], "missing")
        self.assertEqual(rows["MANUFACTURE"]["missing"], ["previous_session"])
        # Catalogued but never scraped.
        self.assertEqual(rows["HYDROPOWER"]["status"], "missing")
        self.assertIn("close", rows["HYDROPOWER"]["missing"])
        self.assertEqual(result["summary"], {"scraped": 3, "missing": 14, "mismatch": 0, "total": 17})

    def test_revised_feed_values_are_mismatches_with_both_values(self):
        revised = deepcopy(HISTORY)
        revised["NEPSE Index"][1]["turnoverValue"] = 4392e6
        rows = self.by_code(index_verification.verify_session(history=revised))
        self.assertEqual(rows["NEPSE"]["status"], "mismatch")
        self.assertEqual(rows["NEPSE"]["mismatches"], [
            {"field": "turnover", "stored": Decimal("4391000000.00"), "source": Decimal("4392000000.0")},
        ])

    def test_resync_overwrites_without_duplicates(self):
        revised = deepcopy(HISTORY)
        revised["NEPSE Index"][1]["turnoverValue"] = 4392e6
        with mock.patch.object(index_verification, "fetch_index_history", return_value=revised):
            _, result = index_verification.resync_session()
        self.assertEqual(self.by_code(result)["NEPSE"]["status"], "scraped")
        self.assertEqual(IndexDaily.objects.filter(index__code="NEPSE", date=SESSION).count(), 1)
        self.assertEqual(IndexDaily.objects.get(index__code="NEPSE", date=SESSION).turnover, Decimal("4392000000.00"))

    def test_feed_down_checks_presence_only(self):
        with mock.patch.object(index_verification, "fetch_index_history", side_effect=nepse_indices.IndexFeedError("down")):
            result = index_verification.verify_session()
        rows = self.by_code(result)
        self.assertFalse(result["feed_ok"])
        self.assertEqual(rows["NEPSE"]["status"], "scraped")
        self.assertFalse(rows["NEPSE"]["verified"])

    def test_api_permissions(self):
        viewer = User.objects.create_user(
            username="v", email="v@example.test", password="unused-test-password", role=User.Role.VIEWER,
        )
        client = APIClient()
        client.force_authenticate(viewer)
        with mock.patch.object(index_verification, "fetch_index_history", return_value=HISTORY):
            response = client.get("/api/market-indices/verify/")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["summary"]["scraped"], 3)
            self.assertEqual(client.post("/api/market-indices/verify/").status_code, 403)
            self.assertEqual(client.get("/api/market-indices/verify/", {"date": "bad"}).status_code, 400)
