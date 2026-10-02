# from django.db.models import Count, F, Q
# from django.shortcuts import get_object_or_404
# from rest_framework import generics, status
# from rest_framework.permissions import IsAuthenticated
# from rest_framework.response import Response
# from rest_framework.views import APIView

# from apps.companies.models import Company
# from apps.users.permissions import HasAppPermission
# from .models import ArticleCompanyTag, CategorizationCorrection, NewsArticle
# from .serializers import (
#     CategorizationCorrectionSerializer,
#     NewsArticleSerializer,
#     RecategorizeRequestSerializer,
# )
# from .tasks import categorize_article_task


# class NewsArticleListAPIView(generics.ListAPIView):
#     """
#     GET /api/news/?company_id=&sentiment=&source=&search=&confidence_min=&confidence_max=&needs_review=
#     """
#     permission_classes = [HasAppPermission]
#     permission_key = "view_news"
#     serializer_class = NewsArticleSerializer

#     def get_queryset(self):
#         qs = NewsArticle.objects.prefetch_related(
#             "company_tags__company", "corrections__corrected_by"
#         ).all().order_by(
#             F("published_at").desc(nulls_last=True),
#             F("id").desc(),
#         )

#         company_id = self.request.query_params.get("company_id")
#         if company_id:
#             qs = qs.filter(company_tags__company_id=company_id)

#         sentiment = self.request.query_params.get("sentiment")
#         if sentiment:
#             qs = qs.filter(sentiment_label__iexact=sentiment)

#         source = self.request.query_params.get("source")
#         if source:
#             qs = qs.filter(source__iexact=source)

#         search = self.request.query_params.get("search")
#         if search:
#             qs = qs.filter(
#                 Q(headline__icontains=search) | Q(body__icontains=search)
#             )

#         confidence_min = self.request.query_params.get("confidence_min")
#         if confidence_min:
#             try:
#                 qs = qs.filter(company_tags__confidence__gte=float(confidence_min))
#             except ValueError:
#                 pass

#         confidence_max = self.request.query_params.get("confidence_max")
#         if confidence_max:
#             try:
#                 qs = qs.filter(company_tags__confidence__lte=float(confidence_max))
#             except ValueError:
#                 pass

#         needs_review = self.request.query_params.get("needs_review")
#         if needs_review and needs_review.lower() == "true":
#             # Filter articles with low confidence (< 0.65) or no company tags
#             qs = qs.filter(
#                 Q(company_tags__confidence__lt=0.65) | Q(company_tags__isnull=True)
#             )

#         return qs.distinct()


# class NewsArticleDetailAPIView(generics.RetrieveAPIView):
#     """
#     GET /api/news/:id/
#     """
#     permission_classes = [HasAppPermission]
#     permission_key = "view_news"
#     serializer_class = NewsArticleSerializer
#     queryset = NewsArticle.objects.prefetch_related(
#         "company_tags__company", "corrections__corrected_by"
#     ).all()


# class NewsRecategorizeAPIView(APIView):
#     """
#     POST /api/news/:id/recategorize/
#     Permission-gated: requires categorize_news or correct_categories.
#     Body:
#     {
#       "company_id": 1,
#       "action": "add" | "remove" | "update",
#       "confidence": 0.95,
#       "reason": "Explicit company name mention in 2nd paragraph"
#     }
#     """
#     permission_classes = [HasAppPermission]
#     permission_key = "categorize_news"

#     def post(self, request, pk):
#         article = get_object_or_404(NewsArticle, pk=pk)
#         req_serializer = RecategorizeRequestSerializer(data=request.data)
#         req_serializer.is_valid(raise_exception=True)

#         company_id = req_serializer.validated_data["company_id"]
#         action = req_serializer.validated_data["action"]
#         confidence = req_serializer.validated_data.get("confidence", 1.0)
#         reason = req_serializer.validated_data["reason"]

#         company = get_object_or_404(Company, pk=company_id)

#         existing_tag = ArticleCompanyTag.objects.filter(
#             article=article,
#             company=company,
#         ).first()

#         prev_confidence = existing_tag.confidence if existing_tag else None
#         prev_method = existing_tag.method if existing_tag else ""

