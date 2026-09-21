"""Sentiment pipeline: clean -> detect language -> score -> label -> save."""

from django.test import TestCase

from apps.crawler_runs.models import CrawlRun
from apps.news.models import NewsArticle, RawArticle
from apps.news.services.sentiment import (
    LABEL_NEGATIVE,
    LABEL_NEUTRAL,
    LABEL_POSITIVE,
    METHOD_LEXICON,
    MIN_CONTENT_CHARS,
    NEGATIVE_THRESHOLD,
    POSITIVE_THRESHOLD,
    STATUS_ERROR,
    STATUS_INSUFFICIENT_CONTENT,
    STATUS_NO_LEXICON_MATCH,
    STATUS_OK,
    STATUS_UNSUPPORTED_LANGUAGE,
    analyze_text,
    apply_sentiment,
    clean_text,
    detect_language,
    score_to_label,
)
from apps.news.tasks import (
    analyze_article_sentiment_task,
    analyze_unscored_sentiment_task,
)


class CleanTextTests(TestCase):

    def test_html_tags_stripped(self):
        self.assertEqual(clean_text("<p>Profit <b>rose</b></p>"), "Profit rose")

    def test_html_entities_decoded(self):
        self.assertEqual(clean_text("Profit &amp; growth"), "Profit & growth")

    def test_urls_removed(self):
        self.assertNotIn("http", clean_text("See https://example.com/x for more"))

    def test_whitespace_collapsed(self):
        self.assertEqual(clean_text("a\n\n  b\t c"), "a b c")

    def test_none_and_empty_safe(self):
        self.assertEqual(clean_text(None), "")
        self.assertEqual(clean_text(""), "")

    def test_raw_article_text_is_not_mutated(self):
        original = "<p>Profit rose</p>"
        clean_text(original)
        self.assertEqual(original, "<p>Profit rose</p>")


class LanguageDetectionTests(TestCase):

    def test_english_detected(self):
        self.assertEqual(detect_language("Profit rose sharply this quarter"), "en")

    def test_nepali_detected(self):
        self.assertEqual(detect_language("नाफा बढ्यो र वृद्धि भयो"), "ne")

    def test_mixed_script_uses_dominant_script(self):
        # A Nepali article quoting a Latin ticker is still Nepali.
        self.assertEqual(
            detect_language("नेपाल बैंकको नाफा बढ्यो NABIL"),
            "ne",
        )

    def test_no_letters_is_unknown(self):
        self.assertEqual(detect_language("12345 ... !!!"), "unknown")

    def test_empty_is_unknown(self):
        self.assertEqual(detect_language(""), "unknown")


class ScoringTests(TestCase):

    def test_positive_article_scores_positive(self):
        result = analyze_text(
            "Company profit surges as revenue grows strongly",
            "The bank reported record profit growth and a higher dividend "
            "for shareholders this fiscal year.",
        )

        self.assertEqual(result.status, STATUS_OK)
        self.assertEqual(result.label, LABEL_POSITIVE)
        self.assertGreater(result.score, POSITIVE_THRESHOLD)
        self.assertTrue(result.is_available)

    def test_negative_article_scores_negative(self):
        result = analyze_text(
            "Share price plunges after heavy losses reported",
            "The company posted a significant loss and warned of a "
            "weak outlook, while trading was suspended.",
        )

        self.assertEqual(result.status, STATUS_OK)
        self.assertEqual(result.label, LABEL_NEGATIVE)
        self.assertLess(result.score, NEGATIVE_THRESHOLD)

    def test_score_stays_within_documented_range(self):
        extreme = analyze_text(
            "surge soar rally profit growth boom",
            " ".join(["surge soared profit growth gains rebound"] * 40),
        )

        self.assertGreaterEqual(extreme.score, -1.0)
        self.assertLessEqual(extreme.score, 1.0)

    def test_nepali_article_is_scored(self):
        result = analyze_text(
            "बैंकको नाफा बढ्यो",
            "कम्पनीले यस वर्ष राम्रो वृद्धि र लाभांश घोषणा गरेको छ । "
            "सुधार र प्रगति भएको छ ।",
        )

        self.assertEqual(result.language, "ne")
        self.assertEqual(result.status, STATUS_OK)
        self.assertEqual(result.label, LABEL_POSITIVE)

    def test_negation_flips_polarity(self):
        positive = analyze_text(
            "Company profit did rise this quarter after strong results",
            "The results were positive for the company and its shareholders.",
        )
        negated = analyze_text(
            "Company profit did not rise this quarter despite results",
            "The results were not positive for the company or shareholders.",
        )

        self.assertLess(negated.score, positive.score)

    def test_intensifier_strengthens_score(self):
        plain = analyze_text(
            "Company profit rose during the reporting period this year",
            "Analysts noted the profit result for the reporting period.",
        )
        intense = analyze_text(
            "Company profit rose sharply during the period this year",
            "Analysts noted the profit result for the reporting period.",
        )

        self.assertGreater(intense.score, plain.score)

    def test_headline_weighted_above_body(self):
        in_headline = analyze_text(
            "Profit surges to record levels for the bank this year",
            "The filing was submitted to the regulator on the usual date.",
        )
        in_body = analyze_text(
            "Bank submits filing to regulator on the usual date this year",
            "Profit surges to record levels according to the document.",
        )

        self.assertGreater(in_headline.score, in_body.score)

    def test_deterministic(self):
        args = ("Profit surges on strong growth", "Record results reported.")
        self.assertEqual(analyze_text(*args).score, analyze_text(*args).score)


