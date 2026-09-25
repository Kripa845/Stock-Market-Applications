from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.companies.serializers import CompanySerializer
from apps.companies.models import Company
from apps.crawler_runs.models import CrawlRun
from apps.crawler_runs.serializers import CrawlRunSerializer
from apps.market_data.models import DailyPrice, FloorsheetTransaction
from apps.news.models import NewsArticle
from apps.users.permissions import HasAppPermission, HasViewMethodPermissions
from apps.users.company_access import filter_company_queryset, get_accessible_company_ids


User = get_user_model()


class DashboardSummaryAPIView(APIView):
    """
    GET /api/dashboard/summary/
    General market summary — requires view_market_data or view_news.
    Returns whichever data the user is permitted to see.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        result = {}

        if user.has_app_permission("view_companies") or user.has_app_permission("view_market_data"):
            companies = Company.objects.filter(
                is_active=True,
                tracking__is_tracked=True,
            )
            companies = filter_company_queryset(companies, user, "id")
            tracked_companies = companies.count()

            latest_prices = DailyPrice.objects.filter(
                company__in=companies,
            ).order_by("-date")

            market_volume = 0
            market_turnover = 0.0
            latest_date = latest_prices.values_list("date", flat=True).first()

            if latest_date:
                latest_day_prices = latest_prices.filter(date=latest_date)
                market_volume = latest_day_prices.aggregate(total=Sum("volume"))["total"] or 0
                market_turnover = latest_day_prices.aggregate(total=Sum("turnover"))["total"] or 0.0

            result["tracked_companies"] = tracked_companies
            result["market_volume"] = int(market_volume)
            result["market_turnover"] = float(market_turnover)
            result["total_trading_days"] = (
                DailyPrice.objects
                .filter(company__in=companies)
                .values("date")
                .distinct()
                .count()
            )
            if user.has_app_permission("view_market_data"):
                result["total_floorsheet_transactions"] = (
                    FloorsheetTransaction.objects
                    .filter(company__in=companies)
                    .count()
                )

        if user.has_app_permission("view_news"):
            news = NewsArticle.objects.all()
            accessible_ids = get_accessible_company_ids(user)
            if accessible_ids is not None:
                news = news.filter(company_tags__company_id__in=accessible_ids).distinct()
            result["total_news"] = news.count()
            result["positive_news"] = news.filter(sentiment_label__iexact="positive").count()
            result["negative_news"] = news.filter(sentiment_label__iexact="negative").count()
            result["neutral_news"] = news.filter(sentiment_label__iexact="neutral").count()

        return Response(result)


class AdminDashboardAPIView(APIView):
    """
    GET /api/dashboard/admin/
    Full admin dashboard — requires view_users AND view_crawl_runs.
    Falls back gracefully for each section depending on permissions.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Must have at least one relevant admin permission to access this endpoint
        if not user.is_admin() and not any(
            user.has_app_permission(p)
            for p in ["view_users", "view_crawl_runs", "view_companies", "view_news"]
        ):
            from rest_framework import status as http_status
            from rest_framework.response import Response as R
            return R(
                {"detail": "You do not have permission to access the admin dashboard."},
                status=http_status.HTTP_403_FORBIDDEN,
            )

        summary = {}

        if user.has_app_permission("view_companies") or user.is_admin():
            summary["total_companies"] = filter_company_queryset(
                Company.objects.all(), user, "id"
            ).count()

        if user.has_app_permission("view_users") or user.is_admin():
            summary["total_users"] = User.objects.count()

        if user.has_app_permission("view_news") or user.is_admin():
            news = NewsArticle.objects.all()
            accessible_ids = get_accessible_company_ids(user)
            if accessible_ids is not None:
                news = news.filter(company_tags__company_id__in=accessible_ids).distinct()
            summary["total_news"] = news.count()

        if user.has_app_permission("view_crawl_runs") or user.is_admin():
            summary["active_crawl_runs"] = CrawlRun.objects.filter(
                status__in=[CrawlRun.Status.PENDING, CrawlRun.Status.RUNNING]
            ).count()
            summary["successful_crawl_runs"] = CrawlRun.objects.filter(
                status=CrawlRun.Status.SUCCESS
            ).count()
            summary["failed_crawl_runs"] = CrawlRun.objects.filter(
                status=CrawlRun.Status.FAILED
            ).count()

        recent_crawls_data = []
        if user.has_app_permission("view_crawl_runs") or user.is_admin():
            recent_runs = (
                CrawlRun.objects
                .select_related("triggered_by")
                .order_by("-created_at", "-id")[:10]
            )
            recent_crawls_data = CrawlRunSerializer(recent_runs, many=True).data

        tracked_companies_data = []
        if user.has_app_permission("view_companies") or user.is_admin():
            companies = (
                filter_company_queryset(Company.objects.all(), user, "id")
                .select_related("tracking")
                .order_by("symbol")[:8]
            )
            tracked_companies_data = CompanySerializer(
                [
                    company
                    for company in companies
                    if getattr(getattr(company, "tracking", None), "is_tracked", False)
                ],
                many=True,
            ).data

        return Response({
            "summary": summary,
            "recent_crawls": recent_crawls_data,
            "tracked_companies": tracked_companies_data,
        })


