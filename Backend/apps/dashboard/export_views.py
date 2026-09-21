import csv

from django.http import HttpResponse

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from apps.users.permissions import HasAppPermission
from apps.market_data.models import DailyPrice, FloorsheetTransaction
from apps.news.models import NewsArticle


class ExportDataAPIView(APIView):
    """
    GET /api/reports/export/?type=prices|floorsheet|analysis|news
        &company_id=&format=csv|json

    Base permission:
        export_reports

    Additional permission by export type:
        prices     -> view_price_history
        floorsheet -> view_trading_volume
        news       -> view_news
    """

    permission_classes = [HasAppPermission]
    permission_key = "export_reports"

    TYPE_PERMISSION = {
        "prices": "view_price_history",
        "floorsheet": "view_trading_volume",
        "news": "view_news",
    }

    def get(self, request):
        export_type = request.query_params.get("type", "prices").lower()

        # ---------------------------------------------------------
        # Per-export permission check
        # ---------------------------------------------------------
        required = self.TYPE_PERMISSION.get(export_type)

        if required and not request.user.has_app_permission(required):
            return Response(
                {
                    "detail": f"Requires {required}."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        export_format = request.query_params.get("format", "csv").lower()
        company_id = request.query_params.get("company_id")

        # =========================================================
        # DAILY PRICES
        # =========================================================
        if export_type == "prices":
            qs = DailyPrice.objects.select_related("company").all()

            if company_id:
                qs = qs.filter(company_id=company_id)

            qs = qs.order_by("-date")[:500]

            if export_format == "csv":
                response = HttpResponse(
                    content_type="text/csv"
                )
                response["Content-Disposition"] = (
                    'attachment; filename="daily_prices.csv"'
                )

                writer = csv.writer(response)

                writer.writerow(
                    [
                        "Symbol",
                        "Company Name",
                        "Date",
                        "Open",
                        "High",
                        "Low",
                        "Close",
                        "Volume",
                        "Turnover",
                    ]
                )

                for p in qs:
                    writer.writerow(
                        [
                            p.company.symbol,
                            p.company.name,
                            p.date,
                            p.open,
                            p.high,
                            p.low,
                            p.close,
                            p.volume,
                            p.turnover,
                        ]
                    )

                return response

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

        # =========================================================
        # FLOORSHEET
        # =========================================================
        elif export_type == "floorsheet":
            qs = FloorsheetTransaction.objects.select_related(
                "company"
            ).all()

            if company_id:
                qs = qs.filter(company_id=company_id)

            qs = qs.order_by("-date", "-id")[:1000]

            if export_format == "csv":
                response = HttpResponse(
                    content_type="text/csv"
                )
                response["Content-Disposition"] = (
                    'attachment; filename="floorsheet.csv"'
                )

                writer = csv.writer(response)

                writer.writerow(
                    [
                        "Symbol",
                        "Date",
                        "Transaction ID",
                        "Buyer Broker",
                        "Seller Broker",
                        "Quantity",
                        "Rate",
                        "Amount",
                    ]
                )

                for f in qs:
                    writer.writerow(
                        [
                            f.company.symbol,
                            f.date,
                            f.transaction_id,
                            f.buyer_broker,
                            f.seller_broker,
                            f.quantity,
                            f.rate,
                            f.amount,
                        ]
                    )

                return response

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

        # =========================================================
        # NEWS
        # =========================================================
        elif export_type == "news":
            qs = (
                NewsArticle.objects
                .prefetch_related("company_tags__company")
                .order_by("-published_at")
            )

            # IMPORTANT:
            # Filter BEFORE slicing so company-specific exports
            # contain the latest 200 articles for that company,
            # rather than filtering the first 200 global articles.
            if company_id:
                qs = qs.filter(
                    company_tags__company_id=company_id
                ).distinct()

            qs = qs[:200]

            if export_format == "csv":
                response = HttpResponse(
                    content_type="text/csv"
                )
                response["Content-Disposition"] = (
                    'attachment; filename="categorized_news.csv"'
                )

                writer = csv.writer(response)

                writer.writerow(
                    [
                        "ID",
                        "Headline",
                        "Source",
                        "URL",
                        "Published At",
                        "Sentiment",
                        "Tagged Companies",
                    ]
                )

                for n in qs:
                    tags = ", ".join(
                        f"{tag.company.symbol} ({tag.confidence:.2f})"
                        for tag in n.company_tags.all()
                    )

                    writer.writerow(
                        [
                            n.id,
                            n.headline,
                            n.source,
                            n.url,
                            n.published_at,
                            n.sentiment_label,
                            tags,
                        ]
                    )

                return response

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
                        {
                            "symbol": tag.company.symbol,
                            "confidence": tag.confidence,
                            "method": tag.method,
                        }
                        for tag in n.company_tags.all()
                    ],
                }
                for n in qs
            ]

            return Response(data)

        # =========================================================
        # INVALID EXPORT TYPE
        # =========================================================
        return Response(
            {
                "error": "Invalid export type."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )