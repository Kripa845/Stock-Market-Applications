from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.companies.models import Company
from apps.users.permissions import HasAppPermission
from .models import ArticleCompanyTag, CategorizationCorrection, NewsArticle
from .serializers import (
    CategorizationCorrectionSerializer,
    NewsArticleSerializer,
    RecategorizeRequestSerializer,
)
from .tasks import categorize_article_task


class NewsArticleListAPIView(generics.ListAPIView):
    """
    GET /api/news/?company_id=&sentiment=&source=&search=&confidence_min=&confidence_max=&needs_review=
    """
    permission_classes = [HasAppPermission]
    permission_key = "view_news"
    serializer_class = NewsArticleSerializer

    def get_queryset(self):
        qs = NewsArticle.objects.prefetch_related(
            "company_tags__company", "corrections__corrected_by"
        ).all().order_by(
            F("published_at").desc(nulls_last=True),
            F("id").desc(),
        )

        company_id = self.request.query_params.get("company_id")
        if company_id:
            qs = qs.filter(company_tags__company_id=company_id)

        sentiment = self.request.query_params.get("sentiment")
        if sentiment:
            qs = qs.filter(sentiment_label__iexact=sentiment)

        source = self.request.query_params.get("source")
        if source:
            qs = qs.filter(source__iexact=source)

        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(headline__icontains=search) | Q(body__icontains=search)
            )

        confidence_min = self.request.query_params.get("confidence_min")
        if confidence_min:
            try:
                qs = qs.filter(company_tags__confidence__gte=float(confidence_min))
            except ValueError:
                pass

        confidence_max = self.request.query_params.get("confidence_max")
        if confidence_max:
            try:
                qs = qs.filter(company_tags__confidence__lte=float(confidence_max))
            except ValueError:
                pass

        needs_review = self.request.query_params.get("needs_review")
        if needs_review and needs_review.lower() == "true":
            # Filter articles with low confidence (< 0.65) or no company tags
            qs = qs.filter(
                Q(company_tags__confidence__lt=0.65) | Q(company_tags__isnull=True)
            )

        return qs.distinct()


class NewsArticleDetailAPIView(generics.RetrieveAPIView):
    """
    GET /api/news/:id/
    """
    permission_classes = [HasAppPermission]
    permission_key = "view_news"
    serializer_class = NewsArticleSerializer
    queryset = NewsArticle.objects.prefetch_related(
        "company_tags__company", "corrections__corrected_by"
    ).all()


class NewsRecategorizeAPIView(APIView):
    """
    POST /api/news/:id/recategorize/
    Permission-gated: requires categorize_news or correct_categories.
    Body:
    {
      "company_id": 1,
      "action": "add" | "remove" | "update",
      "confidence": 0.95,
      "reason": "Explicit company name mention in 2nd paragraph"
    }
    """
    permission_classes = [HasAppPermission]
    permission_key = "categorize_news"

    def post(self, request, pk):
        article = get_object_or_404(NewsArticle, pk=pk)
        req_serializer = RecategorizeRequestSerializer(data=request.data)
        req_serializer.is_valid(raise_exception=True)

        company_id = req_serializer.validated_data["company_id"]
        action = req_serializer.validated_data["action"]
        confidence = req_serializer.validated_data.get("confidence", 1.0)
        reason = req_serializer.validated_data["reason"]

        company = get_object_or_404(Company, pk=company_id)

        existing_tag = ArticleCompanyTag.objects.filter(
            article=article,
            company=company,
        ).first()

        prev_confidence = existing_tag.confidence if existing_tag else None
        prev_method = existing_tag.method if existing_tag else ""

        if action == "remove":
            if existing_tag:
                existing_tag.delete()
        elif action == "add":
            if not existing_tag:
                ArticleCompanyTag.objects.create(
                    article=article,
                    company=company,
                    confidence=confidence,
                    method="manual",
                    evidence={"manual_reason": reason, "by": request.user.username},
                    is_manual=True,
                )
            else:
                existing_tag.confidence = confidence
                existing_tag.method = "manual"
                existing_tag.is_manual = True
                existing_tag.evidence = {"manual_reason": reason, "by": request.user.username}
                existing_tag.save()
        elif action == "update":
            tag, _ = ArticleCompanyTag.objects.update_or_create(
                article=article,
                company=company,
                defaults={
                    "confidence": confidence,
                    "method": "manual",
                    "evidence": {"manual_reason": reason, "by": request.user.username},
                    "is_manual": True,
                },
            )

        # Log audit trail correction record
        correction = CategorizationCorrection.objects.create(
            article=article,
            company=company,
            previous_confidence=prev_confidence,
            previous_method=prev_method,
            action=action,
            reason=reason,
            corrected_by=request.user,
        )

        article.refresh_from_db()
        return Response(
            {
                "message": f"Article recategorized successfully ({action}).",
                "correction": CategorizationCorrectionSerializer(correction).data,
                "article": NewsArticleSerializer(article).data,
            },
            status=status.HTTP_200_OK,
        )


class NewsTriggerCategorizeAPIView(APIView):
    """
    POST /api/news/:id/trigger-categorize/
    Permission-gated: requires categorize_news permission.
    Dispatches asynchronous Celery auto-categorization task for an article.
    """
    permission_classes = [HasAppPermission]
    permission_key = "categorize_news"

    def post(self, request, pk):
        article = get_object_or_404(NewsArticle, pk=pk)
        task = categorize_article_task.delay(article.id)
        return Response(
            {
                "message": f"Categorization task dispatched for article {article.id}.",
                "task_id": task.id,
                "article_id": article.id,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class NewsStatsAPIView(APIView):
    """
    GET /api/news/stats/
    Provides metrics on total articles, categorized, uncategorized,
    multi-company articles, source breakdown, and company breakdown.
    """
    permission_classes = [HasAppPermission]
    permission_key = "view_news"

    def get(self, request):
        total_articles = NewsArticle.objects.count()
        categorized = NewsArticle.objects.filter(company_tags__isnull=False).distinct().count()
        uncategorized = total_articles - categorized

        multi_company_articles = (
            NewsArticle.objects
            .annotate(tag_count=Count("company_tags"))
            .filter(tag_count__gt=1)
            .count()
        )

        by_source = list(
            NewsArticle.objects
            .values("source")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        by_company = list(
            ArticleCompanyTag.objects
            .values("company__symbol", "company__name")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        return Response({
            "total_articles": total_articles,
            "categorized": categorized,
            "uncategorized": uncategorized,
            "multi_company_articles": multi_company_articles,
            "by_source": by_source,
            "by_company": by_company,
        })


class CategorizationCorrectionListAPIView(generics.ListAPIView):
    """
    GET /api/news/corrections/?article_id=
    Audit log of all manual categorization corrections.
    """
    permission_classes = [HasAppPermission]
    permission_key = "correct_categories"
    serializer_class = CategorizationCorrectionSerializer

    def get_queryset(self):
        qs = CategorizationCorrection.objects.select_related(
            "article", "company", "corrected_by"
        ).all().order_by("-corrected_at")

        article_id = self.request.query_params.get("article_id")
        if article_id:
            qs = qs.filter(article_id=article_id)

        company_id = self.request.query_params.get("company_id")
        if company_id:
            qs = qs.filter(company_id=company_id)

        return qs
