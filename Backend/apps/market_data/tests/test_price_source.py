from django.test import TestCase


class PriceSourceParamTests(TestCase):
    def test_unknown_source_is_rejected(self):
        from rest_framework.test import APIClient
        from apps.users.models import User

        client = APIClient()
        client.force_authenticate(User.objects.create_user(
            username="source-admin", email="source-admin@example.test", password="x", role=User.Role.ADMIN,
        ))
        self.assertEqual(client.get("/api/market-data/", {"source": "bogus"}).status_code, 400)
        self.assertEqual(client.get("/api/market-data/", {"source": "seeded"}).status_code, 200)
