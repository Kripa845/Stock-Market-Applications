"""
Categorization: evidence tiers, multi-label behaviour, and the
persistence of manual corrections across automatic reruns.

The embedding model is patched out throughout. Loading
sentence-transformers would download weights and make these tests depend
on the network and on a model's opinions; the decision logic under test
is deterministic given a similarity number, so the similarity is injected.
"""

from unittest.mock import patch

import numpy as np
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.companies.models import Company
from apps.crawler_runs.models import CrawlRun
from apps.news.models import (
    ArticleCompanyTag,
    CategorizationCorrection,
    NewsArticle,
    RawArticle,
)
from apps.news.services.categorization import (
    MATCH_ALIAS,
    MATCH_BODY_MENTION,
    MATCH_COMPANY_NAME,
    MATCH_SEMANTIC_ONLY,
    MATCH_SYMBOL,
    calculate_lexical_score,
    categorize_article,
    classify_evidence,
    decide_company_match,
    invalidate_company_cache,
)
from apps.news.services.corrections import (
    apply_add,
    apply_remove,
    apply_update,
)


class NewsFixtureMixin:

    def make_article(self, headline, body="", url=None):
        run = CrawlRun.objects.create(crawl_type="news", source="test")
        url = url or f"https://example.com/{abs(hash(headline)) % 10**8}"
        raw = RawArticle.objects.create(crawl_run=run, source="test", url=url)
        return NewsArticle.objects.create(
            raw_article=raw,
            source="test",
            url=url,
            headline=headline,
            body=body,
            content_hash=str(abs(hash(headline)) % 10**8),
        )


class EvidenceClassificationTests(NewsFixtureMixin, TestCase):

    def setUp(self):
        self.nabil = Company.objects.create(
            symbol="NABIL", name="Nabil Bank Limited", sector="Banking",
            aliases=["Nabil Bank", "Nabil"],
        )

    def test_exact_symbol_in_headline(self):
        article = self.make_article("NABIL announces dividend", "Body text.")
        score, evidence = calculate_lexical_score(article, self.nabil)
        match_type, in_headline = classify_evidence(evidence)

        self.assertEqual(match_type, MATCH_SYMBOL)
        self.assertTrue(in_headline)

    def test_exact_company_name(self):
        article = self.make_article("Nabil Bank Limited posts profit", "Body.")
        _, evidence = calculate_lexical_score(article, self.nabil)
        match_type, _ = classify_evidence(evidence)

        self.assertIn(match_type, {MATCH_SYMBOL, MATCH_COMPANY_NAME})

    def test_alias_match(self):
        # A company whose symbol is NOT a substring of its aliases, so the
        # alias tier can be observed in isolation. (For NABIL the symbol
        # "nabil" equals the alias word "Nabil" once casefolded, so a
        # symbol match correctly wins there.)
        himalayan = Company.objects.create(
            symbol="HBL", name="Himalayan Bank Limited", sector="Banking",
            aliases=["Himalayan Bank"],
        )
        article = self.make_article("Himalayan Bank opens new branch", "Body.")
        _, evidence = calculate_lexical_score(article, himalayan)
        match_type, in_headline = classify_evidence(evidence)

        self.assertIn(match_type, {MATCH_ALIAS, MATCH_COMPANY_NAME})
        self.assertTrue(in_headline)

    def test_body_only_mention_is_weaker_than_headline(self):
        article = self.make_article(
            "Banking sector review published",
            "Among the banks surveyed, Nabil Bank reported steady results.",
        )
        _, evidence = calculate_lexical_score(article, self.nabil)
        match_type, in_headline = classify_evidence(evidence)

        self.assertFalse(in_headline)
        self.assertIn(match_type, {MATCH_BODY_MENTION, MATCH_SYMBOL, MATCH_COMPANY_NAME})

    def test_unrelated_company_has_no_lexical_match(self):
        other = Company.objects.create(
            symbol="NICA", name="NIC Asia Bank", sector="Banking", aliases=[],
        )
        article = self.make_article("NABIL announces dividend", "Nabil Bank news.")
        score, evidence = calculate_lexical_score(article, other)
        match_type, _ = classify_evidence(evidence)

        self.assertEqual(score, 0.0)
        self.assertIsNone(match_type)

    def test_substring_does_not_falsely_match(self):
        # 'NICA' must not match inside 'Nicaragua'.
        other = Company.objects.create(
            symbol="NICA", name="NIC Asia Bank", sector="Banking", aliases=[],
        )
        article = self.make_article("Trade delegation visits Nicaragua", "Body.")
        score, _ = calculate_lexical_score(article, other)

        self.assertEqual(score, 0.0)


