import csv
import io
from django.http import HttpResponse, JsonResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from apps.users.permissions import IsAnalystUserRole
from apps.companies.models import Company
from apps.market_data.models import DailyPrice, FloorsheetTransaction
from apps.news.models import NewsArticle, ArticleCompanyTag
from apps.analysis.models import DailyAnalysis


class ExportDataAPIView(APIView):
    """
    GET /api/reports/export/?type=prices|floorsheet|analysis|news&company_id=&format=csv|json
    Role-gated: Analyst & Admin only.
    """
    permission_classes = [IsAnalystUserRole]

    def get(self, request):
        export_type = request.query_params.get("type", "prices").lower()
        export_format = request.query_params.get("format", "csv").lower()
        company_id = request.query_params.get("company_id")

        if export_type == "prices":
            qs = DailyPrice.objects.select_related("company").all()
            if company_id:
                qs = qs.filter(company_id=company_id)
            qs = qs.order_by("-date")[:500]

            if export_format == "csv":
                response = HttpResponse(content_type="text/csv")
                response["Content-Disposition"] = 'attachment; filename="daily_prices.csv"'
                writer = csv.writer(response)
                writer.writerow(["Symbol", "Company Name", "Date", "Open", "High", "Low", "Close", "Volume", "Turnover"])
                for p in qs:
                    writer.writerow([
                        p.company.symbol, p.company.name, p.date,
                        p.open, p.high, p.low, p.close, p.volume, p.turnover
                    ])
                return response
            else:
                data = [
                    {
                        "symbol": p.company.symbol,
                        "date": str(p.date),
                        "open": float(p.open),
                        "high": float(p.high),
                        "low": float(p.low),
                        "close": float(p.close),
                        "volume": int(p.volume),
                        "turnover": float(p.turnover),
                    }
                    for p in qs
                ]
                return Response(data)

        elif export_type == "floorsheet":
            qs = FloorsheetTransaction.objects.select_related("company").all()
            if company_id:
                qs = qs.filter(company_id=company_id)
            qs = qs.order_by("-date", "-id")[:1000]

            if export_format == "csv":
                response = HttpResponse(content_type="text/csv")
                response["Content-Disposition"] = 'attachment; filename="floorsheet.csv"'
                writer = csv.writer(response)
                writer.writerow(["Symbol", "Date", "Transaction ID", "Buyer Broker", "Seller Broker", "Quantity", "Rate", "Amount"])
                for f in qs:
                    writer.writerow([
                        f.company.symbol, f.date, f.transaction_id,
                        f.buyer_broker, f.seller_broker, f.quantity, f.rate, f.amount
                    ])
                return response
            else:
                data = [
                    {
                        "symbol": f.company.symbol,
                        "date": str(f.date),
                        "transaction_id": f.transaction_id,
                        "buyer_broker": f.buyer_broker,
                        "seller_broker": f.seller_broker,
                        "quantity": int(f.quantity),
                        "rate": float(f.rate),
                        "amount": float(f.amount) if f.amount else 0.0,
                    }
                    for f in qs
                ]
                return Response(data)

        elif export_type == "news":
            qs = NewsArticle.objects.prefetch_related("company_tags__company").all().order_by("-published_at")[:200]
            if company_id:
                qs = qs.filter(company_tags__company_id=company_id)

            if export_format == "csv":
                response = HttpResponse(content_type="text/csv")
                response["Content-Disposition"] = 'attachment; filename="categorized_news.csv"'
                writer = csv.writer(response)
                writer.writerow(["ID", "Headline", "Source", "URL", "Published At", "Sentiment", "Tagged Companies"])
                for n in qs:
                    tags = ", ".join([f"{t.company.symbol} ({t.confidence:.2f})" for t in n.company_tags.all()])
                    writer.writerow([
                        n.id, n.headline, n.source, n.url, n.published_at, n.sentiment_label, tags
                    ])
                return response
            else:
                data = [
                    {
                        "id": n.id,
                        "headline": n.headline,
                        "source": n.source,
                        "url": n.url,
                        "published_at": str(n.published_at),
                        "sentiment": n.sentiment,
                        "sentiment_label": n.sentiment_label,
                        "tags": [
                            {"symbol": t.company.symbol, "confidence": t.confidence, "method": t.method}
                            for t in n.company_tags.all()
                        ],
                    }
                    for n in qs
                ]
                return Response(data)

        return Response({"error": "Invalid export type."}, status=status.HTTP_400_BAD_REQUEST)