#         if action == "remove":
#             if existing_tag:
#                 existing_tag.delete()
#         elif action == "add":
#             if not existing_tag:
#                 ArticleCompanyTag.objects.create(
#                     article=article,
#                     company=company,
#                     confidence=confidence,
#                     method="manual",
#                     evidence={"manual_reason": reason, "by": request.user.username},
#                     is_manual=True,
#                 )
#             else:
#                 existing_tag.confidence = confidence
#                 existing_tag.method = "manual"
#                 existing_tag.is_manual = True
#                 existing_tag.evidence = {"manual_reason": reason, "by": request.user.username}
#                 existing_tag.save()
#         elif action == "update":
#             tag, _ = ArticleCompanyTag.objects.update_or_create(
#                 article=article,
#                 company=company,
#                 defaults={
#                     "confidence": confidence,
#                     "method": "manual",
#                     "evidence": {"manual_reason": reason, "by": request.user.username},
#                     "is_manual": True,
#                 },
#             )

#         # Log audit trail correction record
#         correction = CategorizationCorrection.objects.create(
#             article=article,
#             company=company,
#             previous_confidence=prev_confidence,
#             previous_method=prev_method,
#             action=action,
#             reason=reason,
#             corrected_by=request.user,
#         )

#         article.refresh_from_db()
#         return Response(
#             {
#                 "message": f"Article recategorized successfully ({action}).",
#                 "correction": CategorizationCorrectionSerializer(correction).data,
#                 "article": NewsArticleSerializer(article).data,
#             },
#             status=status.HTTP_200_OK,
#         )


# class NewsTriggerCategorizeAPIView(APIView):
#     """
#     POST /api/news/:id/trigger-categorize/
#     Permission-gated: requires categorize_news permission.
#     Dispatches asynchronous Celery auto-categorization task for an article.
#     """
#     permission_classes = [HasAppPermission]
#     permission_key = "categorize_news"

#     def post(self, request, pk):
#         article = get_object_or_404(NewsArticle, pk=pk)
#         task = categorize_article_task.delay(article.id)
#         return Response(
#             {
#                 "message": f"Categorization task dispatched for article {article.id}.",
#                 "task_id": task.id,
#                 "article_id": article.id,
#             },
#             status=status.HTTP_202_ACCEPTED,
#         )


# class NewsStatsAPIView(APIView):
#     """
#     GET /api/news/stats/
#     Provides metrics on total articles, categorized, uncategorized,
#     multi-company articles, source breakdown, and company breakdown.
#     """
#     permission_classes = [HasAppPermission]
#     permission_key = "view_news"

#     def get(self, request):
#         total_articles = NewsArticle.objects.count()
#         categorized = NewsArticle.objects.filter(company_tags__isnull=False).distinct().count()
#         uncategorized = total_articles - categorized

#         multi_company_articles = (
#             NewsArticle.objects
#             .annotate(tag_count=Count("company_tags"))
#             .filter(tag_count__gt=1)
#             .count()
#         )

#         by_source = list(
#             NewsArticle.objects
#             .values("source")
#             .annotate(count=Count("id"))
#             .order_by("-count")
#         )

#         by_company = list(
#             ArticleCompanyTag.objects
#             .values("company__symbol", "company__name")
#             .annotate(count=Count("id"))
#             .order_by("-count")
#         )

#         return Response({
#             "total_articles": total_articles,
#             "categorized": categorized,
#             "uncategorized": uncategorized,
#             "multi_company_articles": multi_company_articles,
#             "by_source": by_source,
#             "by_company": by_company,
#         })


# class CategorizationCorrectionListAPIView(generics.ListAPIView):
#     """
#     GET /api/news/corrections/?article_id=
#     Audit log of all manual categorization corrections.
#     """
#     permission_classes = [HasAppPermission]
#     permission_key = "correct_categories"
#     serializer_class = CategorizationCorrectionSerializer

#     def get_queryset(self):
#         qs = CategorizationCorrection.objects.select_related(
#             "article", "company", "corrected_by"
#         ).all().order_by("-corrected_at")

#         article_id = self.request.query_params.get("article_id")
#         if article_id:
#             qs = qs.filter(article_id=article_id)

#         company_id = self.request.query_params.get("company_id")
#         if company_id:
#             qs = qs.filter(company_id=company_id)

#         return qs
from datetime import timedelta

