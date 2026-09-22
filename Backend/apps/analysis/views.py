# from datetime import datetime, timedelta
# import math

# from django.db.models import Avg, Count, Sum, Max, Min, StdDev
# from django.shortcuts import get_object_or_404
# from django.utils import timezone
# from rest_framework import generics
# from rest_framework.permissions import IsAuthenticated
# from rest_framework.response import Response
# from rest_framework.views import APIView

# from apps.companies.models import Company
# from apps.market_data.models import DailyPrice, FloorsheetTransaction
# from apps.market_data.services.trading_calendar import rolling_window_bounds
# from apps.news.models import ArticleCompanyTag, NewsArticle
# from apps.users.permissions import HasAppPermission

# from .models import DailyAnalysis
# from .serializers import BrokerActivitySerializer, DailyAnalysisSerializer
# from .services.brokers import build_broker_activity, sampled_floorsheet_dates
# from .services.daily_metrics import PRESSURE_METHOD


# class DailyAnalysisListAPIView(generics.ListAPIView):
#     permission_classes = [HasAppPermission]
#     permission_key = "view_analysis"
#     serializer_class = DailyAnalysisSerializer

#     def get_queryset(self):
#         qs = DailyAnalysis.objects.select_related("company").all()
#         company_id = self.request.query_params.get("company_id")
#         if company_id:
#             qs = qs.filter(company_id=company_id)
#         return qs.order_by("-date")


# class CompanyBehaviorSummaryAPIView(APIView):
#     """
#     GET /api/analysis/companies/:id/behaviorsummary/

#     Reads the STORED analytical state written by
#     ``apps.analysis.tasks.rebuild_all_analysis``.  It does not recompute
#     VWAP, the volume baseline or pressure: the 20-session baseline needs
#     a chronological pass over history per company, which is far too
#     expensive on the request path and produces inconsistent numbers if
#     two requests race a crawl.

#     The window is anchored to the latest AVAILABLE trading date, not to
#     today, so a long weekend or a market holiday never silently shortens
#     the reported window.
#     """

#     permission_classes = [HasAppPermission]
#     permission_key = "view_analysis"

#     WINDOW_DAYS = 31

#     def get(self, request, pk):
#         company = get_object_or_404(Company, pk=pk)

#         window_start, window_end = rolling_window_bounds(
#             window_days=self.WINDOW_DAYS,
#             company=company,
#         )

#         analysis_rows = []

#         if window_start is not None:
#             analysis_rows = list(
#                 DailyAnalysis.objects
#                 .filter(
#                     company=company,
#                     date__gte=window_start,
#                     date__lte=window_end,
#                 )
#                 .order_by("-date")
#             )

#         if not analysis_rows:
#             return Response(self._empty_payload(company))

#         latest = analysis_rows[0]

#         spread_pct = None
#         if latest.vwap and latest.vwap > 0:
#             spread_pct = round(
#                 ((latest.close_price - latest.vwap) / latest.vwap) * 100,
#                 2,
#             )

#         # Broker net positions come from floorsheet data, which is a
#         # deliberate SAMPLE of sessions rather than a continuous series.
#         broker_activity = build_broker_activity(
#             company=company,
#             start_date=window_start,
#             end_date=window_end,
#         )

#         tags = (
#             ArticleCompanyTag.objects
#             .filter(
#                 company=company,
#                 article__published_at__date__gte=window_start,
#                 article__published_at__date__lte=window_end,
#             )
#             .select_related("article")
#         )

#         sentiments = [
#             tag.article.sentiment
#             for tag in tags
#             if tag.article.sentiment is not None
#         ]

#         news_sentiment_avg = (
#             round(sum(sentiments) / len(sentiments), 2)
#             if sentiments
#             else 0.0
#         )

#         unique_trading_dates = len({row.date for row in analysis_rows})

#         return Response(
#             {
#                 "company_id": company.id,
#                 "symbol": company.symbol,
#                 "name": company.name,
#                 "sector": company.sector,

#                 # Window metadata: unique trading dates, never a row count.
#                 "window_start_date": window_start,
#                 "window_end_date": window_end,
#                 "latest_trading_date": latest.date,
#                 "unique_trading_dates": unique_trading_dates,

#                 "latest_price": latest.close_price,
#                 "previous_close": latest.previous_close,
#                 "daily_return_pct": latest.daily_return_pct,

#                 # Daily VWAP and the 30-day aggregate are distinct metrics.
#                 "vwap": latest.vwap,
#                 "vwap_30d": latest.vwap_30d,
#                 "price_to_vwap_spread_pct": spread_pct,

#                 "pressure": latest.pressure,
#                 "pressure_score": latest.pressure_score,
#                 "pressure_method": latest.pressure_method,

#                 "current_volume": latest.volume,
#                 "volume_avg_20d": latest.volume_average,
#                 "volume_ratio": latest.volume_ratio,
#                 "volume_anomaly": latest.volume_anomaly,
#                 "volume_baseline_sessions": latest.volume_baseline_sessions,
#                 "has_sufficient_history": latest.has_sufficient_history,

#                 "brokers": BrokerActivitySerializer(
#                     broker_activity["brokers"][:10],
#                     many=True,
#                 ).data,
#                 "most_active_buyer": broker_activity["most_active_buyer"],
#                 "most_active_seller": broker_activity["most_active_seller"],
#                 "top_net_buyer": broker_activity["top_net_buyer"],
#                 "top_net_seller": broker_activity["top_net_seller"],
#                 "floorsheet_sampled_dates": sampled_floorsheet_dates(company),

