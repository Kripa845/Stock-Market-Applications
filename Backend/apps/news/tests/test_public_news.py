from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.crawler_runs.models import CrawlRun
from apps.news.models import NewsArticle, RawArticle


class PublicLatestNewsTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("news-public-latest")
        self.crawl_run = CrawlRun.objects.create(
            status=CrawlRun.Status.SUCCESS, started_at=timezone.now(), sources=["sharesansar"],
        )
        self.now = timezone.now()

    def _article(self, n, *, hours_ago=0, provenance="crawled", body="word " * 20, image_url=""):
        url = f"https://www.sharesansar.com/newsdetail/{n}"
        raw = RawArticle.objects.create(crawl_run=self.crawl_run, source="ShareSansar", url=url, http_status=200)
        return NewsArticle.objects.create(
            raw_article=raw, source="ShareSansar", url=url, headline=f"Headline {n}", body=body,
            published_at=self.now - timedelta(hours=hours_ago), content_hash=str(n),
            data_provenance=provenance, image_url=image_url,
        )

    def test_anonymous_access_newest_first(self):
        self._article(1, hours_ago=5)
        self._article(2, hours_ago=1, image_url="https://content.sharesansar.com/a.jpg")
        self._article(3, hours_ago=3)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([a["headline"] for a in response.data], ["Headline 2", "Headline 3", "Headline 1"])
        self.assertEqual(response.data[0]["image_url"], "https://content.sharesansar.com/a.jpg")

    def test_only_public_fields(self):
        self._article(1)
        row = self.client.get(self.url).data[0]
        self.assertEqual(
            set(row), {"id", "headline", "excerpt", "source", "url", "image_url", "published_at"},
        )

    def test_invalid_token_is_ignored(self):
        # A logged-out visitor may still carry an expired token; the landing page must load anyway.
        self._article(1)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer expired.or.invalid")
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_excludes_non_crawled_and_far_future(self):
        self._article(1, provenance="unverified")
        self._article(2, hours_ago=-24 * 365 * 56)  # Bikram Sambat year read as AD
        self._article(3)
        self.assertEqual([a["headline"] for a in self.client.get(self.url).data], ["Headline 3"])

    def test_limit_default_and_clamped(self):
        for n in range(15):
            self._article(n, hours_ago=n)
        self.assertEqual(len(self.client.get(self.url).data), 6)
        self.assertEqual(len(self.client.get(self.url, {"limit": 3}).data), 3)
        self.assertEqual(len(self.client.get(self.url, {"limit": 500}).data), 12)
        self.assertEqual(len(self.client.get(self.url, {"limit": "abc"}).data), 6)

    def test_excerpt_is_short(self):
        self._article(1, body="long " * 200)
        excerpt = self.client.get(self.url).data[0]["excerpt"]
        self.assertLessEqual(len(excerpt), 181)
        self.assertTrue(excerpt.endswith("…"))
