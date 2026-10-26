"""
GET export/report/ -- the combined analysis report (PDF or XLSX).
"""

import io
from datetime import datetime

from django.db.models import Avg, Count, Max, Min, Sum
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analysis.models import DailyAnalysis
from apps.floorsheet.models import FloorsheetTransaction
from apps.market_data.models import DailyPrice
from apps.market_data.services.price_source import with_crawled_price
from apps.news.models import NewsArticle
from apps.news.selectors import real_articles
from apps.users.permissions import HasAppPermission
from apps.reports.exports.common import (
    _apply_xlsx_header,
    _autofit_xlsx,
    _bad_request,
    cm,
    ExportContentNegotiation,
    _filename,
    Font,
    openpyxl,
    OPENPYXL_AVAILABLE,
    Paragraph,
    _parse_date,
    _pdf_doc,
    _pdf_response,
    _pdf_styles,
    _pdf_table_style,
    REPORTLAB_AVAILABLE,
    _resolve_companies,
    Spacer,
    Table,
    _validate_date_range,
    _xlsx_header_style,
    _xlsx_response,
)


# ============================================================
# COMBINED ANALYSIS REPORT (PDF + XLSX)
# ============================================================

class ExportReportAPIView(APIView):
   
    permission_classes = [HasAppPermission]
    permission_key = "export_reports"
    content_negotiation_class = ExportContentNegotiation

    def get(self, request):
        fmt = request.query_params.get("format", "pdf").lower()
        company_id_strs = request.query_params.getlist("company_id")
        date_from_str = request.query_params.get("date_from", "")
        date_to_str = request.query_params.get("date_to", "")

        companies, err = _resolve_companies(company_id_strs, request.user)
        if err:
            return err

        date_from, err = _parse_date(date_from_str, "date_from")
        if err:
            return err
        date_to, err = _parse_date(date_to_str, "date_to")
        if err:
            return err
        range_err = _validate_date_range(date_from, date_to)
        if range_err:
            return range_err

        if fmt not in ("pdf", "xlsx"):
            return _bad_request("Report format must be pdf or xlsx.")

        # ── gather data ───────────────────────────────────────────────
        data = self._collect_data(companies, date_from, date_to)

        if not data["has_any_data"]:
            return Response(
                {"message": "No data found for the selected filters."},
                status=status.HTTP_204_NO_CONTENT,
            )

        fname = _filename("analysis_report", companies, date_from, date_to, fmt)

        if fmt == "pdf":
            if not REPORTLAB_AVAILABLE:
                return _bad_request("PDF export requires reportlab.")
            return self._build_pdf(data, fname, companies, date_from, date_to)

        if fmt == "xlsx":
            if not OPENPYXL_AVAILABLE:
                return _bad_request("XLSX export requires openpyxl.")
            return self._build_xlsx(data, fname, companies, date_from, date_to)

    # ------------------------------------------------------------------
    # DATA COLLECTION
    # ------------------------------------------------------------------

    def _collect_data(self, companies, date_from, date_to):
        """Gather all metrics from the database. Pure queries, no I/O."""
        result = {"has_any_data": False}

        # ── Trading summary ───────────────────────────────────────────
        price_qs = DailyPrice.objects.filter(source="crawled").select_related("company")
        price_qs = price_qs.filter(company__in=companies)
        if date_from:
            price_qs = price_qs.filter(date__gte=date_from)
        if date_to:
            price_qs = price_qs.filter(date__lte=date_to)

        price_agg = price_qs.aggregate(
            open_first=Min("open"),
            high_max=Max("high"),
            low_min=Min("low"),
            close_last=Max("close"),   # proxy for last close
            total_volume=Sum("volume"),
            total_turnover=Sum("turnover"),
            trading_days=Count("id", distinct=True),
        )
        if price_agg["total_volume"]:
            result["has_any_data"] = True
            # Get actual first open and last close via ordering
            first_row = price_qs.order_by("date").values("open").first()
            last_row = price_qs.order_by("-date").values("close").first()
            result["trading"] = {
                "trading_days": price_agg["trading_days"] or 0,
                "open_price": float(first_row["open"]) if first_row else None,
                "close_price": float(last_row["close"]) if last_row else None,
                "high": float(price_agg["high_max"]) if price_agg["high_max"] else None,
                "low": float(price_agg["low_min"]) if price_agg["low_min"] else None,
                "total_volume": int(price_agg["total_volume"]),
                "total_turnover": float(price_agg["total_turnover"] or 0),
            }
        else:
            result["trading"] = None

        # ── News summary ──────────────────────────────────────────────
        news_qs = real_articles(NewsArticle.objects.all())
        news_qs = news_qs.filter(company_tags__company__in=companies).distinct()
        if date_from:
            news_qs = news_qs.filter(published_at__date__gte=date_from)
        if date_to:
            news_qs = news_qs.filter(published_at__date__lte=date_to)

        total_news = news_qs.count()
        if total_news:
            result["has_any_data"] = True
            result["news"] = {
                "total": total_news,
                "positive": news_qs.filter(sentiment_label__iexact="positive").count(),
                "negative": news_qs.filter(sentiment_label__iexact="negative").count(),
                "neutral": news_qs.filter(sentiment_label__iexact="neutral").count(),
            }
        else:
            result["news"] = None

        # ── Floorsheet summary ────────────────────────────────────────
        fs_qs = FloorsheetTransaction.objects.all()
        fs_qs = fs_qs.filter(company__in=companies)
        if date_from:
            fs_qs = fs_qs.filter(date__gte=date_from)
        if date_to:
            fs_qs = fs_qs.filter(date__lte=date_to)

        fs_agg = fs_qs.aggregate(
            total_transactions=Count("id"),
            total_quantity=Sum("quantity"),
            total_amount=Sum("amount"),
            avg_rate=Avg("rate"),
        )
        if fs_agg["total_transactions"]:
            result["has_any_data"] = True
            result["floorsheet"] = {
                "total_transactions": fs_agg["total_transactions"],
                "total_quantity": int(fs_agg["total_quantity"] or 0),
                "total_amount": float(fs_agg["total_amount"] or 0),
                "avg_rate": float(fs_agg["avg_rate"] or 0),
            }
        else:
            result["floorsheet"] = None

        # ── Analysis metrics (from DailyAnalysis) ────────────────────
        analysis_qs = with_crawled_price(DailyAnalysis.objects.all())
        analysis_qs = analysis_qs.filter(company__in=companies)
        if date_from:
            analysis_qs = analysis_qs.filter(date__gte=date_from)
        if date_to:
            analysis_qs = analysis_qs.filter(date__lte=date_to)

        latest_analysis = analysis_qs.order_by("-date").first()
        if latest_analysis:
            result["has_any_data"] = True
            result["analysis"] = {
                "latest_date": str(latest_analysis.date),
                "vwap": float(latest_analysis.vwap) if latest_analysis.vwap else None,
                "vwap_30d": float(latest_analysis.vwap_30d) if latest_analysis.vwap_30d else None,
                "pressure": latest_analysis.pressure,
                "pressure_score": float(latest_analysis.pressure_score) if latest_analysis.pressure_score else None,
                "volume_ratio": float(latest_analysis.volume_ratio) if latest_analysis.volume_ratio else None,
                "volume_anomaly": latest_analysis.volume_anomaly,
                "daily_return_pct": float(latest_analysis.daily_return_pct) if latest_analysis.daily_return_pct else None,
            }
        else:
            result["analysis"] = None

        return result

    # ------------------------------------------------------------------
    # PDF REPORT
    # ------------------------------------------------------------------

    def _build_pdf(self, data, fname, companies, date_from, date_to):
        buf = io.BytesIO()
        doc = _pdf_doc(buf, "Stock Market Analysis Report")
        styles = _pdf_styles()
        story = []

        # ── Header ────────────────────────────────────────────────────
        story.append(Paragraph("STOCK MARKET ANALYSIS REPORT", styles["ReportTitle"]))
        story.append(Spacer(1, 0.2 * cm))

        if companies:
            symbols = ", ".join(c.symbol for c in companies)
            story.append(Paragraph(f"Companies: {symbols}", styles["SubHeading"]))
            sectors = ", ".join({c.sector for c in companies})
            story.append(Paragraph(f"Sectors: {sectors}", styles["BodySmall"]))

        period_str = f"{date_from or '—'}  to  {date_to or '—'}"
        story.append(Paragraph(f"Period: {period_str}", styles["BodySmall"]))
        story.append(Paragraph(
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            styles["BodySmall"],
        ))
        story.append(Spacer(1, 0.5 * cm))

        # ── Trading Summary ───────────────────────────────────────────
        if data["trading"]:
            t = data["trading"]
            story.append(Paragraph("TRADING SUMMARY", styles["SectionHeading"]))
            trading_rows = [
                ["Metric", "Value"],
                ["Trading Days", str(t["trading_days"])],
                ["Opening Price", f"{t['open_price']:,.2f}" if t["open_price"] is not None else "N/A"],
                ["Closing Price (latest)", f"{t['close_price']:,.2f}" if t["close_price"] is not None else "N/A"],
                ["Period High", f"{t['high']:,.2f}" if t["high"] is not None else "N/A"],
                ["Period Low", f"{t['low']:,.2f}" if t["low"] is not None else "N/A"],
                ["Total Volume", f"{t['total_volume']:,}"],
                ["Total Turnover", f"{t['total_turnover']:,.2f}"],
            ]
            tbl = Table(trading_rows, colWidths=[8 * cm, 8 * cm], repeatRows=1)
            tbl.setStyle(_pdf_table_style())
            story.append(tbl)
            story.append(Spacer(1, 0.4 * cm))

        # ── Analysis ─────────────────────────────────────────────────
        if data["analysis"]:
            a = data["analysis"]
            story.append(Paragraph("ANALYSIS METRICS (Latest Day)", styles["SectionHeading"]))
            analysis_rows = [
                ["Metric", "Value"],
                ["Latest Date", a["latest_date"]],
                ["Daily VWAP", f"{a['vwap']:,.4f}" if a["vwap"] is not None else "N/A"],
                ["30-Day VWAP", f"{a['vwap_30d']:,.4f}" if a["vwap_30d"] is not None else "N/A"],
                ["Market Pressure", a["pressure"].capitalize()],
                ["Pressure Score", f"{a['pressure_score']:,.2f}" if a["pressure_score"] is not None else "N/A"],
                ["Volume Ratio", f"{a['volume_ratio']:,.2f}x" if a["volume_ratio"] is not None else "N/A"],
                ["Volume Anomaly", "Yes" if a["volume_anomaly"] else "No"],
                ["Daily Return %", f"{a['daily_return_pct']:,.4f}%" if a["daily_return_pct"] is not None else "N/A"],
            ]
            tbl = Table(analysis_rows, colWidths=[8 * cm, 8 * cm], repeatRows=1)
            tbl.setStyle(_pdf_table_style())
            story.append(tbl)
            story.append(Spacer(1, 0.4 * cm))

        # ── News Summary ──────────────────────────────────────────────
        if data["news"]:
            n = data["news"]
            story.append(Paragraph("NEWS SUMMARY", styles["SectionHeading"]))
            news_rows = [
                ["Metric", "Value"],
                ["Total Articles", str(n["total"])],
                ["Positive Sentiment", str(n["positive"])],
                ["Neutral Sentiment", str(n["neutral"])],
                ["Negative Sentiment", str(n["negative"])],
            ]
            if n["total"] > 0:
                news_rows.append([
                    "Positive %",
                    f"{n['positive'] / n['total'] * 100:.1f}%",
                ])
                news_rows.append([
                    "Negative %",
                    f"{n['negative'] / n['total'] * 100:.1f}%",
                ])
            tbl = Table(news_rows, colWidths=[8 * cm, 8 * cm], repeatRows=1)
            tbl.setStyle(_pdf_table_style())
            story.append(tbl)
            story.append(Spacer(1, 0.4 * cm))

        # ── Floorsheet Summary ────────────────────────────────────────
        if data["floorsheet"]:
            f = data["floorsheet"]
            story.append(Paragraph("FLOORSHEET SUMMARY", styles["SectionHeading"]))
            fs_rows = [
                ["Metric", "Value"],
                ["Total Transactions", f"{f['total_transactions']:,}"],
                ["Total Quantity", f"{f['total_quantity']:,}"],
                ["Total Amount", f"{f['total_amount']:,.2f}"],
                ["Average Rate", f"{f['avg_rate']:,.2f}"],
            ]
            tbl = Table(fs_rows, colWidths=[8 * cm, 8 * cm], repeatRows=1)
            tbl.setStyle(_pdf_table_style())
            story.append(tbl)

        doc.build(story)
        buf.seek(0)
        return _pdf_response(buf, fname)

    # ------------------------------------------------------------------
    # XLSX REPORT
    # ------------------------------------------------------------------

    def _build_xlsx(self, data, fname, companies, date_from, date_to):
        wb = openpyxl.Workbook()
        wb.remove(wb.active)  # remove default blank sheet

        header_fill, header_font, header_align = _xlsx_header_style()

        def _add_summary_sheet(title, rows_data):
            ws = wb.create_sheet(title=title)
            _apply_xlsx_header(ws, ["Metric", "Value"])
            for row in rows_data:
                ws.append(row)
            _autofit_xlsx(ws)
            return ws

        # Cover sheet
        ws_cover = wb.create_sheet(title="Report Info")
        ws_cover.append(["STOCK MARKET ANALYSIS REPORT"])
        ws_cover["A1"].font = Font(bold=True, size=14, color="1F3864")
        ws_cover.append([])
        ws_cover.append(["Company", ", ".join(c.symbol for c in companies) if companies else "All Companies"])
        if companies:
            ws_cover.append(["Company Names", ", ".join(c.name for c in companies)])
            ws_cover.append(["Sectors", ", ".join({c.sector for c in companies})])
        ws_cover.append(["Period From", str(date_from) if date_from else "—"])
        ws_cover.append(["Period To", str(date_to) if date_to else "—"])
        ws_cover.append(["Generated", datetime.now().strftime("%Y-%m-%d %H:%M")])
        ws_cover.column_dimensions["A"].width = 20
        ws_cover.column_dimensions["B"].width = 30

        # Trading sheet
        if data["trading"]:
            t = data["trading"]
            _add_summary_sheet("Trading Summary", [
                ["Trading Days", t["trading_days"]],
                ["Opening Price", t["open_price"]],
                ["Closing Price (latest)", t["close_price"]],
                ["Period High", t["high"]],
                ["Period Low", t["low"]],
                ["Total Volume", t["total_volume"]],
                ["Total Turnover", t["total_turnover"]],
            ])

        # Analysis sheet
        if data["analysis"]:
            a = data["analysis"]
            _add_summary_sheet("Analysis", [
                ["Latest Date", a["latest_date"]],
                ["Daily VWAP", a["vwap"]],
                ["30-Day VWAP", a["vwap_30d"]],
                ["Market Pressure", a["pressure"]],
                ["Pressure Score", a["pressure_score"]],
                ["Volume Ratio", a["volume_ratio"]],
                ["Volume Anomaly", "Yes" if a["volume_anomaly"] else "No"],
                ["Daily Return %", a["daily_return_pct"]],
            ])

        # News sheet
        if data["news"]:
            n = data["news"]
            rows = [
                ["Total Articles", n["total"]],
                ["Positive", n["positive"]],
                ["Neutral", n["neutral"]],
                ["Negative", n["negative"]],
            ]
            if n["total"] > 0:
                rows.append(["Positive %", round(n["positive"] / n["total"] * 100, 1)])
                rows.append(["Negative %", round(n["negative"] / n["total"] * 100, 1)])
            _add_summary_sheet("News Summary", rows)

        # Floorsheet sheet
        if data["floorsheet"]:
            f = data["floorsheet"]
            _add_summary_sheet("Floorsheet Summary", [
                ["Total Transactions", f["total_transactions"]],
                ["Total Quantity", f["total_quantity"]],
                ["Total Amount", f["total_amount"]],
                ["Average Rate", f["avg_rate"]],
            ])

        return _xlsx_response(wb, fname)