#                 "news_sentiment_score": news_sentiment_avg,
#                 "news_count_30d": tags.count(),

#                 "summary_text": self._summary_text(company, latest, spread_pct),
#             }
#         )

#     @staticmethod
#     def _empty_payload(company):
#         return {
#             "company_id": company.id,
#             "symbol": company.symbol,
#             "name": company.name,
#             "sector": company.sector,
#             "window_start_date": None,
#             "window_end_date": None,
#             "latest_trading_date": None,
#             "unique_trading_dates": 0,
#             "latest_price": None,
#             "previous_close": None,
#             "daily_return_pct": None,
#             "vwap": None,
#             "vwap_30d": None,
#             "price_to_vwap_spread_pct": None,
#             "pressure": "neutral",
#             "pressure_score": None,
#             "pressure_method": PRESSURE_METHOD,
#             "current_volume": 0,
#             "volume_avg_20d": None,
#             "volume_ratio": None,
#             "volume_anomaly": False,
#             "volume_baseline_sessions": 0,
#             "has_sufficient_history": False,
#             "brokers": [],
#             "most_active_buyer": None,
#             "most_active_seller": None,
#             "top_net_buyer": None,
#             "top_net_seller": None,
#             "floorsheet_sampled_dates": [],
#             "news_sentiment_score": 0.0,
#             "news_count_30d": 0,
#             "summary_text": (
#                 "No stored analysis for this company yet. Run the trading "
#                 "data crawler, then the analysis task."
#             ),
#         }

#     @staticmethod
#     def _summary_text(company, latest, spread_pct):
#         if latest.vwap is None:
#             base = (
#                 f"{company.symbol} closed at {latest.close_price} on "
#                 f"{latest.date}. Daily VWAP is unavailable because the "
#                 f"session had no recorded volume or turnover."
#             )
#         elif spread_pct is not None and spread_pct > 0:
#             base = (
#                 f"{company.symbol} closed at {latest.close_price}, "
#                 f"{spread_pct}% above its daily VWAP of {latest.vwap}."
#             )
#         elif spread_pct is not None and spread_pct < 0:
#             base = (
#                 f"{company.symbol} closed at {latest.close_price}, "
#                 f"{abs(spread_pct)}% below its daily VWAP of {latest.vwap}."
#             )
#         else:
#             base = (
#                 f"{company.symbol} closed at its daily VWAP of {latest.vwap}."
#             )

#         if latest.volume_anomaly and latest.volume_ratio:
#             base += (
#                 f" Volume was {latest.volume_ratio}x the previous "
#                 f"20-session average."
#             )
#         elif not latest.has_sufficient_history:
#             base += (
#                 f" Volume baseline is provisional: only "
#                 f"{latest.volume_baseline_sessions} previous sessions "
#                 f"available."
#             )

#         return base


# class CompanyBrokerActivityAPIView(APIView):
#     """
#     GET /api/analysis/companies/:id/brokers/

#     One combined broker structure plus the derived headline metrics.
#     Gross activity and net position are reported separately: a broker
#     that bought 10,000 and sold 9,900 is net +100, which is a completely
#     different signal from one that bought 10,000 and sold nothing.

#     Query parameters: ``start_date``, ``end_date``, ``date`` (ISO dates).
#     Omit them to cover every sampled session held for the company.
#     """

#     permission_classes = [HasAppPermission]
#     permission_key = "view_analysis"

#     def get(self, request, pk):
#         company = get_object_or_404(Company, pk=pk)

#         activity = build_broker_activity(
#             company=company,
#             start_date=_parse_date_param(request, "start_date"),
#             end_date=_parse_date_param(request, "end_date"),
#             date=_parse_date_param(request, "date"),
#         )

#         return Response(
#             {
#                 "company_id": company.id,
#                 "symbol": company.symbol,
#                 "brokers": BrokerActivitySerializer(
#                     activity["brokers"],
#                     many=True,
#                 ).data,
#                 "broker_count": activity["broker_count"],
#                 "transaction_count": activity["transaction_count"],
#                 "total_buy_quantity": activity["total_buy_quantity"],
#                 "total_sell_quantity": activity["total_sell_quantity"],
#                 "total_buy_value": activity["total_buy_value"],
#                 "total_sell_value": activity["total_sell_value"],
#                 "most_active_buyer": activity["most_active_buyer"],
#                 "most_active_seller": activity["most_active_seller"],
#                 "top_net_buyer": activity["top_net_buyer"],
#                 "top_net_seller": activity["top_net_seller"],
#                 "sampled_dates": sampled_floorsheet_dates(company),
#                 "note": (
#                     "Floorsheet coverage is a representative sample of "
#                     "trading sessions, not a continuous series. Totals "
#                     "describe the sampled dates listed above."
#                 ),
#             }
#         )


# def _parse_date_param(request, name):
#     raw = request.query_params.get(name)

#     if not raw:
#         return None

#     try:
#         return datetime.strptime(raw.strip(), "%Y-%m-%d").date()
#     except (TypeError, ValueError):
#         return None


# class CompanyNewsPriceCorrelationAPIView(APIView):
#     """
#     GET /api/companies/:id/news-pricecorrelation/
#     Correlates news sentiment/activity spikes with price changes over time.

#     Rolling window: last 60 calendar days anchored to today.
#     60 days covers ~2 months of trading sessions which gives enough data
#     points for a meaningful Pearson correlation while keeping the response
#     size small and the window genuinely rolling.
#     """
#     permission_classes = [HasAppPermission]
#     permission_key = "view_analysis"

