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

    def test_top_brokers_defaults_to_latest_complete_day_and_ranks_by_turnover(self):
        # 2026-09-12: 52 buys 60 TST2 (6,000) and sells 40 TEST (4,000) -> 10,000;
        # 88 sells 6,000; 17 buys 4,000.
        response = self.client.get("/api/analysis/brokers/top/")
        self.assertEqual(response.status_code, 200, response.content[:500])
        self.assertEqual(response.data["date"], "2026-09-12")
        self.assertTrue(response.data["is_complete"])
        self.assertEqual(response.data["companies"], 2)
        self.assertEqual([row["broker"] for row in response.data["results"]], ["52", "88", "17"])
        self.assertEqual([row["broker"] for row in response.data["podium"]], ["52", "88", "17"])
        self.assertEqual(Decimal(response.data["results"][0]["total_value"]), Decimal("10000"))

        summary = response.data["summary"]
        self.assertEqual(Decimal(summary["total_amount"]), Decimal("10000"))  # each trade once
        self.assertEqual(summary["total_quantity"], 100)
        self.assertEqual(summary["transaction_count"], 2)
        self.assertEqual(summary["active_brokers"], 3)

    def test_top_brokers_top_stock_is_highest_turnover_symbol(self):
        response = self.client.get("/api/analysis/brokers/top/", {"date": "2026-09-12"})
        top = response.data["results"][0]["top_stock"]
        self.assertEqual(top["symbol"], "TST2")
        self.assertEqual(Decimal(top["buy_amount"]), Decimal("6000"))
        self.assertEqual(Decimal(top["sell_amount"]), Decimal("0"))
        self.assertEqual(Decimal(top["turnover"]), Decimal("6000"))

    def test_top_brokers_lists_top_stocks_with_share_and_count(self):
        # Broker 52 on 2026-09-12: buys 6,000 of TST2, sells 4,000 of TEST.
        response = self.client.get("/api/analysis/brokers/top/", {"date": "2026-09-12"})
        row = next(r for r in response.data["results"] if r["broker"] == "52")
        self.assertEqual(row["stock_count"], 2)
        self.assertEqual([s["symbol"] for s in row["top_stocks"]], ["TST2", "TEST"])
        first, second = row["top_stocks"]
        self.assertEqual(first["name"], "Second Test Company")
        self.assertEqual((Decimal(first["buy_amount"]), Decimal(first["sell_amount"])), (Decimal("6000"), Decimal("0")))
        self.assertEqual((first["buy_quantity"], first["sell_quantity"]), (60, 0))
        self.assertEqual((second["buy_quantity"], second["sell_quantity"]), (0, 40))
        self.assertEqual((Decimal(first["share_pct"]), Decimal(second["share_pct"])), (Decimal("60.00"), Decimal("40.00")))
        self.assertEqual(set(first), {
            "symbol", "name", "logo_url", "buy_amount", "sell_amount",
            "buy_quantity", "sell_quantity", "turnover", "share_pct",
        })

    def test_top_brokers_top_stock_keeps_shape_and_is_first_of_top_stocks(self):
        response = self.client.get("/api/analysis/brokers/top/", {"date": "2026-09-12"})
        for row in response.data["results"]:
            self.assertEqual(set(row["top_stock"]), {"symbol", "logo_url", "buy_amount", "sell_amount", "turnover"})
            self.assertEqual(row["top_stock"]["symbol"], row["top_stocks"][0]["symbol"])
            self.assertEqual(row["top_stock"]["turnover"], row["top_stocks"][0]["turnover"])
        podium_52 = next(r for r in response.data["podium"] if r["broker"] == "52")
        self.assertEqual(podium_52["top_stock"]["symbol"], "TST2")

    def test_top_brokers_top_stocks_capped_at_ten(self):
        for n in range(12):
            company = Company.objects.create(symbol=f"CAP{n:02d}", name=f"Cap {n}", sector="Banking")
            self._create_tx("52", "99", 10 + n, company, date(2026, 9, 12))
        response = self.client.get("/api/analysis/brokers/top/", {"date": "2026-09-12"})
        row = next(r for r in response.data["results"] if r["broker"] == "52")
        self.assertEqual(row["stock_count"], 14)
        self.assertEqual(len(row["top_stocks"]), 10)
        turnovers = [Decimal(s["turnover"]) for s in row["top_stocks"]]
        self.assertEqual(turnovers, sorted(turnovers, reverse=True))

    def test_top_brokers_top_stocks_respect_company_access(self):
        viewer = User.objects.create_user(
            username="top-stocks-viewer", email="top-stocks-viewer@example.test",
            password="unused-test-password", role=User.Role.VIEWER,
        )
        viewer.custom_role = CustomRole.objects.create(name="Top Stocks Viewer", permissions=["view_analysis"])
        viewer.save(update_fields=["custom_role"])
        UserCompanyAccess.objects.create(user=viewer, company=self.company, status=1)
        restricted = APIClient()
        restricted.force_authenticate(viewer)

        response = restricted.get("/api/analysis/brokers/top/", {"date": "2026-09-12"})
        self.assertEqual(response.status_code, 200)
        for row in response.data["results"]:
            self.assertEqual({s["symbol"] for s in row["top_stocks"]}, {"TEST"})
        row_52 = next(r for r in response.data["results"] if r["broker"] == "52")
        self.assertEqual((row_52["stock_count"], Decimal(row_52["top_stocks"][0]["share_pct"])), (1, Decimal("100.00")))

    def test_top_brokers_flags_partial_day_and_lists_available_dates(self):
        response = self.client.get("/api/analysis/brokers/top/", {"date": "2026-09-10"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_complete"])
        self.assertEqual(response.data["companies"], 1)
        self.assertEqual(response.data["expected_companies"], 2)
        self.assertEqual(
            [(d["date"], d["is_complete"]) for d in response.data["available_dates"]],
            [("2026-09-12", True), ("2026-09-10", False)],
        )

    def test_top_brokers_rejects_bad_date_and_returns_empty_for_day_without_trades(self):
        self.assertEqual(self.client.get("/api/analysis/brokers/top/", {"date": "12-09-2026"}).status_code, 400)
        response = self.client.get("/api/analysis/brokers/top/", {"date": "2026-09-11"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [])
        self.assertEqual(response.data["podium"], [])
        self.assertEqual(response.data["summary"]["transaction_count"], 0)

    def test_detail_returns_daily_trend_and_existing_company_breakdown(self):
        response = self.client.get("/api/analysis/brokers/52/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["summary"]["buy_quantity"], 180)
        self.assertEqual(response.data["summary"]["sell_quantity"], 40)
        self.assertEqual(response.data["summary"]["net_quantity"], 140)
        self.assertEqual(len(response.data["daily_activity"]), 2)
        self.assertEqual({row["symbol"] for row in response.data["companies"]}, {"TEST", "TST2"})

    def test_detail_lists_every_session_including_days_broker_did_not_trade(self):
        response = self.client.get("/api/analysis/brokers/88/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["sampled_dates"], ["2026-09-12"])
        self.assertEqual(response.data["trading_sessions"], ["2026-09-10", "2026-09-12"])

    def test_detail_includes_broker_profile_from_directory(self):
        Broker.objects.create(
            broker_no=52,
            broker_code="52",
            name="Sweta Securities Pvt. Ltd.",
            short_name="Sweta",
            logo="52.png",
            website="https://example.test",
            tms_link="tms52.nepsetms.com.np",
        )
        response = self.client.get("/api/analysis/brokers/52/")
        self.assertEqual(response.status_code, 200)
        profile = response.data["profile"]
        self.assertEqual(profile["name"], "Sweta Securities Pvt. Ltd.")
        self.assertEqual(profile["logo_url"], "/broker-logos/52.png")
        self.assertEqual(profile["tms_link"], "tms52.nepsetms.com.np")
        self.assertTrue(profile["in_directory"])

    def test_detail_profile_falls_back_for_unlisted_broker(self):
        profile = self.client.get("/api/analysis/brokers/52/").data["profile"]
        self.assertEqual(profile["name"], "Broker 52")
        self.assertIsNone(profile["logo_url"])
        self.assertFalse(profile["in_directory"])

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