class AnalystDashboardAPIView(APIView):
    """
    GET /api/dashboard/analyst/
    Analyst dashboard — requires view_news or view_companies.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if not any(
            user.has_app_permission(p)
            for p in ["view_news", "view_companies", "view_market_data", "view_analysis"]
        ):
            from rest_framework import status as http_status
            return Response(
                {"detail": "You do not have permission to access this dashboard."},
                status=http_status.HTTP_403_FORBIDDEN,
            )

        from apps.news.models import CategorizationCorrection

        result = {"role": "analyst"}

        if user.has_app_permission("view_companies") or user.has_app_permission("view_market_data"):
            companies = Company.objects.filter(
                is_active=True,
                tracking__is_tracked=True,
            )
            result["tracked_companies"] = filter_company_queryset(
                companies, user, "id"
            ).count()

        if user.has_app_permission("view_news"):
            news = NewsArticle.objects.all()
            accessible_ids = get_accessible_company_ids(user)
            if accessible_ids is not None:
                news = news.filter(company_tags__company_id__in=accessible_ids).distinct()
            result["total_news"] = news.count()

        if user.has_app_permission("correct_categories"):
            corrections = CategorizationCorrection.objects.all()
            accessible_ids = get_accessible_company_ids(user)
            if accessible_ids is not None:
                corrections = corrections.filter(company_id__in=accessible_ids)
            result["corrections_count"] = corrections.count()

        return Response(result)


class ViewerDashboardAPIView(APIView):
    """
    GET /api/dashboard/viewer/
    Viewer dashboard — requires view_market_data or view_news.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if not any(
            user.has_app_permission(p)
            for p in ["view_news", "view_companies", "view_market_data", "view_analysis"]
        ):
            from rest_framework import status as http_status
            return Response(
                {"detail": "You do not have permission to access this dashboard."},
                status=http_status.HTTP_403_FORBIDDEN,
            )

        result = {"role": request.user.role}
        summary = {}

        if user.has_app_permission("view_companies") or user.has_app_permission("view_market_data"):
            tracked_count = filter_company_queryset(Company.objects.filter(
                is_active=True,
                tracking__is_tracked=True,
            ), user, "id").count()
            summary["tracked_companies"] = tracked_count
            result["tracked_companies"] = tracked_count

        if user.has_app_permission("view_news"):
            news = NewsArticle.objects.all()
            accessible_ids = get_accessible_company_ids(user)
            if accessible_ids is not None:
                news = news.filter(company_tags__company_id__in=accessible_ids).distinct()
            total_news = news.count()
            summary["total_news"] = total_news
            result["total_news"] = total_news

        result["summary"] = summary

        if user.has_app_permission("view_companies"):
            tracked = (
                filter_company_queryset(Company.objects, user, "id")
                .filter(is_active=True, tracking__is_tracked=True)
                .select_related("tracking")
                .order_by("symbol")[:10]
            )
            result["companies"] = CompanySerializer(tracked, many=True).data

        return Response(result)