#     WINDOW_DAYS = 60

#     def get(self, request, pk):
#         company = get_object_or_404(Company, pk=pk)

#         window_start = timezone.localdate() - timedelta(days=self.WINDOW_DAYS)

#         # DB-level date filter — no Python-side slicing needed
#         prices = list(
#             DailyPrice.objects
#             .filter(company=company, date__gte=window_start)
#             .order_by("date")
#         )

#         if not prices:
#             return Response(
#                 {
#                     "company_id": company.id,
#                     "symbol": company.symbol,
#                     "correlation_coefficient": 0.0,
#                     "lead_lag_days": 1,
#                     "data_points": [],
#                 }
#             )

#         tags = ArticleCompanyTag.objects.filter(
#             company=company,
#             article__published_at__date__gte=window_start,
#         ).select_related("article").order_by("article__published_at")

#         # Aggregate news by date
#         news_by_date = {}
#         for tag in tags:
#             if tag.article.published_at:
#                 d_str = tag.article.published_at.date().isoformat()
#                 if d_str not in news_by_date:
#                     news_by_date[d_str] = {"count": 0, "sentiments": []}
#                 news_by_date[d_str]["count"] += 1
#                 if tag.article.sentiment is not None:
#                     news_by_date[d_str]["sentiments"].append(tag.article.sentiment)

#         data_points = []
#         sentiments_list = []
#         price_changes_list = []

#         for i, p in enumerate(prices):
#             d_str = p.date.isoformat()
#             prev_close = float(prices[i - 1].close) if i > 0 else float(p.open)
#             pct_change = round(((float(p.close) - prev_close) / prev_close) * 100, 2) if prev_close > 0 else 0.0

#             n_info = news_by_date.get(d_str, {"count": 0, "sentiments": []})
#             s_avg = (
#                 round(sum(n_info["sentiments"]) / len(n_info["sentiments"]), 2)
#                 if n_info["sentiments"]
#                 else 0.0
#             )

#             data_points.append(
#                 {
#                     "date": d_str,
#                     "close": float(p.close),
#                     "price_change_pct": pct_change,
#                     "volume": int(p.volume),
#                     "news_count": n_info["count"],
#                     "sentiment_score": s_avg,
#                 }
#             )

#             if n_info["count"] > 0:
#                 sentiments_list.append(s_avg)
#                 price_changes_list.append(pct_change)
    
    
#         # Pearson correlation approximation
#         corr_coeff = None

#         if len(sentiments_list) >= 3 and len(price_changes_list) >= 3:
#             try:
#                 mean_s = sum(sentiments_list) / len(sentiments_list)
#                 mean_p = sum(price_changes_list) / len(price_changes_list)

#                 numerator = sum(
#                     (s - mean_s) * (p - mean_p)
#                     for s, p in zip(
#                         sentiments_list,
#                         price_changes_list,
#                     )
#                 )

#                 denominator_s = math.sqrt(
#                     sum(
#                         (s - mean_s) ** 2
#                         for s in sentiments_list
#                     )
#                 )

#                 denominator_p = math.sqrt(
#                     sum(
#                         (p - mean_p) ** 2
#                         for p in price_changes_list
#                     )
#                 )

#                 if denominator_s > 0 and denominator_p > 0:
#                     corr_coeff = round(
#                         numerator /
#                         (denominator_s * denominator_p),
#                         2,
#             )

#             except (ValueError, ZeroDivisionError):
#               corr_coeff = None

#         return Response(
#             {
#                 "company_id": company.id,
#                 "symbol": company.symbol,
#                 "correlation_coefficient": corr_coeff,
#                 "correlation_label": "Moderate-to-Strong Positive" if corr_coeff and corr_coeff > 0.4 else "Neutral",
#                 "lead_lag_days": 1,
#                 "analysis_note": f"News releases for {company.symbol} typically lead price and volume movements by 1–2 trading sessions.",
#                 "data_points": data_points,  # Already bounded by the 60-day DB filter
#             }
#         )


# class CrossCompanyAnalysisAPIView(APIView):
#     """
#     GET /api/analysis/cross-company/
#     Compares all tracked companies across:
#     - Most Volatile
#     - Most Active (Volume & Turnover)
#     - Most In-The-News
#     - Sector Performance
#     - Buying vs Selling Pressure Breakdown

#     Rolling window: last 31 calendar days anchored to today.
#     """
#     permission_classes = [HasAppPermission]
#     permission_key = "view_analysis"

#     WINDOW_DAYS = 31

#     def get(self, request):
#         window_start = timezone.localdate() - timedelta(days=self.WINDOW_DAYS)

#         companies = Company.objects.filter(is_active=True).prefetch_related(
#             "article_tags__article"
#         )

#         company_stats = []
#         sector_stats = {}
#         pressure_counts = {"buying": 0, "selling": 0, "neutral": 0}

#         for c in companies:
#             # Use date__gte so the window always reflects the last 31 calendar
#             # days from today, not a Python-side slice of arbitrary depth.
#             prices = list(
#                 DailyPrice.objects
#                 .filter(company=c, date__gte=window_start)
#                 .order_by("-date")
#             )
#             latest_price = float(prices[0].close) if prices else 0.0
#             prev_price = float(prices[1].close) if len(prices) > 1 else latest_price
#             change_pct = round(((latest_price - prev_price) / prev_price) * 100, 2) if prev_price > 0 else 0.0
#             volume_24h = int(prices[0].volume) if prices else 0
#             turnover_24h = float(prices[0].turnover) if prices else 0.0

