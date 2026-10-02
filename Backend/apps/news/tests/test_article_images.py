from io import StringIO

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.crawler_runs.models import CrawlRun
from apps.news.models import NewsArticle, RawArticle
from apps.news.services.article_images import extract_image_url, normalize_image_url


PAGE = "https://www.sharesansar.com/newsdetail/some-article-2026-09-30"


def page(head="", body=""):
    return f"<html><head>{head}</head><body>{body}</body></html>"


class ExtractImageUrlTests(SimpleTestCase):

    def test_og_image(self):
        html = page('<meta property="og:image" content="https://cdn.example.com/a.jpg" />')
        self.assertEqual(extract_image_url(html, PAGE), "https://cdn.example.com/a.jpg")

    def test_og_secure_url_preferred(self):
        # MeroLagani publishes both; the https one wins.
        html = page(
            '<meta property="og:image" content="http://images.example.com/a.jpg">'
            '<meta property="og:image:secure_url" content="https://images.example.com/a.jpg">'
        )
        self.assertEqual(extract_image_url(html, PAGE), "https://images.example.com/a.jpg")

    def test_twitter_image_fallback(self):
        html = page('<meta name="twitter:image" content="https://cdn.example.com/t.png">')
        self.assertEqual(extract_image_url(html, PAGE), "https://cdn.example.com/t.png")

    def test_spaces_are_encoded(self):
        # Real ShareSansar value: "https://content.sharesansar.com/admin/Raju/appoint ceo.jpg"
        html = page('<meta property="og:image" content="https://content.sharesansar.com/admin/Raju/appoint ceo.jpg" />')
        self.assertEqual(
            extract_image_url(html, PAGE),
            "https://content.sharesansar.com/admin/Raju/appoint%20ceo.jpg",
        )

    def test_existing_escapes_not_double_encoded(self):
        self.assertEqual(
            normalize_image_url("https://cdn.example.com/a%20b.jpg?w=600&h=400"),
            "https://cdn.example.com/a%20b.jpg?w=600&h=400",
        )

    def test_relative_url_made_absolute(self):
        html = page('<meta property="og:image" content="/uploads/pic.jpg">')
        self.assertEqual(extract_image_url(html, PAGE), "https://www.sharesansar.com/uploads/pic.jpg")

    def test_logo_skipped_for_article_image(self):
        html = page(
            '<meta property="og:image" content="https://example.com/static/site-logo.png">',
            '<article><img src="https://example.com/uploads/story.jpg"></article>',
        )
        self.assertEqual(extract_image_url(html, PAGE), "https://example.com/uploads/story.jpg")

    def test_body_image_prefers_lazy_source(self):
        html = page(body=(
            '<div class="entry-content">'
            '<img src="data:image/gif;base64,R0lGOD" data-src="https://example.com/real.jpg">'
            '</div>'
        ))
        self.assertEqual(extract_image_url(html, PAGE), "https://example.com/real.jpg")

    def test_no_image(self):
        self.assertEqual(extract_image_url(page(body="<p>text only</p>"), PAGE), "")
        self.assertEqual(extract_image_url("", PAGE), "")

    def test_rejects_non_http_and_svg(self):
        self.assertEqual(normalize_image_url("javascript:alert(1)"), "")
        self.assertEqual(normalize_image_url("data:image/png;base64,AAAA"), "")
        self.assertEqual(normalize_image_url("https://example.com/chart.svg"), "")


class BackfillNewsImagesCommandTests(TestCase):

    def setUp(self):
        self.crawl_run = CrawlRun.objects.create(
            status=CrawlRun.Status.SUCCESS,
            started_at=timezone.now(),
            sources=["sharesansar"],
        )

    def _article(self, url, raw_html, image_url=""):
        raw = RawArticle.objects.create(
            crawl_run=self.crawl_run, source="sharesansar", url=url, http_status=200, raw_html=raw_html,
        )
        return NewsArticle.objects.create(
            raw_article=raw, source="sharesansar", url=url, headline=url, body="body",
            published_at=timezone.now(), content_hash=url, image_url=image_url,
        )

    def test_fills_missing_images_from_stored_html(self):
        with_image = self._article(
            "https://example.com/1", page('<meta property="og:image" content="https://example.com/1.jpg">'),
        )
        without_image = self._article("https://example.com/2", page(body="<p>no picture</p>"))
        already_set = self._article(
            "https://example.com/3",
            page('<meta property="og:image" content="https://example.com/new.jpg">'),
            image_url="https://example.com/kept.jpg",
        )

        out = StringIO()
        call_command("backfill_news_images", stdout=out)

        with_image.refresh_from_db()
        without_image.refresh_from_db()
        already_set.refresh_from_db()
        self.assertEqual(with_image.image_url, "https://example.com/1.jpg")
        self.assertEqual(without_image.image_url, "")
        self.assertEqual(already_set.image_url, "https://example.com/kept.jpg")
        self.assertIn("Set image_url on 1 article(s); no image found for 1.", out.getvalue())

    def test_dry_run_saves_nothing(self):
        article = self._article(
            "https://example.com/1", page('<meta property="og:image" content="https://example.com/1.jpg">'),
        )
        call_command("backfill_news_images", "--dry-run", stdout=StringIO())
        article.refresh_from_db()
        self.assertEqual(article.image_url, "")

    def test_force_re_extracts(self):
        article = self._article(
            "https://example.com/1",
            page('<meta property="og:image" content="https://example.com/new.jpg">'),
            image_url="https://example.com/old.jpg",
        )
        call_command("backfill_news_images", "--force", stdout=StringIO())
        article.refresh_from_db()
        self.assertEqual(article.image_url, "https://example.com/new.jpg")
