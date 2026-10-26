from decimal import Decimal

from rest_framework.test import APIClient

from apps.market_data.tests.test_market_stats import MONDAY, TUESDAY, TrackedMarketFixture
from apps.users.models import User, Watchlist, WatchlistItem


class NamedWatchlistApiTests(TrackedMarketFixture):

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username="watcher", email="watcher@example.test",
            password="unused-test-password", role=User.Role.ADMIN,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def primary(self):
        lists = self.client.get("/api/market/watchlists/").data["results"]
        self.assertEqual([(w["name"], w["is_default"]) for w in lists], [("Primary", True)])
        return lists[0]["id"]

    def test_add_any_active_company_with_holding(self):
        pk = self.primary()
        created = self.client.post(f"/api/market/watchlists/{pk}/items/", {"symbol": "out"}, format="json")
        self.assertEqual(created.status_code, 201)  # untracked companies can be saved too
        self.assertEqual(created.data["symbol"], "OUT")
        self.assertEqual(created.data["ltp"], Decimal("150"))
        self.assertEqual(created.data["change"], Decimal("50"))
        self.assertEqual(created.data["change_pct"], Decimal("50.00"))
        self.assertEqual([p["date"] for p in created.data["sparkline"]], [MONDAY, TUESDAY])

        again = self.client.post(f"/api/market/watchlists/{pk}/items/", {"symbol": "OUT"}, format="json")
        self.assertEqual(again.status_code, 400)
        self.assertEqual(self.client.post(f"/api/market/watchlists/{pk}/items/", {"symbol": "NOPE"}).status_code, 404)

        item_id = created.data["id"]
        edited = self.client.patch(
            f"/api/market/watchlists/{pk}/items/{item_id}/", {"units": 10, "wacc": "120"}, format="json",
        )
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(edited.data["investment"], Decimal("1200.00"))
        self.assertEqual(edited.data["current_value"], Decimal("1500.00"))
        self.assertEqual(edited.data["profit"], Decimal("300.00"))
        self.assertEqual(edited.data["profit_pct"], Decimal("25.00"))
        bad = self.client.patch(f"/api/market/watchlists/{pk}/items/{item_id}/", {"units": -1}, format="json")
        self.assertEqual(bad.status_code, 400)

        self.client.post(f"/api/market/watchlists/{pk}/items/", {"symbol": "LOSE", "units": 10, "wacc": 200}, format="json")
        listing = self.client.get(f"/api/market/watchlists/{pk}/items/").data
        self.assertEqual([row["symbol"] for row in listing["rows"]], ["LOSE", "OUT"])
        self.assertEqual(listing["summary"]["total_units"], 20)
        self.assertEqual(listing["summary"]["average_wacc"], Decimal("160.00"))
        self.assertEqual(listing["summary"]["investment"], Decimal("3200.00"))
        self.assertEqual(listing["summary"]["current_value"], Decimal("3400.00"))
        self.assertEqual(listing["summary"]["profit"], Decimal("200.00"))

        self.assertEqual(self.client.delete(f"/api/market/watchlists/{pk}/items/{item_id}/").status_code, 204)
        self.assertEqual(WatchlistItem.objects.count(), 1)

    def test_lists_are_named_per_user_and_default_moves_on_delete(self):
        primary = self.primary()
        banks = self.client.post("/api/market/watchlists/", {"name": "Banks"}, format="json")
        self.assertEqual(banks.status_code, 201)
        self.assertFalse(banks.data["is_default"])
        self.assertEqual(self.client.post("/api/market/watchlists/", {"name": "banks"}, format="json").status_code, 400)

        starred = self.client.patch(f"/api/market/watchlists/{banks.data['id']}/", {"is_default": True}, format="json")
        self.assertTrue(starred.data["is_default"])
        self.assertFalse(Watchlist.objects.get(pk=primary).is_default)

        # the old single-list endpoint follows the default list
        self.client.post("/api/market/watchlist/", {"symbol": "GAIN"}, format="json")
        self.assertEqual(WatchlistItem.objects.get().watchlist_id, banks.data["id"])

        self.assertEqual(self.client.delete(f"/api/market/watchlists/{banks.data['id']}/").status_code, 204)
        self.assertTrue(Watchlist.objects.get(pk=primary).is_default)
        self.assertFalse(WatchlistItem.objects.exists())

        other = User.objects.create_user(
            username="other", email="other@example.test", password="unused-test-password", role=User.Role.ADMIN,
        )
        client = APIClient()
        client.force_authenticate(other)
        self.assertEqual(client.get(f"/api/market/watchlists/{primary}/items/").status_code, 404)