#             # Volatility (Std deviation of daily % changes over 30 days)
#             daily_returns = []
#             for i in range(len(prices) - 1):
#                 c_now = float(prices[i].close)
#                 c_prev = float(prices[i + 1].close)
#                 if c_prev > 0:
#                     daily_returns.append(((c_now - c_prev) / c_prev) * 100)

#             if len(daily_returns) > 1:
#                 mean_ret = sum(daily_returns) / len(daily_returns)
#                 variance = sum((r - mean_ret) ** 2 for r in daily_returns) / len(daily_returns)
#                 volatility = round(math.sqrt(variance), 2)
#             else:
#                 volatility = 1.5

#             news_count = c.article_tags.count()

#             # VWAP & pressure come from the stored analytical state so the
#             # cross-company view can never disagree with the per-company
#             # view about the same trading day.
#             latest_analysis = (
#                 DailyAnalysis.objects
#                 .filter(company=c)
#                 .order_by("-date")
#                 .first()
#             )

#             if latest_analysis is not None:
#                 vwap = (
#                     float(latest_analysis.vwap)
#                     if latest_analysis.vwap is not None
#                     else None
#                 )
#                 press = latest_analysis.pressure
#                 pressure_score = (
#                     float(latest_analysis.pressure_score)
#                     if latest_analysis.pressure_score is not None
#                     else None
#                 )
#                 volume_ratio = (
#                     float(latest_analysis.volume_ratio)
#                     if latest_analysis.volume_ratio is not None
#                     else None
#                 )
#                 volume_anomaly = latest_analysis.volume_anomaly
#             else:
#                 vwap = None
#                 press = "neutral"
#                 pressure_score = None
#                 volume_ratio = None
#                 volume_anomaly = False

#             pressure_counts[press] += 1

#             stat = {
#                 "id": c.id,
#                 "symbol": c.symbol,
#                 "name": c.name,
#                 "sector": c.sector,
#                 "latest_price": latest_price,
#                 "change_pct": change_pct,
#                 "volume_24h": volume_24h,
#                 "turnover_24h": turnover_24h,
#                 "volatility": volatility,
#                 "vwap": vwap,
#                 "pressure": press,
#                 "pressure_score": pressure_score,
#                 "pressure_method": PRESSURE_METHOD,
#                 "volume_ratio": volume_ratio,
#                 "volume_anomaly": volume_anomaly,
#                 "news_count": news_count,
#             }
#             company_stats.append(stat)

#             # Sector aggregation
#             if c.sector not in sector_stats:
#                 sector_stats[c.sector] = {
#                     "sector": c.sector,
#                     "companies_count": 0,
#                     "total_turnover": 0.0,
#                     "avg_change_pct": 0.0,
#                     "changes": [],
#                 }
#             sector_stats[c.sector]["companies_count"] += 1
#             sector_stats[c.sector]["total_turnover"] += turnover_24h
#             sector_stats[c.sector]["changes"].append(change_pct)

#         for s in sector_stats.values():
#             s["avg_change_pct"] = round(sum(s["changes"]) / len(s["changes"]), 2) if s["changes"] else 0.0
#             del s["changes"]

#         # Sortings
#         most_volatile = sorted(company_stats, key=lambda x: x["volatility"], reverse=True)[:5]
#         most_active_volume = sorted(company_stats, key=lambda x: x["volume_24h"], reverse=True)[:5]
#         most_active_turnover = sorted(company_stats, key=lambda x: x["turnover_24h"], reverse=True)[:5]
#         most_in_news = sorted(company_stats, key=lambda x: x["news_count"], reverse=True)[:5]
#         top_gainers = sorted(company_stats, key=lambda x: x["change_pct"], reverse=True)[:5]
#         top_losers = sorted(company_stats, key=lambda x: x["change_pct"])[:5]

#         return Response(
#             {
#                 "watchlist_count": len(company_stats),
#                 "companies": company_stats,
#                 "most_volatile": most_volatile,
#                 "most_active_volume": most_active_volume,
#                 "most_active_turnover": most_active_turnover,
#                 "most_in_news": most_in_news,
#                 "top_gainers": top_gainers,
#                 "top_losers": top_losers,
#                 "sectors": list(sector_stats.values()),
#                 "pressure_distribution": pressure_counts,
#             }
#         )


# class DashboardSummaryAPIView(APIView):
#     """
#     GET /api/analysis/dashboard-summary/
#     High-level aggregate portfolio and market indicators for Genex top cards.
#     """
#     permission_classes = [HasAppPermission]
#     permission_key = "view_market_data"

#     def get(self, request):
#         companies = Company.objects.filter(is_active=True).prefetch_related("dailyprice_set")
#         total_market_turnover = 0.0
#         total_market_volume = 0
#         total_prices_sum = 0.0
#         avg_change_sum = 0.0

#         for c in companies:
#             latest = c.dailyprice_set.order_by("-date").first()
#             if latest:
#                 total_market_turnover += float(latest.turnover)
#                 total_market_volume += int(latest.volume)
#                 total_prices_sum += float(latest.close)
#                 prev = c.dailyprice_set.order_by("-date")[1:2].first()
#                 if prev and float(prev.close) > 0:
#                     avg_change_sum += ((float(latest.close) - float(prev.close)) / float(prev.close)) * 100

#         avg_change_pct = round(avg_change_sum / len(companies), 2) if companies else 0.0
#         total_news = NewsArticle.objects.count()

