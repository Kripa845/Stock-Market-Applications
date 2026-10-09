"""Synthetic (seeded) data and made-up defaults must never reach an API response."""

from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.companies.models import Company, TrackedCompany
from apps.crawler_runs.models import CrawlRun
from apps.market_data.models import DailyPrice
from apps.news.models import ArticleCompanyTag, NewsArticle, RawArticle
from apps.users.models import User


class NoSyntheticDataTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(User.objects.create_user(
            username="integrity-admin", email="integrity@example.test",
            password="unused-test-password", role=User.Role.ADMIN,
        ))
        self.company = Company.objects.create(symbol="NABIL", name="Nabil Bank", sector="Commercial Bank")
        TrackedCompany.objects.create(company=self.company, is_tracked=True)
        run = CrawlRun.objects.create(status=CrawlRun.Status.SUCCESS, started_at=timezone.now(), sources=["x"])
        for n, provenance in ((1, "crawled"), (2, "unverified"), (3, "seeded")):
            url = f"https://example.test/news/{n}"
            raw = RawArticle.objects.create(crawl_run=run, source="ShareSansar", url=url, http_status=200)
            article = NewsArticle.objects.create(
                raw_article=raw, source="ShareSansar", url=url, headline=f"{provenance} article", body="body",
                published_at=timezone.now(), content_hash=f"h{n}", data_provenance=provenance, sentiment=0.5,
            )
            ArticleCompanyTag.objects.create(article=article, company=self.company, confidence=0.95, method="symbol")

    def test_seeded_news_hidden_from_feed_and_stats(self):
        headlines = [row["headline"] for row in self.client.get("/api/news/").data["results"]]
        self.assertEqual(sorted(headlines), ["crawled article", "unverified article"])
        self.assertEqual(self.client.get("/api/news/stats/").data["total_articles"], 2)
        seeded = NewsArticle.objects.get(data_provenance="seeded")
        self.assertEqual(self.client.get(f"/api/news/{seeded.id}/").status_code, 404)

    def test_company_counts_exclude_seeded_news(self):
        row = self.client.get(f"/api/companies/{self.company.id}/").data
        self.assertEqual(row["news_count"], 2)

    def test_company_without_prices_has_nulls_not_zeros(self):
        row = self.client.get(f"/api/companies/{self.company.id}/").data
        for field in ("latest_price", "price_change", "price_change_percent", "volume_24h",
                      "turnover_24h", "high_24h", "low_24h"):
            self.assertIsNone(row[field], field)

    def test_company_change_uses_movers_definition(self):
        # 566.00 -> 530.70 close-to-close is -6.24%; ShareSansar's adjusted % is -1.55%.
        for day, close, pct in ((date(2026, 9, 29), "566.00", None), (date(2026, 9, 30), "530.70", "-1.55")):
            DailyPrice.objects.create(
                company=self.company, source="crawled", date=day, open=close, high=close, low=close,
                close=close, volume=100, turnover=1000, source_change_pct=pct,
            )
        row = self.client.get(f"/api/companies/{self.company.id}/").data
        self.assertEqual(row["latest_price"], 530.7)
        self.assertEqual(row["price_change_percent"], -1.55)

    def test_cross_company_has_no_made_up_volatility(self):
        DailyPrice.objects.create(company=self.company, source="crawled", date=timezone.localdate(),
                                  open=Decimal("100"), high=Decimal("100"), low=Decimal("100"), close=Decimal("100"),
                                  volume=100, turnover=1000)
        stat = self.client.get("/api/analysis/cross-company/").data["companies"][0]
        self.assertIsNone(stat["volatility"])       # was a hardcoded 1.5
        self.assertIsNone(stat["change_pct"])       # no previous session: unknown, not 0
        self.assertEqual(self.client.get("/api/analysis/cross-company/").data["most_volatile"], [])
