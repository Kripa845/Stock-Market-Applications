from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.companies.models import Company
from apps.crawler_runs.models import CrawlRun
from apps.market_data.models import Broker, FloorsheetTransaction
from apps.news.models import ArticleCompanyTag, NewsArticle, RawArticle
from apps.users.models import CustomRole, User, UserCompanyAccess


class BrokerAnalysisApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            symbol="TEST", name="Test Company", sector="Banking"
        )
        self.other = Company.objects.create(
            symbol="TST2", name="Second Test Company", sector="Finance"
        )
        self.user = User.objects.create_user(
            username="broker-api-admin",
            email="broker-api-admin@example.test",
            password="unused-test-password",
            role=User.Role.ADMIN,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self._create_tx("52", "44", 120, self.company, date(2026, 9, 10))
        self._create_tx("17", "52", 40, self.company, date(2026, 9, 12))
        self._create_tx("52", "88", 60, self.other, date(2026, 9, 12))

    @staticmethod
    def _create_tx(buyer, seller, quantity, company, when):
        return FloorsheetTransaction.objects.create(
            company=company,
            date=when,
            transaction_id=f"{buyer}-{seller}-{quantity}-{company.pk}-{when}",
            buyer_broker=buyer,
            seller_broker=seller,
            quantity=quantity,
            rate=Decimal("100.0000"),
        )

    def test_overview_aggregates_only_real_rows_and_lists_sampled_dates(self):
        response = self.client.get("/api/analysis/brokers/")
        self.assertEqual(response.status_code, 200, response.content[:500])
        self.assertEqual(response.data["summary"]["total_buy_quantity"], 220)
        self.assertEqual(response.data["summary"]["total_sell_quantity"], 220)
        self.assertEqual(response.data["summary"]["total_activity"], 440)
        self.assertEqual(response.data["summary"]["sampled_trading_days"], 2)
        self.assertEqual(set(response.data["broker_options"]), {"17", "44", "52", "88"})

    def test_overview_broker_name_uses_fallback_and_directory_name(self):
        response = self.client.get("/api/analysis/brokers/")
        broker_52 = next(row for row in response.data["results"] if row["broker"] == "52")
        self.assertEqual(broker_52["broker_name"], "Broker 52")

        Broker.objects.create(
            broker_no=52,
            broker_code="52",
            name="Naasa Securities Co. Ltd.",
        )
        response = self.client.get("/api/analysis/brokers/")
        broker_52 = next(row for row in response.data["results"] if row["broker"] == "52")
        self.assertEqual(broker_52["broker_name"], "Naasa Securities Co. Ltd.")

    def test_company_and_date_filters_apply_to_overview(self):
        response = self.client.get("/api/analysis/brokers/", {
            "company_id": self.company.pk,
            "start_date": "2026-09-11",
            "end_date": "2026-09-12",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["summary"]["total_buy_quantity"], 40)
        self.assertEqual(response.data["sampled_dates"], ["2026-09-12"])

    def test_invalid_date_range_is_rejected(self):
        response = self.client.get("/api/analysis/brokers/", {
            "start_date": "2026-09-20",
            "end_date": "2026-09-10",
        })
        self.assertEqual(response.status_code, 400)

    def test_detail_returns_daily_trend_and_existing_company_breakdown(self):
        response = self.client.get("/api/analysis/brokers/52/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["summary"]["buy_quantity"], 180)
        self.assertEqual(response.data["summary"]["sell_quantity"], 40)
        self.assertEqual(response.data["summary"]["net_quantity"], 140)
        self.assertEqual(len(response.data["daily_activity"]), 2)
        self.assertEqual({row["symbol"] for row in response.data["companies"]}, {"TEST", "TST2"})

    def test_missing_broker_returns_empty_not_fake_data(self):
        response = self.client.get("/api/analysis/brokers/9999/")
        self.assertEqual(response.status_code, 404)

    def test_seed_command_placeholder_floorsheet_rows_are_excluded(self):
        FloorsheetTransaction.objects.create(
            company=self.company,
            date=date(2026, 9, 13),
            transaction_id="TX-TEST-20260913-0001",
            buyer_broker="Broker-58",
            seller_broker="Broker-45",
            quantity=999999,
            rate=Decimal("100.0000"),
        )
        response = self.client.get("/api/analysis/brokers/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Broker-58", response.data["broker_options"])
        self.assertEqual(response.data["summary"]["transaction_count"], 3)

    def test_company_news_returns_only_articles_categorized_for_that_company(self):
        run = CrawlRun.objects.create(crawl_type="news", source="test")

        def make_article(slug, headline):
            url = f"https://example.test/{slug}"
            raw = RawArticle.objects.create(crawl_run=run, source="test", url=url)
            return NewsArticle.objects.create(
                raw_article=raw,
                source="Test Source",
                url=url,
                headline=headline,
                body="Article content",
                content_hash=slug,
            )

        categorized = make_article("company-news", "Company announces results")
        make_article("uncategorized-news", "Unrelated market headline")
        tagged_elsewhere = make_article("other-company-news", "Second company headline")
        ArticleCompanyTag.objects.create(
            article=categorized,
            company=self.company,
            confidence=0.94,
            method="symbol_match",
        )
        ArticleCompanyTag.objects.create(
            article=tagged_elsewhere,
            company=self.other,
            confidence=0.88,
            method="symbol_match",
        )

        response = self.client.get(
            f"/api/analysis/companies/{self.company.pk}/categorized-news/"
        )
        self.assertEqual(response.status_code, 200, response.content[:500])
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], categorized.pk)
        self.assertEqual(response.data["results"][0]["confidence"], 0.94)

    def test_global_overview_is_scoped_to_user_company_access(self):
        viewer = User.objects.create_user(
            username="broker-api-viewer",
            email="broker-api-viewer@example.test",
            password="unused-test-password",
            role=User.Role.VIEWER,
        )
        viewer.custom_role = CustomRole.objects.create(
            name="Broker API Viewer",
            permissions=["view_analysis"],
        )
        viewer.save(update_fields=["custom_role"])
        UserCompanyAccess.objects.create(user=viewer, company=self.company, status=1)
        restricted_client = APIClient()
        restricted_client.force_authenticate(viewer)

        response = restricted_client.get("/api/analysis/brokers/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["summary"]["total_buy_quantity"], 160)
        self.assertNotIn("88", response.data["broker_options"])

        denied = restricted_client.get(
            "/api/analysis/brokers/", {"company_id": self.other.pk}
        )
        self.assertEqual(denied.status_code, 403)

    def test_broker_activity_export_contains_aggregated_rows(self):
        response = self.client.get("/api/reports/export/brokers/?format=csv")
        body = response.content.decode("utf-8-sig")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Sampled Trading Sessions", body)
        self.assertIn("Broker-side Buy Qty", body)
        self.assertIn(",52,180,40,140,220,3", body)
