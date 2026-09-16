"""
Comprehensive Automated Test Suite for News Auto-Categorization.

Covers:
1. Exact company name matching
2. Alias matching
3. Case-insensitive matching
4. Semantic similarity calculation (Cosine similarity)
5. Hybrid scoring formula
6. Threshold behavior
7. Multi-label article handling (multiple companies tagged)
8. No-match article handling (no false positive tags)
9. Confidence score persistence
10. Duplicate tag prevention (unique constraint)
11. Manual correction precedence over auto-categorization
12. Audit record creation in CategorizationCorrection
13. Analyst-only recategorization
14. Viewer cannot recategorize (403 Forbidden)
15. Admin permissions verification
16. Celery task execution safety
17. Idempotency when running categorization multiple times
"""

import hashlib
import numpy as np
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.companies.models import Company, TrackedCompany
from apps.crawler_runs.models import CrawlRun
from apps.news.models import (
    ArticleCompanyTag,
    CategorizationCorrection,
    NewsArticle,
    RawArticle,
)
from apps.news.services.categorization import (
    build_article_text,
    build_company_profile,
    calculate_cosine_similarity,
    calculate_hybrid_score,
    calculate_lexical_score,
    categorize_article,
    encode_text,
    get_company_profiles_cache,
    invalidate_company_cache,
    normalize_text,
)
from apps.news.tasks import categorize_article_task

User = get_user_model()


