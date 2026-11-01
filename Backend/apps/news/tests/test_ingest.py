from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest import mock
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from apps.companies.models import Company
from apps.crawler_runs.models import CrawlRun
from apps.news.models import ArticleCompanyTag, ArticleLike, NewsArticle, NewsSource, RawArticle
from apps.news.services import dedupe
from apps.news.services import ingest as ingest_mod
from apps.news.services.ingest import IngestRejected, ingest_article, resolve_source
from apps.news.services.normalize import (
    canonical_title,
    compute_canonical_hash,
    compute_content_hash,
    normalize_url,
)
from apps.news.tests.factories import news_source_for

NPT = ZoneInfo("Asia/Kathmandu")
WHEN = datetime(2026, 10, 20, 11, 0, tzinfo=NPT)


class NormalizeTests(TestCase):
    def test_strips_tracking_fragment_slash_and_www(self):
        self.assertEqual(
            normalize_url("https://WWW.ShareSansar.com/newsdetail/abc/?utm_source=fb&fbclid=x#top"),
            "https://sharesansar.com/newsdetail/abc",
        )

    def test_keeps_identifying_query_and_path_case(self):
        self.assertEqual(
            normalize_url("https://merolagani.com/NewsDetail.aspx?newsID=131443&utm_medium=x"),
            "https://merolagani.com/NewsDetail.aspx?newsID=131443",
        )

    def test_relative_or_empty_url_has_no_identity(self):
        self.assertEqual(normalize_url("/news/1"), "")
        self.assertEqual(normalize_url(""), "")
        self.assertEqual(normalize_url("mailto:news@sharesansar.com"), "")

    def test_http_and_https_are_one_identity(self):
        self.assertEqual(
            normalize_url("http://www.sharesansar.com/newsdetail/abc"),
            normalize_url("https://sharesansar.com/newsdetail/abc/"),
        )

    def test_canonical_title_folds_digits_and_punctuation(self):
        self.assertEqual(canonical_title("  नेप्से ३ अंकले बढ्यो! "), "नेप्से 3 अंकले बढ्यो")
        self.assertEqual(canonical_title("NABIL: Q1 Profit up 10%"), "nabil q1 profit up 10")

    def test_vowel_signs_keep_words_apart(self):
        self.assertNotEqual(canonical_title("कम मूल्यमा शेयर बिक्री"), canonical_title("काम मूल्यमा शेयर बिक्री"))

    def test_short_titles_are_not_grouped(self):
        self.assertEqual(compute_canonical_hash("सूचना"), "")