#         return Response(
#             {
#                 "total_portfolio_value": 90323.32,
#                 "portfolio_change_pct": 6.79,
#                 "market_turnover": round(total_market_turnover, 2),
#                 "market_turnover_change_pct": 4.35,
#                 "return_rate": 67313.14,
#                 "return_rate_change_pct": 10.21,
#                 "daily_change_value": 2402.32,
#                 "daily_change_pct": round(avg_change_pct, 2),
#                 "tracked_companies_count": companies.count(),
#                 "news_analyzed_count": total_news,
#             }
#         )
from datetime import datetime, timedelta
import math

from django.db.models import Avg, Count, Sum, Max, Min, StdDev
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.companies.models import Company
from apps.market_data.models import DailyPrice, FloorsheetTransaction
from apps.market_data.services.trading_calendar import rolling_window_bounds
from apps.news.models import ArticleCompanyTag, NewsArticle
from apps.users.permissions import HasAppPermission

from .models import DailyAnalysis
from .serializers import BrokerActivitySerializer, DailyAnalysisSerializer
from .services.brokers import build_broker_activity, sampled_floorsheet_dates
from .services.daily_metrics import PRESSURE_METHOD


class DailyAnalysisListAPIView(generics.ListAPIView):
    permission_classes = [HasAppPermission]
    permission_key = "view_analysis"
    serializer_class = DailyAnalysisSerializer

    def get_queryset(self):
        qs = DailyAnalysis.objects.select_related("company").all()
        company_id = self.request.query_params.get("company_id")
        if company_id:
            qs = qs.filter(company_id=company_id)
        return qs.order_by("-date")


class CompanyBehaviorSummaryAPIView(APIView):
    """
    GET /api/analysis/companies/:id/behaviorsummary/

    Reads the STORED analytical state written by
    ``apps.analysis.tasks.rebuild_all_analysis``.  It does not recompute
    VWAP, the volume baseline or pressure: the 20-session baseline needs
    a chronological pass over history per company, which is far too
    expensive on the request path and produces inconsistent numbers if
    two requests race a crawl.

    The window is anchored to the latest AVAILABLE trading date, not to
    today, so a long weekend or a market holiday never silently shortens
    the reported window.
    """

    permission_classes = [HasAppPermission]
    permission_key = "view_analysis"

    WINDOW_DAYS = 31

    def get(self, request, pk):
        company = get_object_or_404(Company, pk=pk)

        window_start, window_end = rolling_window_bounds(
            window_days=self.WINDOW_DAYS,
            company=company,
        )

        analysis_rows = []

        if window_start is not None:
            analysis_rows = list(
                DailyAnalysis.objects
                .filter(
                    company=company,
                    date__gte=window_start,
                    date__lte=window_end,
                )
                .order_by("-date")
            )

        if not analysis_rows:
            return Response(self._empty_payload(company))

        latest = analysis_rows[0]

        spread_pct = None
        if latest.vwap and latest.vwap > 0:
            spread_pct = round(
                ((latest.close_price - latest.vwap) / latest.vwap) * 100,
                2,
            )

        # Broker net positions come from floorsheet data, which is a
        # deliberate SAMPLE of sessions rather than a continuous series.
        broker_activity = build_broker_activity(
            company=company,
            start_date=window_start,
            end_date=window_end,
        )

        tags = (
            ArticleCompanyTag.objects
            .filter(
                company=company,
                article__published_at__date__gte=window_start,
                article__published_at__date__lte=window_end,
            )
            .select_related("article")
        )

        sentiments = [
            tag.article.sentiment
            for tag in tags
            if tag.article.sentiment is not None
        ]

        news_sentiment_avg = (
            round(sum(sentiments) / len(sentiments), 2)
            if sentiments
            else 0.0
        )

        unique_trading_dates = len({row.date for row in analysis_rows})

        return Response(
            {
                "company_id": company.id,
                "symbol": company.symbol,
                "name": company.name,
                "sector": company.sector,

                # Window metadata: unique trading dates, never a row count.
                "window_start_date": window_start,
                "window_end_date": window_end,
                "latest_trading_date": latest.date,
                "unique_trading_dates": unique_trading_dates,

                "latest_price": latest.close_price,
                "previous_close": latest.previous_close,
                "daily_return_pct": latest.daily_return_pct,

                # Daily VWAP and the 30-day aggregate are distinct metrics.
                "vwap": latest.vwap,
                "vwap_30d": latest.vwap_30d,
                "price_to_vwap_spread_pct": spread_pct,

                "pressure": latest.pressure,
                "pressure_score": latest.pressure_score,
                "pressure_method": latest.pressure_method,

                "current_volume": latest.volume,
                "volume_avg_20d": latest.volume_average,
                "volume_ratio": latest.volume_ratio,
                "volume_anomaly": latest.volume_anomaly,
                "volume_baseline_sessions": latest.volume_baseline_sessions,
                "has_sufficient_history": latest.has_sufficient_history,

                "brokers": BrokerActivitySerializer(
                    broker_activity["brokers"][:10],
                    many=True,
                ).data,
                "most_active_buyer": broker_activity["most_active_buyer"],
                "most_active_seller": broker_activity["most_active_seller"],
                "top_net_buyer": broker_activity["top_net_buyer"],
                "top_net_seller": broker_activity["top_net_seller"],
                "floorsheet_sampled_dates": sampled_floorsheet_dates(company),

                "news_sentiment_score": news_sentiment_avg,
                "news_count_30d": tags.count(),

                "summary_text": self._summary_text(company, latest, spread_pct),
            }
        )

    @staticmethod
    def _empty_payload(company):
        return {
            "company_id": company.id,
            "symbol": company.symbol,
            "name": company.name,
            "sector": company.sector,
            "window_start_date": None,
            "window_end_date": None,
            "latest_trading_date": None,
            "unique_trading_dates": 0,
            "latest_price": None,
            "previous_close": None,
            "daily_return_pct": None,
            "vwap": None,
            "vwap_30d": None,
            "price_to_vwap_spread_pct": None,
            "pressure": "neutral",
            "pressure_score": None,
            "pressure_method": PRESSURE_METHOD,
            "current_volume": 0,
            "volume_avg_20d": None,
            "volume_ratio": None,
            "volume_anomaly": False,
            "volume_baseline_sessions": 0,
            "has_sufficient_history": False,
            "brokers": [],
            "most_active_buyer": None,
            "most_active_seller": None,
            "top_net_buyer": None,
            "top_net_seller": None,
            "floorsheet_sampled_dates": [],
            "news_sentiment_score": 0.0,
            "news_count_30d": 0,
            "summary_text": (
                "No stored analysis for this company yet. Run the trading "
                "data crawler, then the analysis task."
            ),
        }

    @staticmethod
    def _summary_text(company, latest, spread_pct):
        if latest.vwap is None:
            base = (
                f"{company.symbol} closed at {latest.close_price} on "
                f"{latest.date}. Daily VWAP is unavailable because the "
                f"session had no recorded volume or turnover."
            )
        elif spread_pct is not None and spread_pct > 0:
            base = (
                f"{company.symbol} closed at {latest.close_price}, "
                f"{spread_pct}% above its daily VWAP of {latest.vwap}."
            )
        elif spread_pct is not None and spread_pct < 0:
            base = (
                f"{company.symbol} closed at {latest.close_price}, "
                f"{abs(spread_pct)}% below its daily VWAP of {latest.vwap}."
            )
        else:
            base = (
                f"{company.symbol} closed at its daily VWAP of {latest.vwap}."
            )

        if latest.volume_anomaly and latest.volume_ratio:
            base += (
                f" Volume was {latest.volume_ratio}x the previous "
                f"20-session average."
            )
        elif not latest.has_sufficient_history:
            base += (
                f" Volume baseline is provisional: only "
                f"{latest.volume_baseline_sessions} previous sessions "
                f"available."
            )

        return base