class LabelThresholdTests(TestCase):

    def test_documented_boundaries(self):
        self.assertEqual(score_to_label(POSITIVE_THRESHOLD), LABEL_POSITIVE)
        self.assertEqual(score_to_label(NEGATIVE_THRESHOLD), LABEL_NEGATIVE)
        self.assertEqual(score_to_label(0.0), LABEL_NEUTRAL)
        self.assertEqual(score_to_label(0.04), LABEL_NEUTRAL)
        self.assertEqual(score_to_label(-0.04), LABEL_NEUTRAL)

    def test_none_score_has_no_label(self):
        self.assertEqual(score_to_label(None), "")


class MissingContentTests(TestCase):

    def test_empty_article_reports_insufficient_content(self):
        result = analyze_text("", "")

        self.assertEqual(result.status, STATUS_INSUFFICIENT_CONTENT)
        self.assertIsNone(result.score)
        self.assertFalse(result.is_available)

    def test_short_article_reports_insufficient_content(self):
        result = analyze_text("Profit up", "")

        self.assertEqual(result.status, STATUS_INSUFFICIENT_CONTENT)
        self.assertIsNone(result.score)

    def test_none_inputs_do_not_crash(self):
        result = analyze_text(None, None)
        self.assertEqual(result.status, STATUS_INSUFFICIENT_CONTENT)

    def test_minimum_length_is_documented_and_enforced(self):
        just_under = "x" * (MIN_CONTENT_CHARS - 2)
        self.assertEqual(
            analyze_text(just_under, "").status,
            STATUS_INSUFFICIENT_CONTENT,
        )


class UnsupportedLanguageTests(TestCase):

    def test_unsupported_script_is_reported_not_scored(self):
        # Long enough to pass the length gate, but no Latin/Devanagari.
        result = analyze_text("这是一篇关于股票市场的长篇新闻报道文章内容需要足够长才能通过最小长度检查测试以便验证不支持的语言处理逻辑", "")

        self.assertEqual(result.status, STATUS_UNSUPPORTED_LANGUAGE)
        self.assertIsNone(result.score)
        self.assertFalse(result.is_available)

    def test_supported_languages_listed_in_details(self):
        result = analyze_text("这是一篇关于股票市场的长篇新闻报道文章内容需要足够长才能通过最小长度检查测试以便验证不支持的语言处理逻辑", "")
        self.assertIn("supported_languages", result.details)

    def test_supported_language_with_no_lexicon_hits(self):
        result = analyze_text(
            "The committee met on Tuesday to discuss the agenda items",
            "Attendance was recorded and the minutes were circulated later.",
        )

        self.assertEqual(result.status, STATUS_NO_LEXICON_MATCH)
        self.assertEqual(result.label, LABEL_NEUTRAL)
        self.assertEqual(result.score, 0.0)
        # Still "available": a genuine neutral reading, not a failure.
        self.assertTrue(result.is_available)