class DecisionTierTests(TestCase):
    """The arithmetic fix: strong lexical evidence must not be diluted."""

    def _evidence(self, term_type, headline_count=1, body_count=0):
        return {
            "matched_terms": [{
                "term": "x", "type": term_type,
                "headline_count": headline_count, "body_count": body_count,
            }]
        }

    def test_headline_symbol_accepted_despite_weak_semantics(self):
        # Under the old formula: 0.6*0.10 + 0.4*0.95 = 0.44 < 0.65 -> REJECTED.
        # An article whose headline names the ticker must not be rejected
        # because its prose does not resemble the company profile.
        decision = decide_company_match(
            lexical_score=0.95,
            lexical_evidence=self._evidence("symbol"),
            semantic_similarity=0.10,
            hybrid_score=0.44,
        )

        self.assertTrue(decision["accept"])
        self.assertEqual(decision["match_type"], MATCH_SYMBOL)
        self.assertGreaterEqual(decision["confidence"], 0.95)

    def test_company_name_accepted(self):
        decision = decide_company_match(
            lexical_score=0.95,
            lexical_evidence=self._evidence("canonical_name"),
            semantic_similarity=0.20,
            hybrid_score=0.50,
        )
        self.assertTrue(decision["accept"])
        self.assertEqual(decision["match_type"], MATCH_COMPANY_NAME)

    def test_alias_accepted(self):
        decision = decide_company_match(
            lexical_score=0.85,
            lexical_evidence=self._evidence("alias"),
            semantic_similarity=0.20,
            hybrid_score=0.46,
        )
        self.assertTrue(decision["accept"])
        self.assertEqual(decision["match_type"], MATCH_ALIAS)

    def test_body_only_gets_lower_confidence_than_headline(self):
        headline = decide_company_match(
            lexical_score=0.85,
            lexical_evidence=self._evidence("alias", headline_count=1, body_count=0),
            semantic_similarity=0.2, hybrid_score=0.46,
        )
        body = decide_company_match(
            lexical_score=0.75,
            lexical_evidence=self._evidence("alias", headline_count=0, body_count=1),
            semantic_similarity=0.2, hybrid_score=0.42,
        )

        self.assertEqual(body["match_type"], MATCH_BODY_MENTION)
        self.assertLess(body["confidence"], headline["confidence"])

    def test_semantic_only_strong_match_accepted(self):
        decision = decide_company_match(
            lexical_score=0.0,
            lexical_evidence={"matched_terms": []},
            semantic_similarity=0.82,
            hybrid_score=0.49,
        )

        self.assertTrue(decision["accept"])
        self.assertEqual(decision["match_type"], MATCH_SEMANTIC_ONLY)
        self.assertEqual(decision["decision_basis"], "semantic_only")

    def test_semantic_only_weak_match_goes_to_review_not_tagged(self):
        decision = decide_company_match(
            lexical_score=0.0,
            lexical_evidence={"matched_terms": []},
            semantic_similarity=0.65,
            hybrid_score=0.39,
        )

        self.assertFalse(decision["accept"])
        self.assertTrue(decision["needs_review"])

    def test_semantic_only_below_floor_rejected_outright(self):
        decision = decide_company_match(
            lexical_score=0.0,
            lexical_evidence={"matched_terms": []},
            semantic_similarity=0.30,
            hybrid_score=0.18,
        )

        self.assertFalse(decision["accept"])
        self.assertFalse(decision["needs_review"])

    def test_semantic_only_bar_is_higher_than_lexical_bar(self):
        # A generic market article resembling every company at 0.70 must
        # not be tagged to all of them.
        generic = decide_company_match(
            lexical_score=0.0,
            lexical_evidence={"matched_terms": []},
            semantic_similarity=0.70,
            hybrid_score=0.42,
        )
        self.assertFalse(generic["accept"])