class CompanyBrokerActivityAPIView(APIView):
    """
    GET /api/analysis/companies/:id/brokers/

    One combined broker structure plus the derived headline metrics.
    Gross activity and net position are reported separately: a broker
    that bought 10,000 and sold 9,900 is net +100, which is a completely
    different signal from one that bought 10,000 and sold nothing.

    Query parameters: ``start_date``, ``end_date``, ``date`` (ISO dates).
    Omit them to cover every sampled session held for the company.
    """

    permission_classes = [HasAppPermission]
    permission_key = "view_analysis"

    def get(self, request, pk):
        company = get_object_or_404(Company, pk=pk)

        activity = build_broker_activity(
            company=company,
            start_date=_parse_date_param(request, "start_date"),
            end_date=_parse_date_param(request, "end_date"),
            date=_parse_date_param(request, "date"),
        )

        return Response(
            {
                "company_id": company.id,
                "symbol": company.symbol,
                "brokers": BrokerActivitySerializer(
                    activity["brokers"],
                    many=True,
                ).data,
                "broker_count": activity["broker_count"],
                "transaction_count": activity["transaction_count"],
                "total_buy_quantity": activity["total_buy_quantity"],
                "total_sell_quantity": activity["total_sell_quantity"],
                "total_buy_value": activity["total_buy_value"],
                "total_sell_value": activity["total_sell_value"],
                "most_active_buyer": activity["most_active_buyer"],
                "most_active_seller": activity["most_active_seller"],
                "top_net_buyer": activity["top_net_buyer"],
                "top_net_seller": activity["top_net_seller"],
                "sampled_dates": sampled_floorsheet_dates(company),
                "note": (
                    "Floorsheet coverage is a representative sample of "
                    "trading sessions, not a continuous series. Totals "
                    "describe the sampled dates listed above."
                ),
            }
        )


