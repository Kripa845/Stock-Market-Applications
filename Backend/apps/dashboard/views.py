from django.db.models import Count, Sum
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.companies.serializers import CompanySerializer
from apps.analysis.views import (
    CrossCompanyAnalysisAPIView,
)
from apps.companies.models import Company
from apps.market_data.models import DailyPrice, FloorsheetTransaction
from apps.news.models import NewsArticle
from apps.users.permissions import IsAdminUserRole


class DashboardSummaryAPIView(APIView):
   

    permission_classes = [IsAuthenticated]

    def get(self, request):
        companies = Company.objects.filter(
            is_active=True,
            tracking__is_tracked=True,
        )

        tracked_companies = companies.count()

        total_news = NewsArticle.objects.count()

        total_trading_days = (
            DailyPrice.objects
            .filter(company__in=companies)
            .values("date")
            .distinct()
            .count()
        )

        total_floorsheet_transactions = (
            FloorsheetTransaction.objects
            .filter(company__in=companies)
            .count()
        )

        latest_prices = (
            DailyPrice.objects
            .filter(company__in=companies)
            .order_by("-date")
        )

        market_volume = 0
        market_turnover = 0.0

        latest_date = (
            latest_prices.values_list("date", flat=True).first()
        )

        if latest_date:
            latest_day_prices = latest_prices.filter(
                date=latest_date
            )

            market_volume = (
                latest_day_prices.aggregate(
                    total=Sum("volume")
                )["total"]
                or 0
            )

            market_turnover = (
                latest_day_prices.aggregate(
                    total=Sum("turnover")
                )["total"]
                or 0
            )

        positive_news = NewsArticle.objects.filter(
            sentiment_label__iexact="positive"
        ).count()

        negative_news = NewsArticle.objects.filter(
            sentiment_label__iexact="negative"
        ).count()

        neutral_news = NewsArticle.objects.filter(
            sentiment_label__iexact="neutral"
        ).count()

        return Response({
            "tracked_companies": tracked_companies,
            "total_news": total_news,
            "total_trading_days": total_trading_days,
            "total_floorsheet_transactions": total_floorsheet_transactions,

            "market_volume": int(market_volume),
            "market_turnover": float(market_turnover),

            "positive_news": positive_news,
            "negative_news": negative_news,
            "neutral_news": neutral_news,
        })


from django.contrib.auth import get_user_model
from django.db.models import Count, Q

from apps.crawler_runs.models import CrawlRun
from apps.crawler_runs.serializers import CrawlRunSerializer
from apps.companies.models import Company


User = get_user_model()


class AdminDashboardAPIView(APIView):
    permission_classes = [IsAdminUserRole]

    def get(self, request):
        total_companies = Company.objects.count()

        total_users = User.objects.count()

        active_crawls = CrawlRun.objects.filter(
            status__in=[
                CrawlRun.Status.PENDING,
                CrawlRun.Status.RUNNING,
            ]
        ).count()

        successful_crawls = CrawlRun.objects.filter(
            status=CrawlRun.Status.SUCCESS
        ).count()

        failed_crawls = CrawlRun.objects.filter(
            status=CrawlRun.Status.FAILED
        ).count()

        recent_runs = (
         CrawlRun.objects
            .select_related("triggered_by")
            .order_by(
                "-created_at",
                "-id",
            )[:10]
)

        companies = (
            Company.objects
            .select_related("tracking")
            .order_by("symbol")[:8]
        )

        return Response({
            "summary": {
                "total_companies": total_companies,
                "total_users": total_users,
                "active_crawl_runs": active_crawls,
                "successful_crawl_runs": successful_crawls,
                "failed_crawl_runs": failed_crawls,
                "total_news": NewsArticle.objects.count(),
            },

            "recent_crawls": CrawlRunSerializer(
                recent_runs,
                many=True,
            ).data,

            "tracked_companies": CompanySerializer(
                [
                    company
                    for company in companies
                    if getattr(
                        getattr(
                            company,
                            "tracking",
                            None,
                        ),
                        "is_tracked",
                        False,
                    )
                ],
                many=True,
            ).data,
        })

class AnalystDashboardAPIView(APIView):
  

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.news.models import CategorizationCorrection

        return Response({
            "role": "analyst",
            "tracked_companies": Company.objects.filter(
                is_active=True,
                tracking__is_tracked=True,
            ).count(),
            "total_news": NewsArticle.objects.count(),
            "corrections_count": CategorizationCorrection.objects.count(),
        })


class ViewerDashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tracked = (
            Company.objects
            .filter(
                is_active=True,
                tracking__is_tracked=True,
            )
            .select_related("tracking")
            .order_by("symbol")[:10]
        )

        return Response({
            "role": request.user.role,
            "summary": {
                "tracked_companies": Company.objects.filter(
                    is_active=True,
                    tracking__is_tracked=True,
                ).count(),

                "total_news": NewsArticle.objects.count(),
            },

            "companies": CompanySerializer(
                tracked,
                many=True,
            ).data,
        })