class IngestTests(TestCase):
    def setUp(self):
        self.run = CrawlRun.objects.create(crawl_type="news")
        self.sharesansar = news_source_for("ShareSansar")
        self.merolagani = news_source_for("MeroLagani")

    def item(self, **overrides):
        item = {
            "url": "https://www.sharesansar.com/newsdetail/nabil-dividend",
            "headline": "Nabil Bank announces 30 percent dividend",
            "body": "The board of Nabil Bank proposed a dividend.",
            "published_at": WHEN,
        }
        item.update(overrides)
        return item

    def ingest(self, source=None, **overrides):
        return ingest_article((source or self.sharesansar).pk, self.item(**overrides), ingest_run_id=self.run.pk)

    def test_insert_records_source_and_run(self):
        result = self.ingest()
        self.assertEqual(result.status, "inserted")
        article = NewsArticle.objects.get(pk=result.article_id)
        self.assertEqual(article.news_source, self.sharesansar)
        self.assertEqual(article.source, "ShareSansar")
        self.assertEqual(article.ingest_run, self.run)
        self.assertEqual(article.raw_article.crawl_run, self.run)
        self.assertEqual(article.data_provenance, "crawled")

    def test_rerun_is_idempotent(self):
        first = self.ingest()
        before = NewsArticle.objects.get(pk=first.article_id).last_seen_at
        again = self.ingest(url="https://sharesansar.com/newsdetail/nabil-dividend/?utm_source=x")
        self.assertEqual((again.status, again.article_id), ("duplicate", first.article_id))
        self.assertEqual(NewsArticle.objects.count(), 1)
        self.assertGreaterEqual(NewsArticle.objects.get(pk=first.article_id).last_seen_at, before)

    def test_edited_article_is_updated_in_place(self):
        first = self.ingest()
        old_hash = NewsArticle.objects.get(pk=first.article_id).content_hash
        result = self.ingest(body="The board of Nabil Bank proposed a 30% cash dividend.")
        self.assertEqual((result.status, result.article_id), ("updated", first.article_id))
        article = NewsArticle.objects.get(pk=first.article_id)
        self.assertNotEqual(article.content_hash, old_hash)
        self.assertIn("cash dividend", article.body)

    def test_edit_queues_sentiment_rescore_and_records_run(self):
        first = self.ingest()
        NewsArticle.objects.filter(pk=first.article_id).update(sentiment_status="ok", sentiment=0.4)
        later_run = CrawlRun.objects.create(crawl_type="news")
        ingest_article(self.sharesansar.pk, self.item(body="Rewritten with new figures."), ingest_run_id=later_run.pk)
        article = NewsArticle.objects.get(pk=first.article_id)
        self.assertEqual(article.sentiment_status, "pending")
        self.assertEqual(article.ingest_run, self.run)  # still the inserting run
        self.assertEqual(article.raw_article.crawl_run, later_run)

    def test_unchanged_rerun_keeps_sentiment(self):
        first = self.ingest()
        NewsArticle.objects.filter(pk=first.article_id).update(sentiment_status="ok")
        self.ingest()
        self.assertEqual(NewsArticle.objects.get(pk=first.article_id).sentiment_status, "ok")

    def test_edited_article_seen_over_http_is_not_a_new_row(self):
        first = self.ingest()
        result = self.ingest(url="http://sharesansar.com/newsdetail/nabil-dividend", body="Corrected text.")
        self.assertEqual((result.status, result.article_id), ("updated", first.article_id))
        self.assertEqual(NewsArticle.objects.count(), 1)

    def test_concurrent_insert_falls_back_to_update(self):
        """The row another worker committed between lookup and insert is updated, not duplicated."""
        first = self.ingest()
        real_find = ingest_mod._find_existing
        calls = []

        def miss_once(*args, **kwargs):
            calls.append(1)
            return None if len(calls) == 1 else real_find(*args, **kwargs)

        with mock.patch.object(ingest_mod, "_find_existing", side_effect=miss_once):
            result = self.ingest(body="Edited while another worker inserted it.")
        self.assertEqual((result.status, result.article_id), ("updated", first.article_id))
        self.assertEqual(NewsArticle.objects.count(), 1)

    def test_external_id_identifies_across_url_changes(self):
        first = self.ingest(external_id="131443")
        result = self.ingest(url="https://www.sharesansar.com/newsdetail/renamed-slug", external_id="131443")
        self.assertEqual((result.status, result.article_id), ("duplicate", first.article_id))

    def test_same_source_exact_copy_under_new_url_is_duplicate(self):
        first = self.ingest()
        result = self.ingest(url="https://www.sharesansar.com/newsdetail/nabil-dividend-copy")
        self.assertEqual((result.status, result.article_id), ("duplicate", first.article_id))
        self.assertEqual(NewsArticle.objects.count(), 1)

    def test_cross_source_story_is_kept_and_linked(self):
        root = self.ingest()
        copy = self.ingest(
            source=self.merolagani,
            url="https://merolagani.com/NewsDetail.aspx?newsID=1",
            headline="NABIL Bank announces 30 percent dividend!",
            body="Different write-up of the same news.",
            published_at=WHEN + timedelta(hours=5),
        )
        self.assertEqual(copy.status, "inserted")
        self.assertEqual(copy.duplicate_of_id, root.article_id)
        self.assertEqual(NewsArticle.objects.get(pk=root.article_id).also_reported.count(), 1)

    def test_same_title_far_apart_is_not_linked(self):
        self.ingest()
        later = self.ingest(
            source=self.merolagani,
            url="https://merolagani.com/NewsDetail.aspx?newsID=2",
            body="Next year's announcement.",
            published_at=WHEN + timedelta(days=300),
        )
        self.assertIsNone(later.duplicate_of_id)

    def test_own_portal_story_is_not_linked_through_another_portals_copy(self):
        root = self.ingest()
        self.ingest(source=self.merolagani, url="https://merolagani.com/NewsDetail.aspx?newsID=1",
                    body="MeroLagani's copy.")
        follow_up = self.ingest(url="https://www.sharesansar.com/newsdetail/nabil-dividend-2",
                                body="A different ShareSansar article, same title.",
                                published_at=WHEN + timedelta(days=1))
        self.assertEqual(follow_up.status, "inserted")
        self.assertIsNone(follow_up.duplicate_of_id)
        self.assertEqual(NewsArticle.objects.get(pk=root.article_id).also_reported.count(), 1)

    def test_rejects_items_without_provenance_or_required_fields(self):
        cases = [
            dict(url=""),
            dict(url="/relative/path"),
            dict(headline=""),
            dict(body=""),
            dict(published_at=None),
            dict(published_at=datetime(2026, 10, 20, 11, 0)),  # naive
            dict(published_at="2026-10-20 11:00"),  # unparsed
        ]
        for overrides in cases:
            with self.subTest(overrides=overrides), self.assertRaises(IngestRejected):
                self.ingest(**overrides)
        with self.assertRaises(IngestRejected):
            ingest_article(None, self.item(), ingest_run_id=self.run.pk)
        with self.assertRaises(IngestRejected):
            ingest_article(self.sharesansar.pk, self.item(), ingest_run_id=None)
        with self.assertRaises(IngestRejected):
            ingest_article(999999, self.item(), ingest_run_id=self.run.pk)
        self.assertEqual(NewsArticle.objects.count(), 0)

    def test_resolve_source_ignores_case_and_spacing(self):
        fiscal = news_source_for("Fiscal Nepal")
        self.assertEqual(resolve_source("FiscalNepal"), fiscal)
        self.assertEqual(resolve_source("fiscal nepal"), fiscal)
        self.assertIsNone(resolve_source("Unknown Portal"))