from django.db.models import Count, F, Q, Prefetch
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.companies.models import Company
from apps.news.services import corrections
from apps.users.permissions import HasAppPermission
from .models import ArticleCompanyTag, CategorizationCorrection, NewsArticle
from .serializers import (
    CategorizationCorrectionSerializer,
    NewsArticleSerializer,
    PublicNewsSerializer,
    RecategorizeRequestSerializer,
)
from .tasks import categorize_article_task
from apps.users.company_access import get_accessible_company_ids, require_company_access


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

        accessible_ids = get_accessible_company_ids(self.request.user)
        if accessible_ids is not None:
            qs = qs.filter(company_tags__company_id__in=accessible_ids).prefetch_related(
                Prefetch(
                    "company_tags",
                    queryset=ArticleCompanyTag.objects.filter(
                        company_id__in=accessible_ids
                    ).select_related("company"),
                ),
                Prefetch(
                    "corrections",
                    queryset=CategorizationCorrection.objects.filter(
                        company_id__in=accessible_ids
                    ).select_related("corrected_by", "company"),
                ),
            )

        company_id = self.request.query_params.get("company_id")
        if company_id:
            require_company_access(self.request.user, company_id)
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
                confidence_filter = {"company_tags__confidence__gte": float(confidence_min)}
                if accessible_ids is not None:
                    confidence_filter["company_tags__company_id__in"] = accessible_ids
                qs = qs.filter(**confidence_filter)
            except ValueError:
                pass

        confidence_max = self.request.query_params.get("confidence_max")
        if confidence_max:
            try:
                confidence_filter = {"company_tags__confidence__lte": float(confidence_max)}
                if accessible_ids is not None:
                    confidence_filter["company_tags__company_id__in"] = accessible_ids
                qs = qs.filter(**confidence_filter)
            except ValueError:
                pass

        needs_review = self.request.query_params.get("needs_review")
        if needs_review and needs_review.lower() == "true":
            # Filter articles with low confidence (< 0.65) or no company tags
            low_confidence = Q(company_tags__confidence__lt=0.65)
            if accessible_ids is not None:
                low_confidence &= Q(company_tags__company_id__in=accessible_ids)
            qs = qs.filter(
                low_confidence | Q(company_tags__isnull=True)
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

    def get_queryset(self):
        qs = super().get_queryset()
        accessible_ids = get_accessible_company_ids(self.request.user)
        if accessible_ids is not None:
            qs = qs.filter(company_tags__company_id__in=accessible_ids).distinct().prefetch_related(
                Prefetch(
                    "company_tags",
                    queryset=ArticleCompanyTag.objects.filter(
                        company_id__in=accessible_ids
                    ).select_related("company"),
                ),
                Prefetch(
                    "corrections",
                    queryset=CategorizationCorrection.objects.filter(
                        company_id__in=accessible_ids
                    ).select_related("corrected_by", "company"),
                ),
            )
        return qs


class NewsRecategorizeAPIView(APIView):
    """
    POST /api/news/:id/recategorize/

    Apply a PERSISTENT manual correction to an article's company tags.

    Body::

        {
          "company_id": 1,
          "action": "add" | "remove" | "update",
          "confidence": 0.95,          # required for add, optional for update
          "reason": "Named in 2nd paragraph"
        }

    All three actions are durable: every one writes a
    ``CategorizationCorrection`` row, and the automatic categorizer reads
    that log before creating or updating tags. A removal therefore stays
    removed across reruns, which deleting the tag row alone never achieved.

    Permission: ``correct_categories``. Corrections overrule the model and
    persist indefinitely, so this is gated separately from
    ``categorize_news`` (which merely re-runs the model and can be undone
    by running it again).
    """

    permission_classes = [HasAppPermission]
    permission_key = "correct_categories"

    def post(self, request, pk):
        article = get_object_or_404(NewsArticle, pk=pk)

        req_serializer = RecategorizeRequestSerializer(data=request.data)
        req_serializer.is_valid(raise_exception=True)

        data = req_serializer.validated_data
        company = get_object_or_404(Company, pk=data["company_id"])
        action = data["action"]
        reason = data.get("reason", "")

        # ── Company Access check ────────────────────────────────────────
        # News VIEWING is unrestricted by company access.
        # News CATEGORIZATION (modifying tags) requires status = 1 for the
        # specific company being categorized.
        # Admins bypass this check.
        from apps.users.company_access import has_company_access
        if not has_company_access(request.user, company.pk):
            return Response(
                {
                    "detail": (
                        f"You do not have company access to {company.symbol}. "
                        "News categorization requires Company Access status = 1 "
                        "for the target company."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # All persistence goes through the corrections service so the API
        # and the Celery/management paths cannot drift apart.
        try:
            if action == corrections.ACTION_REMOVE:
                correction = corrections.apply_remove(
                    article, company, user=request.user, reason=reason,
                )

            elif action == corrections.ACTION_ADD:
                confidence = data.get("confidence")
                if confidence is None:
                    return Response(
                        {"confidence": ["This field is required for action 'add'."]},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                _, correction = corrections.apply_add(
                    article, company,
                    confidence=confidence,
                    user=request.user,
                    reason=reason,
                )

            elif action == corrections.ACTION_UPDATE:
                _, correction = corrections.apply_update(
                    article, company,
                    confidence=data.get("confidence"),
                    user=request.user,
                    reason=reason,
                )

            else:
                return Response(
                    {"action": [f"Unsupported action '{action}'."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except ArticleCompanyTag.DoesNotExist:
            return Response(
                {
                    "detail": (
                        "No existing tag to update for this article and "
                        "company. Use action 'add' to create one."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        except ValueError as exc:
            return Response(
                {"confidence": [str(exc)]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        article.refresh_from_db()

        return Response(
            {
                "message": f"Correction applied and persisted ({action}).",
                "persisted": True,
                "note": (
                    "This correction overrides automatic categorization and "
                    "will not be reverted by subsequent model runs."
                ),
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


class PublicLatestNewsAPIView(APIView):
    """
    GET /api/news/public/latest/?limit=6

    Unauthenticated, for the public landing page: the newest crawled headlines
    with source link, image and a short excerpt -- never the full text, tags or
    sentiment. Articles dated more than a day ahead (mis-parsed dates) are left
    out so they cannot sit at the top indefinitely.
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "public"

    DEFAULT_LIMIT = 6
    MAX_LIMIT = 12

    def get(self, request):
        try:
            limit = int(request.query_params.get("limit", self.DEFAULT_LIMIT))
        except (TypeError, ValueError):
            limit = self.DEFAULT_LIMIT
        limit = max(1, min(limit, self.MAX_LIMIT))

        articles = (
            NewsArticle.objects
            .filter(
                data_provenance="crawled",
                published_at__isnull=False,
                published_at__lte=timezone.now() + timedelta(days=1),
            )
            .order_by("-published_at", "-id")
            .only("id", "headline", "body", "source", "url", "image_url", "published_at")[:limit]
        )
        return Response(PublicNewsSerializer(articles, many=True).data)


class NewsStatsAPIView(APIView):
    """
    GET /api/news/stats/
    Provides metrics on total articles, categorized, uncategorized,
    multi-company articles, source breakdown, and company breakdown.
    """
    permission_classes = [HasAppPermission]
    permission_key = "view_news"

    def get(self, request):
        accessible_ids = get_accessible_company_ids(request.user)
        articles = NewsArticle.objects.all()
        tags = ArticleCompanyTag.objects.all()
        if accessible_ids is not None:
            articles = articles.filter(company_tags__company_id__in=accessible_ids).distinct()
            tags = tags.filter(company_id__in=accessible_ids)
        total_articles = articles.count()
        categorized = articles.filter(company_tags__isnull=False).distinct().count()
        uncategorized = total_articles - categorized

        multi_company_articles = (
            articles
            .annotate(tag_count=Count(
                "company_tags",
                filter=(Q(company_tags__company_id__in=accessible_ids)
                        if accessible_ids is not None else Q()),
            ))
            .filter(tag_count__gt=1)
            .count()
        )

        by_source = list(
            articles
            .values("source")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        by_company = list(
            tags
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
            require_company_access(self.request.user, company_id)
            qs = qs.filter(company_id=company_id)
        else:
            accessible_ids = get_accessible_company_ids(self.request.user)
            if accessible_ids is not None:
                qs = qs.filter(company_id__in=accessible_ids)

        return qs
