"""
GET export/news/ -- news articles as CSV, XLSX or PDF.
"""

import csv
import io
from datetime import datetime

from django.db.models import Prefetch
from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.news.models import ArticleCompanyTag, NewsArticle
from apps.news.selectors import real_articles
from apps.users.permissions import HasAppPermission
from apps.reports.exports.common import (
    _apply_xlsx_header,
    _autofit_xlsx,
    _bad_request,
    cm,
    ExportContentNegotiation,
    _filename,
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
    _xlsx_response,
)


# ============================================================
# NEWS EXPORT
# ============================================================

class ExportNewsAPIView(APIView):
    """
    GET /api/reports/export/news/

    Query params
    ------------
    format      csv | xlsx | pdf  (default: csv)
    company_id  integer           (optional)
    date_from   YYYY-MM-DD        (optional)
    date_to     YYYY-MM-DD        (optional)
    sentiment   positive | negative | neutral  (optional)

    Permission: export_reports
    """
    permission_classes = [HasAppPermission]
    permission_key = "export_reports"
    content_negotiation_class = ExportContentNegotiation

    # Maximum rows streamed to prevent memory issues on large datasets.
    MAX_ROWS = 5_000

    def get(self, request):
        # ── parse params ──────────────────────────────────────────────
        fmt = request.query_params.get("format", "csv").lower()
        company_id_strs = request.query_params.getlist("company_id")
        date_from_str = request.query_params.get("date_from", "")
        date_to_str = request.query_params.get("date_to", "")
        sentiment_filter = request.query_params.get("sentiment", "").lower()

        # ── validate ──────────────────────────────────────────────────
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

        if fmt not in ("csv", "xlsx", "pdf"):
            return _bad_request("format must be csv, xlsx, or pdf.")

        # ── build queryset ────────────────────────────────────────────
        qs = (
            real_articles(NewsArticle.objects.all())
            .prefetch_related(Prefetch(
                "company_tags",
                queryset=ArticleCompanyTag.objects.filter(
                    company__in=companies
                ).select_related("company"),
            ))
            .order_by("-published_at")
        )

        qs = qs.filter(company_tags__company__in=companies).distinct()

        if date_from:
            qs = qs.filter(published_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(published_at__date__lte=date_to)

        if sentiment_filter in ("positive", "negative", "neutral"):
            qs = qs.filter(sentiment_label__iexact=sentiment_filter)

        qs = qs[: self.MAX_ROWS]

        # ── empty result ──────────────────────────────────────────────
        if not qs.exists():
            return Response(
                {"message": "No data found for the selected filters."},
                status=status.HTTP_204_NO_CONTENT,
            )

        # ── build row data ────────────────────────────────────────────
        HEADERS = [
            "ID", "Headline", "Source", "URL",
            "Published At", "Sentiment", "Tagged Companies",
        ]

        def _row(article):
            tags = ", ".join(
                t.company.symbol
                for t in article.company_tags.all()
            )
            return [
                article.id,
                article.headline,
                article.source,
                article.url,
                str(article.published_at)[:19] if article.published_at else "",
                article.sentiment_label or "",
                tags,
            ]

        rows = [_row(a) for a in qs]
        fname = _filename("news_export", companies, date_from, date_to, fmt)

        # ── CSV ───────────────────────────────────────────────────────
        if fmt == "csv":
            response = HttpResponse(content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = f'attachment; filename="{fname}"'
            response.write("\ufeff")  # BOM for Excel compatibility
            writer = csv.writer(response)
            writer.writerow(HEADERS)
            writer.writerows(rows)
            return response

        # ── XLSX ──────────────────────────────────────────────────────
        if fmt == "xlsx":
            if not OPENPYXL_AVAILABLE:
                return _bad_request("XLSX export requires openpyxl. Contact your administrator.")
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "News"
            _apply_xlsx_header(ws, HEADERS)
            for row in rows:
                ws.append(row)
            _autofit_xlsx(ws)
            ws.freeze_panes = "A2"
            return _xlsx_response(wb, fname)

        # ── PDF ───────────────────────────────────────────────────────
        if fmt == "pdf":
            if not REPORTLAB_AVAILABLE:
                return _bad_request("PDF export requires reportlab. Contact your administrator.")
            buf = io.BytesIO()
            doc = _pdf_doc(buf, "News Export")
            styles = _pdf_styles()
            story = []

            # Title block
            title_txt = "News Export"
            if companies:
                title_txt += f" — {', '.join(c.symbol for c in companies)}"
            story.append(Paragraph(title_txt, styles["ReportTitle"]))

            # Metadata
            meta_lines = []
            if date_from or date_to:
                meta_lines.append(f"Period: {date_from or '—'} to {date_to or '—'}")
            if sentiment_filter:
                meta_lines.append(f"Sentiment filter: {sentiment_filter}")
            meta_lines.append(f"Total articles: {len(rows)}")
            meta_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            for line in meta_lines:
                story.append(Paragraph(line, styles["BodySmall"]))
            story.append(Spacer(1, 0.4 * cm))

            # Table (truncate headline/URL so the PDF stays readable)
            PDF_HEADERS = ["ID", "Headline", "Source", "Published At", "Sentiment", "Companies"]
            table_data = [PDF_HEADERS]
            for r in rows:
                headline = str(r[1])[:80] + ("…" if len(str(r[1])) > 80 else "")
                table_data.append([
                    str(r[0]),
                    headline,
                    str(r[2])[:20],
                    str(r[4])[:16],
                    str(r[5]),
                    str(r[6])[:30],
                ])

            col_widths = [1.2 * cm, 7.5 * cm, 2.5 * cm, 2.8 * cm, 2.0 * cm, 3.0 * cm]
            tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
            tbl.setStyle(_pdf_table_style())
            story.append(tbl)

            doc.build(story)
            buf.seek(0)
            return _pdf_response(buf, fname)