class PatchedCategorizationMixin(NewsFixtureMixin):
    """Runs categorize_article with a stubbed embedding layer."""

    SIMILARITY = 0.10

    def categorize(self, article, similarity=None):
        # The company profile cache is a process-level global that never
        # expires, so without this a previous test's companies (from a
        # rolled-back transaction) leak into this one. See the production
        # note on invalidate_company_cache.
        invalidate_company_cache()
        sim = self.SIMILARITY if similarity is None else similarity
        with patch(
            "apps.news.services.categorization.encode_text",
            return_value=np.zeros(8, dtype="float32"),
        ), patch(
            "apps.news.services.categorization.calculate_cosine_similarity",
            return_value=sim,
        ):
            return categorize_article(article)


class MultiLabelTests(PatchedCategorizationMixin, TestCase):

    def setUp(self):
        self.nabil = Company.objects.create(
            symbol="NABIL", name="Nabil Bank Limited", sector="Banking",
            aliases=["Nabil Bank"],
        )
        self.nica = Company.objects.create(
            symbol="NICA", name="NIC Asia Bank", sector="Banking",
            aliases=["NIC Asia"],
        )
        self.hbl = Company.objects.create(
            symbol="HBL", name="Himalayan Bank Limited", sector="Banking",
            aliases=["Himalayan Bank"],
        )

    def test_article_can_carry_multiple_company_tags(self):
        article = self.make_article(
            "NABIL and NICA both announce dividends",
            "Both banks reported results today.",
        )
        self.categorize(article)

        symbols = set(
            ArticleCompanyTag.objects
            .filter(article=article)
            .values_list("company__symbol", flat=True)
        )
        self.assertEqual(symbols, {"NABIL", "NICA"})

    def test_evaluation_does_not_stop_at_first_match(self):
        article = self.make_article(
            "NABIL, NICA and HBL report quarterly earnings",
            "All three banks published results.",
        )
        self.categorize(article)

        self.assertEqual(
            ArticleCompanyTag.objects.filter(article=article).count(), 3,
        )

    def test_unrelated_company_not_tagged(self):
        article = self.make_article("NABIL announces dividend", "Nabil news.")
        self.categorize(article)

        self.assertFalse(
            ArticleCompanyTag.objects
            .filter(article=article, company=self.hbl)
            .exists()
        )

    def test_generic_market_article_not_tagged_to_everyone(self):
        article = self.make_article(
            "Market closes higher on broad buying",
            "The index gained across sectors today.",
        )
        self.categorize(article, similarity=0.70)  # weak semantic-only

        self.assertEqual(
            ArticleCompanyTag.objects.filter(article=article).count(), 0,
        )

    def test_match_type_is_recorded_on_the_tag(self):
        article = self.make_article("NABIL announces dividend", "Nabil news today.")
        self.categorize(article)

        tag = ArticleCompanyTag.objects.get(article=article, company=self.nabil)
        self.assertEqual(tag.method, MATCH_SYMBOL)
        self.assertEqual(tag.evidence["match_type"], MATCH_SYMBOL)
        self.assertIn("score_interpretation", tag.evidence)

    def test_repeated_runs_are_idempotent(self):
        article = self.make_article("NABIL announces dividend", "Nabil news.")
        self.categorize(article)
        self.categorize(article)
        self.categorize(article)

        self.assertEqual(
            ArticleCompanyTag.objects.filter(article=article).count(), 1,
        )