class IntegrityTests(TestCase):
    def setUp(self):
        self.run = CrawlRun.objects.create(crawl_type="news")
        self.source = news_source_for("ShareSansar")

    def make(self, url, n):
        raw = RawArticle.objects.create(crawl_run=self.run, source="ShareSansar", url=url)
        return NewsArticle.objects.create(
            raw_article=raw, news_source=self.source, source="ShareSansar", url=url,
            headline=f"Headline number {n}", body="body", published_at=WHEN, content_hash=f"h{n}",
        )

    def test_unique_source_normalized_url_in_db(self):
        self.make("https://www.sharesansar.com/a", 1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make("https://sharesansar.com/a/?utm_source=x", 2)

    def test_source_url_required(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make("", 1)

    def test_source_and_run_with_articles_cannot_be_deleted(self):
        self.make("https://www.sharesansar.com/a", 1)
        with self.assertRaises(ProtectedError):
            self.source.delete()
        with self.assertRaises(ProtectedError):
            self.run.delete()

    def test_one_like_per_user(self):
        article = self.make("https://www.sharesansar.com/a", 1)
        user = get_user_model().objects.create_user(username="reader", password="x")
        ArticleLike.objects.create(article=article, user=user)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ArticleLike.objects.create(article=article, user=user)


class DedupeTests(TestCase):
    def setUp(self):
        self.run = CrawlRun.objects.create(crawl_type="news")
        self.sharesansar = news_source_for("ShareSansar")
        self.merolagani = news_source_for("MeroLagani")
        self.company = Company.objects.create(symbol="NABIL", name="Nabil Bank Limited")

    def make(self, source, url, headline, body="body", when=WHEN, provenance="crawled"):
        raw = RawArticle.objects.create(crawl_run=self.run, source=source.name, url=url)
        return NewsArticle.objects.create(
            raw_article=raw, news_source=source, source=source.name, url=url, headline=headline, body=body,
            published_at=when, content_hash=compute_content_hash(headline, body),
            canonical_hash=compute_canonical_hash(headline), data_provenance=provenance,
        )

    def test_same_source_identical_text_merged_keeping_manual_tag(self):
        keep = self.make(self.sharesansar, "https://www.sharesansar.com/a", "Nabil dividend announced today")
        lose = self.make(self.sharesansar, "https://www.sharesansar.com/b", "Nabil dividend announced today")
        ArticleCompanyTag.objects.create(article=keep, company=self.company, confidence=0.4, method="embedding")
        ArticleCompanyTag.objects.create(article=lose, company=self.company, confidence=1.0, method="manual", is_manual=True)

        report = dedupe.run(apply=False)
        self.assertEqual(report.content_groups, [[keep.pk, lose.pk]])
        self.assertEqual(NewsArticle.objects.count(), 2)  # dry run

        dedupe.run(apply=True)
        self.assertEqual(list(NewsArticle.objects.values_list("pk", flat=True)), [keep.pk])
        self.assertFalse(RawArticle.objects.filter(url="https://www.sharesansar.com/b").exists())
        tag = ArticleCompanyTag.objects.get(article=keep)
        self.assertTrue(tag.is_manual)

    def test_crawled_row_survives_over_unverified(self):
        unverified = self.make(self.sharesansar, "https://www.sharesansar.com/a", "Same text here for both",
                               provenance="unverified")
        crawled = self.make(self.sharesansar, "https://www.sharesansar.com/b", "Same text here for both")
        dedupe.run(apply=True)
        self.assertEqual(list(NewsArticle.objects.values_list("pk", flat=True)), [crawled.pk])
        self.assertNotEqual(unverified.pk, crawled.pk)

    def test_cross_source_copies_linked_not_deleted(self):
        root = self.make(self.sharesansar, "https://www.sharesansar.com/a", "NEPSE gains 12 points on Sunday")
        copy = self.make(self.merolagani, "https://merolagani.com/NewsDetail.aspx?newsID=9",
                         "NEPSE gains 12 points on Sunday", body="other text", when=WHEN + timedelta(hours=2))
        dedupe.run(apply=True)
        copy.refresh_from_db()
        self.assertEqual(copy.duplicate_of_id, root.pk)
        self.assertEqual(NewsArticle.objects.count(), 2)

    def test_recurring_same_source_headline_left_alone(self):
        self.make(self.merolagani, "https://merolagani.com/NewsDetail.aspx?newsID=1", "सुनचाँदीको मूल्य बढ्यो",
                  body="day one")
        self.make(self.merolagani, "https://merolagani.com/NewsDetail.aspx?newsID=2", "सुनचाँदीको मूल्य बढ्यो",
                  body="day two", when=WHEN + timedelta(days=1))
        report = dedupe.run(apply=True)
        self.assertEqual(NewsArticle.objects.count(), 2)
        self.assertEqual(report.links, [])
        self.assertEqual(report.same_source_title_groups, 1)

    def test_merge_when_survivor_points_at_loser_keeps_group(self):
        other = self.make(self.merolagani, "https://merolagani.com/NewsDetail.aspx?newsID=3", "Unrelated title 12345")
        loser = self.make(self.sharesansar, "https://www.sharesansar.com/a", "Identical text for merging")
        survivor = self.make(self.sharesansar, "https://www.sharesansar.com/b", "Identical text for merging")
        loser.duplicate_of = other
        loser.save(update_fields=["duplicate_of"])
        survivor.duplicate_of = loser
        survivor.save(update_fields=["duplicate_of"])

        dedupe.merge_into(survivor, loser)
        survivor.refresh_from_db()
        self.assertEqual(survivor.duplicate_of_id, other.pk)


class SourceModelTests(TestCase):
    def test_slug_unique(self):
        NewsSource.objects.create(slug="x", name="X", base_url="https://x.com")
        with self.assertRaises(IntegrityError), transaction.atomic():
            NewsSource.objects.create(slug="x", name="Y", base_url="https://y.com")


class CrawlRunCounterTests(TestCase):
    """One CrawlRun spans every spider of a crawl (crawler_runs.tasks.run_crawl)."""

    def spider(self, run, name, **counts):
        return SimpleNamespace(name=name, crawl_run_id=run.pk, logger=mock.Mock(), **counts)

    def test_counters_add_up_across_spiders_and_task_keeps_status(self):
        from crawlers.crawlers.pipelines import CrawlRunPipeline

        run = CrawlRun.objects.create(crawl_type="all", status=CrawlRun.Status.RUNNING)
        CrawlRunPipeline._complete_crawl_run(self.spider(
            run, "sharesansar", articles_seen=6, news_created=4, news_updated=1, news_duplicate=1))
        # No articles_seen: found falls back to what the pipeline processed.
        CrawlRunPipeline._complete_crawl_run(self.spider(
            run, "fiscalnepal", news_created=2, news_duplicate=3, news_rejected=1))
        CrawlRunPipeline._complete_crawl_run(self.spider(
            run, "trading_data", news_created=0, prices_found=20, prices_created=20))

        run.refresh_from_db()
        self.assertEqual(
            (run.articles_found, run.articles_created, run.articles_updated, run.articles_duplicate),
            (12, 6, 1, 4),
        )
        self.assertEqual(run.prices_created, 20)
        self.assertEqual(run.status, CrawlRun.Status.RUNNING)  # finalised by the task, not a spider

    def test_standalone_run_is_finalised_by_the_spider(self):
        from crawlers.crawlers.pipelines import CrawlRunPipeline

        spider = SimpleNamespace(name="bizmandu", source="Bizmandu", logger=mock.Mock())
        CrawlRunPipeline._create_crawl_run(spider)
        spider.news_created = 2
        CrawlRunPipeline._complete_crawl_run(spider)

        run = CrawlRun.objects.get(pk=spider.crawl_run_id)
        self.assertEqual((run.status, run.articles_created), (CrawlRun.Status.SUCCESS, 2))
        self.assertIsNotNone(run.completed_at)