class FailureHandlingTests(TestCase):

    def test_analyser_failure_is_captured_not_raised(self):
        from unittest.mock import patch

        with patch(
            "apps.news.services.sentiment.detect_language",
            side_effect=RuntimeError("model exploded"),
        ):
            result = analyze_text("Profit surges on strong growth this year", "body text here")

        self.assertEqual(result.status, STATUS_ERROR)
        self.assertIsNone(result.score)
        self.assertIn("model exploded", result.error)
        self.assertFalse(result.is_available)

    def test_one_failure_does_not_abort_the_batch(self):
        from unittest.mock import patch

        run = CrawlRun.objects.create(crawl_type="news", source="test")
        articles = []
        for index in range(3):
            raw = RawArticle.objects.create(
                crawl_run=run, source="test", url=f"https://x/{index}",
            )
            articles.append(NewsArticle.objects.create(
                raw_article=raw,
                source="test",
                url=f"https://x/{index}",
                headline="Profit surges on strong growth and record results",
                body="The company reported higher profit and strong growth.",
                content_hash=f"hash{index}",
            ))

        original = analyze_text
        calls = {"n": 0}

        def flaky(headline, body=""):
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("transient NLP failure")
            return original(headline, body)

        with patch("apps.news.services.sentiment.analyze_text", side_effect=flaky):
            outcome = analyze_unscored_sentiment_task()

        # All three attempted; the failure is isolated and counted.
        self.assertEqual(outcome["attempted"], 3)
        self.assertEqual(outcome["failed"], 1)
        self.assertEqual(outcome["succeeded"], 2)


class PersistenceTests(TestCase):

    def setUp(self):
        run = CrawlRun.objects.create(crawl_type="news", source="test")
        raw = RawArticle.objects.create(
            crawl_run=run, source="test", url="https://example.com/a",
        )
        self.article = NewsArticle.objects.create(
            raw_article=raw,
            source="test",
            url="https://example.com/a",
            headline="Bank profit surges on strong growth",
            body="The bank reported record profit and a higher dividend.",
            content_hash="abc123",
        )

    def test_default_status_is_pending(self):
        self.assertEqual(self.article.sentiment_status, "pending")
        self.assertIsNone(self.article.sentiment)

    def test_apply_sentiment_persists_all_fields(self):
        apply_sentiment(self.article)
        self.article.refresh_from_db()

        self.assertEqual(self.article.sentiment_status, STATUS_OK)
        self.assertEqual(self.article.sentiment_label, LABEL_POSITIVE)
        self.assertIsNotNone(self.article.sentiment)
        self.assertEqual(self.article.sentiment_method, METHOD_LEXICON)
        self.assertEqual(self.article.sentiment_language, "en")
        self.assertIsNotNone(self.article.sentiment_processed_at)

    def test_raw_crawled_text_is_preserved(self):
        headline_before = self.article.headline
        body_before = self.article.body

        apply_sentiment(self.article)
        self.article.refresh_from_db()

        self.assertEqual(self.article.headline, headline_before)
        self.assertEqual(self.article.body, body_before)

    def test_processing_is_idempotent(self):
        apply_sentiment(self.article)
        self.article.refresh_from_db()
        first_score = self.article.sentiment
        first_label = self.article.sentiment_label

        apply_sentiment(self.article)
        self.article.refresh_from_db()

        self.assertEqual(self.article.sentiment, first_score)
        self.assertEqual(self.article.sentiment_label, first_label)
        self.assertEqual(NewsArticle.objects.count(), 1)

    def test_task_scores_the_article(self):
        outcome = analyze_article_sentiment_task(self.article.id)
        self.article.refresh_from_db()

        self.assertTrue(outcome["success"])
        self.assertEqual(self.article.sentiment_status, STATUS_OK)

    def test_task_handles_missing_article(self):
        outcome = analyze_article_sentiment_task(999999)
        self.assertFalse(outcome["success"])

    def test_batch_task_only_picks_up_pending(self):
        apply_sentiment(self.article)

        outcome = analyze_unscored_sentiment_task()
        self.assertEqual(outcome["attempted"], 0)

    def test_unavailable_is_distinguishable_from_calculated(self):
        # Short article -> unavailable, with a status explaining why.
        run = CrawlRun.objects.create(crawl_type="news", source="test")
        raw = RawArticle.objects.create(
            crawl_run=run, source="test", url="https://example.com/short",
        )
        short = NewsArticle.objects.create(
            raw_article=raw,
            source="test",
            url="https://example.com/short",
            headline="Up",
            body="",
            content_hash="short1",
        )

        apply_sentiment(short)
        apply_sentiment(self.article)
        short.refresh_from_db()
        self.article.refresh_from_db()

        self.assertIsNone(short.sentiment)
        self.assertEqual(short.sentiment_status, STATUS_INSUFFICIENT_CONTENT)

        self.assertIsNotNone(self.article.sentiment)
        self.assertEqual(self.article.sentiment_status, STATUS_OK)

        # The two are distinguishable on status alone.
        self.assertNotEqual(short.sentiment_status, self.article.sentiment_status)