class ManualCorrectionTests(PatchedCategorizationMixin, TestCase):
    """
    The core regression: a human correction must survive automatic reruns.
    """

    def setUp(self):
        self.nabil = Company.objects.create(
            symbol="NABIL", name="Nabil Bank Limited", sector="Banking",
            aliases=["Nabil Bank"],
        )
        self.nica = Company.objects.create(
            symbol="NICA", name="NIC Asia Bank", sector="Banking",
            aliases=["NIC Asia"],
        )
        self.user = get_user_model().objects.create_user(
            username="analyst", password="x",
        )
        self.article = self.make_article(
            "NABIL announces dividend",
            "Nabil Bank declared a dividend today.",
        )

    def test_automatic_add_creates_tag(self):
        self.categorize(self.article)

        tag = ArticleCompanyTag.objects.get(
            article=self.article, company=self.nabil,
        )
        self.assertFalse(tag.is_manual)

    def test_manual_remove_deletes_tag_and_records_correction(self):
        self.categorize(self.article)
        apply_remove(self.article, self.nabil, user=self.user, reason="wrong")

        self.assertFalse(
            ArticleCompanyTag.objects
            .filter(article=self.article, company=self.nabil)
            .exists()
        )
        self.assertTrue(
            CategorizationCorrection.objects
            .filter(article=self.article, company=self.nabil, action="remove")
            .exists()
        )

    def test_rerun_after_remove_does_not_recreate_the_tag(self):
        # THE REGRESSION. Before the fix, this rerun brought the tag back
        # because the deleted row could no longer carry is_manual=True.
        self.categorize(self.article)
        apply_remove(self.article, self.nabil, user=self.user)

        self.categorize(self.article)

        self.assertFalse(
            ArticleCompanyTag.objects
            .filter(article=self.article, company=self.nabil)
            .exists(),
            "manually removed tag was recreated by automatic categorization",
        )

    def test_removal_survives_many_reruns(self):
        self.categorize(self.article)
        apply_remove(self.article, self.nabil, user=self.user)

        for _ in range(5):
            self.categorize(self.article)

        self.assertFalse(
            ArticleCompanyTag.objects
            .filter(article=self.article, company=self.nabil)
            .exists()
        )

    def test_manual_add_persists(self):
        tag, _ = apply_add(self.article, self.nica, confidence=1.0, user=self.user)

        self.assertTrue(tag.is_manual)
        self.assertEqual(tag.method, "manual")

    def test_rerun_after_manual_add_keeps_the_tag(self):
        # The model does not predict NICA for this article at all.
        apply_add(self.article, self.nica, confidence=1.0, user=self.user)

        self.categorize(self.article)

        tag = ArticleCompanyTag.objects.get(
            article=self.article, company=self.nica,
        )
        self.assertTrue(tag.is_manual)
        self.assertEqual(tag.confidence, 1.0)

    def test_manual_update_persists_and_is_not_overwritten(self):
        self.categorize(self.article)
        apply_update(self.article, self.nabil, confidence=0.42, user=self.user)

        self.categorize(self.article)

        tag = ArticleCompanyTag.objects.get(
            article=self.article, company=self.nabil,
        )
        self.assertEqual(tag.confidence, 0.42)
        self.assertTrue(tag.is_manual)

    def test_update_records_previous_values_for_audit(self):
        self.categorize(self.article)
        original = ArticleCompanyTag.objects.get(
            article=self.article, company=self.nabil,
        ).confidence

        apply_update(self.article, self.nabil, confidence=0.42, user=self.user)

        correction = CategorizationCorrection.objects.get(
            article=self.article, company=self.nabil, action="update",
        )
        self.assertEqual(correction.previous_confidence, original)
        self.assertEqual(correction.corrected_by, self.user)

    def test_latest_correction_wins(self):
        # Remove, then change your mind and re-add.
        self.categorize(self.article)
        apply_remove(self.article, self.nabil, user=self.user)
        apply_add(self.article, self.nabil, confidence=0.9, user=self.user)

        self.categorize(self.article)

        tag = ArticleCompanyTag.objects.get(
            article=self.article, company=self.nabil,
        )
        self.assertEqual(tag.confidence, 0.9)
        self.assertTrue(tag.is_manual)

    def test_automatic_predictions_for_other_companies_are_preserved(self):
        article = self.make_article(
            "NABIL and NICA announce dividends",
            "Both banks reported today.",
        )
        self.categorize(article)
        apply_remove(article, self.nabil, user=self.user)
        self.categorize(article)

        # NABIL suppressed, NICA still automatically tagged.
        self.assertFalse(
            ArticleCompanyTag.objects
            .filter(article=article, company=self.nabil).exists()
        )
        self.assertTrue(
            ArticleCompanyTag.objects
            .filter(article=article, company=self.nica).exists()
        )

    def test_remove_is_idempotent(self):
        self.categorize(self.article)
        apply_remove(self.article, self.nabil, user=self.user)
        apply_remove(self.article, self.nabil, user=self.user)

        self.assertFalse(
            ArticleCompanyTag.objects
            .filter(article=self.article, company=self.nabil).exists()
        )

    def test_update_on_missing_tag_raises(self):
        with self.assertRaises(ArticleCompanyTag.DoesNotExist):
            apply_update(self.article, self.nica, confidence=0.5, user=self.user)

    def test_invalid_confidence_rejected(self):
        for bad in (-0.1, 1.5, "abc", None):
            with self.assertRaises((ValueError, TypeError)):
                apply_add(self.article, self.nica, confidence=bad, user=self.user)