class NewsCategorizationTests(TestCase):
    def setUp(self):
        invalidate_company_cache()

        # Create test users for RBAC
        self.admin_user = User.objects.create_user(
            username="admin_test",
            email="admin@test.com",
            password="Password123!",
            role="admin",
        )
        self.analyst_user = User.objects.create_user(
            username="analyst_test",
            email="analyst@test.com",
            password="Password123!",
            role="analyst",
        )
        self.viewer_user = User.objects.create_user(
            username="viewer_test",
            email="viewer@test.com",
            password="Password123!",
            role="viewer",
        )

        # Create standard watchlist companies
        self.nabil = Company.objects.create(
            symbol="NABIL",
            name="Nabil Bank Limited",
            sector="Commercial Bank",
            aliases=["Nabil Bank", "Nabil Bank Ltd", "Nabil"],
            is_active=True,
        )
        TrackedCompany.objects.create(company=self.nabil, is_tracked=True)

        self.nica = Company.objects.create(
            symbol="NICA",
            name="NIC Asia Bank Limited",
            sector="Commercial Bank",
            aliases=["NIC Asia Bank", "NIC Asia Bank Ltd", "NIC Asia", "NICA"],
            is_active=True,
        )
        TrackedCompany.objects.create(company=self.nica, is_tracked=True)

        self.nlic = Company.objects.create(
            symbol="NLIC",
            name="Nepal Life Insurance Company Limited",
            sector="Life Insurance",
            aliases=["Nepal Life Insurance", "Nepal Life", "NLIC"],
            is_active=True,
        )
        TrackedCompany.objects.create(company=self.nlic, is_tracked=True)

        self.shivm = Company.objects.create(
            symbol="SHIVM",
            name="Shivam Cements Limited",
            sector="Manufacturing",
            aliases=["Shivam Cement", "Shivam Cements", "Shivam", "SHIVM"],
            is_active=True,
        )
        TrackedCompany.objects.create(company=self.shivm, is_tracked=True)

        # Create CrawlRun & RawArticle for FK relations
        self.crawl_run = CrawlRun.objects.create(
            status=CrawlRun.Status.SUCCESS,
            started_at=timezone.now(),
            sources=["sharesansar"],
        )

    def _create_article(self, headline: str, body: str, url: str) -> NewsArticle:
        raw = RawArticle.objects.create(
            crawl_run=self.crawl_run,
            source="sharesansar",
            url=url,
            http_status=200,
        )
        content_hash = hashlib.sha256(f"{headline}|{body}".encode("utf-8")).hexdigest()
        return NewsArticle.objects.create(
            raw_article=raw,
            source="sharesansar",
            url=url,
            headline=headline,
            body=body,
            published_at=timezone.now(),
            content_hash=content_hash,
        )

    # -----------------------------------------------------------------------
    # 1. Exact Company Name Matching
    # -----------------------------------------------------------------------
    def test_exact_company_name_matching(self):
        article = self._create_article(
            headline="Nabil Bank Limited announces 35% profit surge",
            body="Nabil Bank Limited reported outstanding first-quarter performance.",
            url="https://example.com/news/1",
        )
        score, evidence = calculate_lexical_score(article, self.nabil)
        self.assertGreaterEqual(score, 0.90)
        self.assertIn("Nabil Bank Limited", [t["term"] for t in evidence["matched_terms"]])

    # -----------------------------------------------------------------------
    # 2. Alias Matching
    # -----------------------------------------------------------------------
    def test_alias_matching(self):
        article = self._create_article(
            headline="Nabil reports higher deposits in Q1",
            body="Deposits increased substantially according to the latest disclosures.",
            url="https://example.com/news/2",
        )
        score, evidence = calculate_lexical_score(article, self.nabil)
        self.assertGreaterEqual(score, 0.80)
        matched_aliases = [t["term"] for t in evidence["matched_terms"] if t["type"] == "alias"]
        self.assertIn("Nabil", matched_aliases)

    # -----------------------------------------------------------------------
    # 3. Case-Insensitive Matching
    # -----------------------------------------------------------------------
    def test_case_insensitive_matching(self):
        article = self._create_article(
            headline="nabil bank and nica bank lead banking gains",
            body="trading volume for nabil was the highest of the session.",
            url="https://example.com/news/3",
        )
        score_nabil, _ = calculate_lexical_score(article, self.nabil)
        score_nica, _ = calculate_lexical_score(article, self.nica)
        self.assertGreater(score_nabil, 0.70)
        self.assertGreater(score_nica, 0.70)

    # -----------------------------------------------------------------------
    # 4. Semantic Similarity Calculation (Real Cosine Similarity)
    # -----------------------------------------------------------------------
    def test_semantic_cosine_similarity(self):
        # Orthogonal vectors should have 0 similarity
        v1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        v2 = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        self.assertEqual(calculate_cosine_similarity(v1, v2), 0.0)

        # Identical vectors should have 1.0 similarity
        v3 = np.array([0.5, 0.5, 0.5], dtype=np.float32)
        self.assertAlmostEqual(calculate_cosine_similarity(v3, v3), 1.0, places=4)

        # Realistic embedding encode test
        emb_bank = encode_text("Nabil Bank Limited commercial banking sector quarterly earnings profit")
        profile_emb = encode_text(build_company_profile(self.nabil))
        sim = calculate_cosine_similarity(emb_bank, profile_emb)
        self.assertGreater(sim, 0.50)

    # -----------------------------------------------------------------------
    # 5. Hybrid Scoring Formula
    # -----------------------------------------------------------------------
    def test_hybrid_scoring_formula(self):
        # semantic 0.90 (weight 0.6) + lexical 1.0 (weight 0.4) = 0.54 + 0.40 = 0.94
        score = calculate_hybrid_score(
            semantic_similarity=0.90,
            lexical_score=1.0,
            embedding_weight=0.60,
            keyword_weight=0.40,
        )
        self.assertAlmostEqual(score, 0.94, places=2)

    # -----------------------------------------------------------------------
    # 6. Threshold Behavior
    # -----------------------------------------------------------------------
    def test_threshold_behavior(self):
        article = self._create_article(
            headline="Cement production updates from eastern region",
            body="General industry report without mentioning Shivam specifically.",
            url="https://example.com/news/threshold",
        )
        # Using a strict threshold of 0.85 should exclude low-confidence matches
        tags = categorize_article(article, threshold=0.85)
        for tag in tags:
            self.assertGreaterEqual(tag.confidence, 0.85)

    # -----------------------------------------------------------------------
    # 7. Multi-Label Article (NABIL and NICA both tagged independently)
    # -----------------------------------------------------------------------
    def test_multi_label_article(self):
        article = self._create_article(
            headline="Nabil Bank and NIC Asia report higher quarterly earnings",
            body="Both Nabil Bank Limited and NIC Asia Bank Limited posted solid growth in net profit this quarter.",
            url="https://example.com/news/multi-label",
        )
        tags = categorize_article(article, threshold=0.65)
        tagged_symbols = [t.company.symbol for t in tags]

        self.assertIn("NABIL", tagged_symbols)
        self.assertIn("NICA", tagged_symbols)
        self.assertNotIn("NLIC", tagged_symbols)
        self.assertNotIn("SHIVM", tagged_symbols)

        # Every tag must have its own confidence score
        for tag in tags:
            self.assertGreaterEqual(tag.confidence, 0.65)
            self.assertEqual(tag.method, "hybrid")

    # -----------------------------------------------------------------------
    # 8. No-Match Article (No false company tags)
    # -----------------------------------------------------------------------
    def test_no_match_article(self):
        article = self._create_article(
            headline="Global investors discuss international macroeconomic outlook in Geneva",
            body="Central banks around the world evaluate monetary policies and global inflation trends.",
            url="https://example.com/news/no-match",
        )
        tags = categorize_article(article, threshold=0.65)
        self.assertEqual(len(tags), 0)
        article.refresh_from_db()
        self.assertTrue(article.is_processed)

    # -----------------------------------------------------------------------
    # 9. Confidence Score Persistence in ArticleCompanyTag
    # -----------------------------------------------------------------------
    def test_confidence_score_persistence(self):
        article = self._create_article(
            headline="Nabil Bank announces branch expansion",
            body="Nabil Bank Limited opens five new branches across Pokhara.",
            url="https://example.com/news/persistence",
        )
        categorize_article(article, threshold=0.60)
        saved_tag = ArticleCompanyTag.objects.filter(article=article, company=self.nabil).first()

        self.assertIsNotNone(saved_tag)
        self.assertGreater(saved_tag.confidence, 0.60)
        self.assertEqual(saved_tag.method, "hybrid")
        self.assertIn("lexical_score", saved_tag.evidence)
        self.assertIn("semantic_similarity", saved_tag.evidence)

    # -----------------------------------------------------------------------
    # 10. Duplicate Tag Prevention (Unique Constraint)
    # -----------------------------------------------------------------------
    def test_duplicate_tag_prevention(self):
        article = self._create_article(
            headline="Nabil Bank reports dividend distribution",
            body="Nabil Bank Limited proposed 15% cash dividend.",
            url="https://example.com/news/dup-test",
        )
        categorize_article(article)
        categorize_article(article)

        # Count tags for this article and company
        count = ArticleCompanyTag.objects.filter(article=article, company=self.nabil).count()
        self.assertEqual(count, 1)

    # -----------------------------------------------------------------------
    # 11. Manual Correction Precedence Over Auto-Categorization
    # -----------------------------------------------------------------------
    def test_manual_correction_precedence(self):
        article = self._create_article(
            headline="Banking sector general news",
            body="General analysis of commercial banks.",
            url="https://example.com/news/manual-precedence",
        )

        # Analyst manually tags NLIC with confidence 1.0
        manual_tag = ArticleCompanyTag.objects.create(
            article=article,
            company=self.nlic,
            confidence=1.0,
            method="manual",
            is_manual=True,
            evidence={"manual_reason": "Analyst verified relevant life insurance impact"},
        )

        # Run auto-categorization (which would not naturally score NLIC high on this article)
        categorize_article(article, threshold=0.65)

        # Verify manual tag was NOT deleted or overwritten
        refreshed_tag = ArticleCompanyTag.objects.get(article=article, company=self.nlic)
        self.assertTrue(refreshed_tag.is_manual)
        self.assertEqual(refreshed_tag.confidence, 1.0)
        self.assertEqual(refreshed_tag.method, "manual")

    # -----------------------------------------------------------------------
    # 12. Audit Record Creation in CategorizationCorrection
    # -----------------------------------------------------------------------
    def test_audit_record_creation(self):
        article = self._create_article(
            headline="Nabil Bank Q3 results",
            body="Nabil Bank Limited results published.",
            url="https://example.com/news/audit-test",
        )

        client = APIClient()
        client.force_authenticate(user=self.analyst_user)

        response = client.post(
            f"/api/news/{article.id}/recategorize/",
            {
                "company_id": self.nabil.id,
                "action": "add",
                "confidence": 0.98,
                "reason": "Explicit company mention verified by senior analyst",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check audit log
        correction = CategorizationCorrection.objects.filter(article=article, company=self.nabil).first()
        self.assertIsNotNone(correction)
        self.assertEqual(correction.action, "add")
        self.assertEqual(correction.reason, "Explicit company mention verified by senior analyst")
        self.assertEqual(correction.corrected_by, self.analyst_user)

    # -----------------------------------------------------------------------
    # 13. Analyst-Only Recategorization
    # -----------------------------------------------------------------------
    def test_analyst_can_recategorize(self):
        article = self._create_article(
            headline="Shivam Cements production increase",
            body="Shivam Cements factory expansion completed.",
            url="https://example.com/news/analyst-perm",
        )
        client = APIClient()
        client.force_authenticate(user=self.analyst_user)

        response = client.post(
            f"/api/news/{article.id}/recategorize/",
            {
                "company_id": self.shivm.id,
                "action": "add",
                "confidence": 0.99,
                "reason": "Analyst manual tag",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # -----------------------------------------------------------------------
    # 14. Viewer Cannot Recategorize (403 Forbidden)
    # -----------------------------------------------------------------------
    def test_viewer_cannot_recategorize(self):
        article = self._create_article(
            headline="Shivam Cements quarterly news",
            body="Shivam Cements quarterly announcement.",
            url="https://example.com/news/viewer-perm",
        )
        client = APIClient()
        client.force_authenticate(user=self.viewer_user)

        response = client.post(
            f"/api/news/{article.id}/recategorize/",
            {
                "company_id": self.shivm.id,
                "action": "add",
                "confidence": 0.99,
                "reason": "Unauthorized viewer attempt",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # -----------------------------------------------------------------------
    # 15. Admin Permissions Verification
    # -----------------------------------------------------------------------
    def test_admin_can_recategorize(self):
        article = self._create_article(
            headline="NIC Asia Bank mobile app launch",
            body="NIC Asia Bank Limited launched upgraded digital banking.",
            url="https://example.com/news/admin-perm",
        )
        client = APIClient()
        client.force_authenticate(user=self.admin_user)

        response = client.post(
            f"/api/news/{article.id}/recategorize/",
            {
                "company_id": self.nica.id,
                "action": "add",
                "confidence": 0.95,
                "reason": "Admin tag review",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # -----------------------------------------------------------------------
    # 16. Celery Task Execution Safety
    # -----------------------------------------------------------------------
    def test_celery_task_safety(self):
        article = self._create_article(
            headline="Nabil Bank and NIC Asia digital integration",
            body="Nabil Bank Limited and NIC Asia Bank Limited cooperate on ATM network.",
            url="https://example.com/news/celery-test",
        )

        # Execute task synchronously
        res = categorize_article_task(article.id)
        self.assertTrue(res["success"])
        self.assertGreaterEqual(res["tag_count"], 1)

        # Non-existent article id should fail safely without crashing
        res_missing = categorize_article_task(999999)
        self.assertFalse(res_missing["success"])

    # -----------------------------------------------------------------------
    # 17. Idempotency When Running Categorization Multiple Times
    # -----------------------------------------------------------------------
    def test_categorization_idempotency(self):
        article = self._create_article(
            headline="Nabil Bank profit grows 25% in Q2",
            body="Nabil Bank Limited posted solid revenue and balance sheet expansion.",
            url="https://example.com/news/idempotent",
        )

        # Run 1
        tags_run1 = categorize_article(article)
        count_run1 = ArticleCompanyTag.objects.filter(article=article).count()

        # Run 2
        tags_run2 = categorize_article(article)
        count_run2 = ArticleCompanyTag.objects.filter(article=article).count()

        self.assertEqual(count_run1, count_run2)
        self.assertEqual(len(tags_run1), len(tags_run2))