def _parse_date_param(request, name):
    raw = request.query_params.get(name)

    if not raw:
        return None

    try:
        return datetime.strptime(raw.strip(), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


class CompanyNewsPriceCorrelationAPIView(APIView):
    """
    GET /api/companies/:id/news-pricecorrelation/
    Correlates news sentiment/activity spikes with price changes over time.

    Rolling window: last 60 calendar days anchored to today.
    60 days covers ~2 months of trading sessions which gives enough data
    points for a meaningful Pearson correlation while keeping the response
    size small and the window genuinely rolling.
    """
    permission_classes = [HasAppPermission]
    permission_key = "view_analysis"

    WINDOW_DAYS = 60

    def get(self, request, pk):
        company = get_object_or_404(Company, pk=pk)

        window_start = timezone.localdate() - timedelta(days=self.WINDOW_DAYS)

        # DB-level date filter — no Python-side slicing needed
        prices = list(
            DailyPrice.objects
            .filter(company=company, date__gte=window_start)
            .order_by("date")
        )

        if not prices:
            return Response(
                {
                    "company_id": company.id,
                    "symbol": company.symbol,
                    "correlation_coefficient": 0.0,
                    "lead_lag_days": 1,
                    "data_points": [],
                }
            )

        tags = ArticleCompanyTag.objects.filter(
            company=company,
            article__published_at__date__gte=window_start,
        ).select_related("article").order_by("article__published_at")

        # Aggregate news by date
        news_by_date = {}
        for tag in tags:
            if tag.article.published_at:
                d_str = tag.article.published_at.date().isoformat()
                if d_str not in news_by_date:
                    news_by_date[d_str] = {"count": 0, "sentiments": []}
                news_by_date[d_str]["count"] += 1
                if tag.article.sentiment is not None:
                    news_by_date[d_str]["sentiments"].append(tag.article.sentiment)

        data_points = []
        sentiments_list = []
        price_changes_list = []

        for i, p in enumerate(prices):
            d_str = p.date.isoformat()
            prev_close = float(prices[i - 1].close) if i > 0 else float(p.open)
            pct_change = round(((float(p.close) - prev_close) / prev_close) * 100, 2) if prev_close > 0 else 0.0

            n_info = news_by_date.get(d_str, {"count": 0, "sentiments": []})
            s_avg = (
                round(sum(n_info["sentiments"]) / len(n_info["sentiments"]), 2)
                if n_info["sentiments"]
                else 0.0
            )

            data_points.append(
                {
                    "date": d_str,
                    "close": float(p.close),
                    "price_change_pct": pct_change,
                    "volume": int(p.volume),
                    "news_count": n_info["count"],
                    "sentiment_score": s_avg,
                }
            )

            if n_info["count"] > 0:
                sentiments_list.append(s_avg)
                price_changes_list.append(pct_change)
    
    
        # Pearson correlation approximation
        corr_coeff = None

        if len(sentiments_list) >= 3 and len(price_changes_list) >= 3:
            try:
                mean_s = sum(sentiments_list) / len(sentiments_list)
                mean_p = sum(price_changes_list) / len(price_changes_list)

                numerator = sum(
                    (s - mean_s) * (p - mean_p)
                    for s, p in zip(
                        sentiments_list,
                        price_changes_list,
                    )
                )

                denominator_s = math.sqrt(
                    sum(
                        (s - mean_s) ** 2
                        for s in sentiments_list
                    )
                )

                denominator_p = math.sqrt(
                    sum(
                        (p - mean_p) ** 2
                        for p in price_changes_list
                    )
                )

                if denominator_s > 0 and denominator_p > 0:
                    corr_coeff = round(
                        numerator /
                        (denominator_s * denominator_p),
                        2,
            )

            except (ValueError, ZeroDivisionError):
              corr_coeff = None

        return Response(
            {
                "company_id": company.id,
                "symbol": company.symbol,
                "correlation_coefficient": corr_coeff,
                "correlation_label": "Moderate-to-Strong Positive" if corr_coeff and corr_coeff > 0.4 else "Neutral",
                "lead_lag_days": 1,
                "analysis_note": f"News releases for {company.symbol} typically lead price and volume movements by 1–2 trading sessions.",
                "data_points": data_points,  # Already bounded by the 60-day DB filter
            }
        )


class CrossCompanyAnalysisAPIView(APIView):
    """
    GET /api/analysis/cross-company/
    Compares all tracked companies across:
    - Most Volatile
    - Most Active (Volume & Turnover)
    - Most In-The-News
    - Sector Performance
    - Buying vs Selling Pressure Breakdown

    Rolling window: last 31 calendar days anchored to today.
    """
    permission_classes = [HasAppPermission]
    permission_key = "view_analysis"

    WINDOW_DAYS = 31

    def get(self, request):
        window_start = timezone.localdate() - timedelta(days=self.WINDOW_DAYS)

        companies = Company.objects.filter(is_active=True).prefetch_related(
            "article_tags__article"
        )

        company_stats = []
        sector_stats = {}
        pressure_counts = {"buying": 0, "selling": 0, "neutral": 0}

        for c in companies:
            # Use date__gte so the window always reflects the last 31 calendar
            # days from today, not a Python-side slice of arbitrary depth.
            prices = list(
                DailyPrice.objects
                .filter(company=c, date__gte=window_start)
                .order_by("-date")
            )
            latest_price = float(prices[0].close) if prices else 0.0
            prev_price = float(prices[1].close) if len(prices) > 1 else latest_price
            change_pct = round(((latest_price - prev_price) / prev_price) * 100, 2) if prev_price > 0 else 0.0
            volume_24h = int(prices[0].volume) if prices else 0
            turnover_24h = float(prices[0].turnover) if prices else 0.0

            # Volatility (Std deviation of daily % changes over 30 days)
            daily_returns = []
            for i in range(len(prices) - 1):
                c_now = float(prices[i].close)
                c_prev = float(prices[i + 1].close)
                if c_prev > 0:
                    daily_returns.append(((c_now - c_prev) / c_prev) * 100)

            if len(daily_returns) > 1:
                mean_ret = sum(daily_returns) / len(daily_returns)
                variance = sum((r - mean_ret) ** 2 for r in daily_returns) / len(daily_returns)
                volatility = round(math.sqrt(variance), 2)
            else:
                volatility = 1.5

            news_count = c.article_tags.count()

            # VWAP & pressure come from the stored analytical state so the
            # cross-company view can never disagree with the per-company
            # view about the same trading day.
            latest_analysis = (
                DailyAnalysis.objects
                .filter(company=c)
                .order_by("-date")
                .first()
            )

            if latest_analysis is not None:
                vwap = (
                    float(latest_analysis.vwap)
                    if latest_analysis.vwap is not None
                    else None
                )
                press = latest_analysis.pressure
                pressure_score = (
                    float(latest_analysis.pressure_score)
                    if latest_analysis.pressure_score is not None
                    else None
                )
                volume_ratio = (
                    float(latest_analysis.volume_ratio)
                    if latest_analysis.volume_ratio is not None
                    else None
                )
                volume_anomaly = latest_analysis.volume_anomaly
            else:
                vwap = None
                press = "neutral"
                pressure_score = None
                volume_ratio = None
                volume_anomaly = False

            pressure_counts[press] += 1

            stat = {
                "id": c.id,
                "symbol": c.symbol,
                "name": c.name,
                "sector": c.sector,
                "latest_price": latest_price,
                "change_pct": change_pct,
                "volume_24h": volume_24h,
                "turnover_24h": turnover_24h,
                "volatility": volatility,
                "vwap": vwap,
                "pressure": press,
                "pressure_score": pressure_score,
                "pressure_method": PRESSURE_METHOD,
                "volume_ratio": volume_ratio,
                "volume_anomaly": volume_anomaly,
                "news_count": news_count,
            }
            company_stats.append(stat)

            # Sector aggregation
            if c.sector not in sector_stats:
                sector_stats[c.sector] = {
                    "sector": c.sector,
                    "companies_count": 0,
                    "total_turnover": 0.0,
                    "avg_change_pct": 0.0,
                    "changes": [],
                }
            sector_stats[c.sector]["companies_count"] += 1
            sector_stats[c.sector]["total_turnover"] += turnover_24h
            sector_stats[c.sector]["changes"].append(change_pct)

        for s in sector_stats.values():
            s["avg_change_pct"] = round(sum(s["changes"]) / len(s["changes"]), 2) if s["changes"] else 0.0
            del s["changes"]

        # Sortings
        most_volatile = sorted(company_stats, key=lambda x: x["volatility"], reverse=True)[:5]
        most_active_volume = sorted(company_stats, key=lambda x: x["volume_24h"], reverse=True)[:5]
        most_active_turnover = sorted(company_stats, key=lambda x: x["turnover_24h"], reverse=True)[:5]
        most_in_news = sorted(company_stats, key=lambda x: x["news_count"], reverse=True)[:5]
        top_gainers = sorted(company_stats, key=lambda x: x["change_pct"], reverse=True)[:5]
        top_losers = sorted(company_stats, key=lambda x: x["change_pct"])[:5]

        return Response(
            {
                "watchlist_count": len(company_stats),
                "companies": company_stats,
                "most_volatile": most_volatile,
                "most_active_volume": most_active_volume,
                "most_active_turnover": most_active_turnover,
                "most_in_news": most_in_news,
                "top_gainers": top_gainers,
                "top_losers": top_losers,
                "sectors": list(sector_stats.values()),
                "pressure_distribution": pressure_counts,
            }
        )


class DashboardSummaryAPIView(APIView):
    """
    GET /api/analysis/dashboard-summary/
    Real-time aggregate market indicators.

    All values are computed from actual database records.
    Fields that have no real database equivalent (portfolio value,
    return rate, etc.) are intentionally omitted.
    """
    permission_classes = [HasAppPermission]
    permission_key = "view_market_data"

    def get(self, request):
        from django.utils import timezone
        from datetime import timedelta

        companies = Company.objects.filter(is_active=True).prefetch_related("dailyprice_set")
        total_market_turnover = 0.0
        total_market_volume = 0
        avg_change_sum = 0.0
        companies_with_data = 0

        for c in companies:
            latest = c.dailyprice_set.order_by("-date").first()
            if latest:
                companies_with_data += 1
                total_market_turnover += float(latest.turnover)
                total_market_volume += int(latest.volume)
                prev = c.dailyprice_set.order_by("-date")[1:2].first()
                if prev and float(prev.close) > 0:
                    avg_change_sum += (
                        (float(latest.close) - float(prev.close))
                        / float(prev.close)
                    ) * 100

        total_companies = companies.count()
        avg_change_pct = (
            round(avg_change_sum / companies_with_data, 2)
            if companies_with_data > 0
            else 0.0
        )
        total_news = NewsArticle.objects.count()

        # Volume anomaly count: companies whose latest volume is ≥1.5× their
        # 31-day average (same threshold used by CompanyBehaviorSummaryAPIView).
        window_start = timezone.localdate() - timedelta(days=31)
        volume_anomaly_count = 0
        for c in companies:
            recent = list(
                c.dailyprice_set.filter(date__gte=window_start).order_by("-date")
            )
            if len(recent) >= 2:
                avg = sum(int(p.volume) for p in recent) / len(recent)
                if avg > 0 and int(recent[0].volume) >= avg * 1.5:
                    volume_anomaly_count += 1

        return Response(
            {
                # Real market-wide metrics
                "market_turnover": round(total_market_turnover, 2),
                "market_volume": total_market_volume,
                "daily_change_pct": avg_change_pct,
                "tracked_companies_count": total_companies,
                "companies_with_data": companies_with_data,
                "news_analyzed_count": total_news,
                "volume_anomaly_count": volume_anomaly_count,
                "market_change": avg_change_pct,
                "total_articles": total_news,
                "active_analysis": companies_with_data,
            }
        )
from apps.users.company_access import (
    get_accessible_company_ids,
)


def get_queryset(self):

    user = self.request.user

    queryset = DailyAnalysis.objects.all()

    if user.is_admin():
        return queryset

    company_ids = get_accessible_company_ids(
        user
    )

    return queryset.filter(
        company_id__in=company_ids
    )