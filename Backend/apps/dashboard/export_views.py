"""
Export Data / Reports
=====================

Permission gate: ``export_reports``  (existing key — wired through the
existing dynamic role/permission system; no role name is hard-coded here).

Two-level authorisation on every request
-----------------------------------------
1. HasAppPermission checks ``export_reports`` via the existing
   ``user.has_app_permission()`` mechanism.
2. Every endpoint that accepts ``company_id`` validates that the company
   exists and is active before touching any data.

Supported exports
-----------------
GET /api/reports/export/news/        → CSV | XLSX | PDF
GET /api/reports/export/trading/     → CSV | XLSX | PDF
GET /api/reports/export/floorsheet/  → CSV | XLSX
GET /api/reports/export/report/      → PDF  (combined analysis report)
GET /api/reports/export/companies/   → JSON list of all active companies
                                        (used to populate the frontend dropdown)

Common query parameters
-----------------------
format      csv | xlsx | pdf   (default: csv)
company_id  integer             (optional — filter to one company)
date_from   YYYY-MM-DD          (optional)
date_to     YYYY-MM-DD          (optional)
sentiment   positive|negative|neutral  (news only)
"""

import csv
import io
import logging
from datetime import date, datetime

from django.db.models import Avg, Count, Max, Min, Q, Sum, Prefetch
from django.http import HttpResponse
from django.utils import timezone

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.negotiation import DefaultContentNegotiation

from apps.companies.models import Company
from apps.market_data.models import DailyPrice, FloorsheetTransaction
from apps.news.models import ArticleCompanyTag, NewsArticle
from apps.analysis.models import DailyAnalysis
from apps.analysis.services.brokers import build_broker_activity, sampled_floorsheet_dates
from apps.users.permissions import HasAppPermission
from apps.users.company_access import get_accessible_company_ids

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional heavy-import guard — openpyxl / reportlab are added to
# requirements.txt; these guards give a readable error if somehow missing.
# ---------------------------------------------------------------------------
try:
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    OPENPYXL_AVAILABLE = True
except ImportError:  # pragma: no cover
    OPENPYXL_AVAILABLE = False

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
    REPORTLAB_AVAILABLE = True
except ImportError:  # pragma: no cover
    REPORTLAB_AVAILABLE = False


# ============================================================
# SHARED HELPERS
# ============================================================

def _bad_request(msg: str):
    return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)


def _forbidden(msg: str):
    return Response({"detail": msg}, status=status.HTTP_403_FORBIDDEN)


def _resolve_companies(company_id_strs, user):
    """
    Validate and return a list of Company instances.
    Returns (companies_list, error_response_or_None).

    If company_id_strs is empty/None  → ([], None) — no filter requested
    If any company is not found/inactive → (None, 400 response)
    If all valid                          → (companies, None)
    """
    if not company_id_strs:
        accessible_ids = get_accessible_company_ids(user)
        qs = Company.objects.filter(is_active=True)
        if accessible_ids is not None:
            qs = qs.filter(pk__in=accessible_ids)
        return list(qs.order_by("symbol")), None
    company_ids = []
    for s in company_id_strs:
        if not s:
            continue
        try:
            company_ids.append(int(s))
        except (ValueError, TypeError):
            return None, _bad_request("company_id must be an integer.")
    try:
        companies = list(
            Company.objects.filter(pk__in=company_ids, is_active=True).order_by("symbol")
        )
    except Exception:
        return None, _bad_request("Invalid company IDs.")
    found_ids = {c.id for c in companies}
    accessible_ids = get_accessible_company_ids(user)
    if accessible_ids is not None:
        denied = [cid for cid in company_ids if cid not in set(accessible_ids)]
        if denied:
            return None, _forbidden("You do not have access to one or more requested companies.")
    for cid in company_ids:
        if cid not in found_ids:
            return None, _bad_request(
                f"Company with id={cid} does not exist or is not active."
            )
    return companies, None


def _parse_date(value: str, field_name: str):
    """Parse YYYY-MM-DD string. Returns (date_obj, error_response)."""
    if not value:
        return None, None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date(), None
    except ValueError:
        return None, _bad_request(
            f"Invalid {field_name} format. Use YYYY-MM-DD."
        )


def _validate_date_range(date_from, date_to):
    """Returns error response if date_from > date_to, else None."""
    if date_from and date_to and date_from > date_to:
        return _bad_request("date_from must not be after date_to.")
    return None


def _filename(prefix, companies, date_from, date_to, ext):
    """Build a clean download filename."""
    parts = [prefix]
    if companies:
        parts.append("_".join(c.symbol for c in companies))
    if date_from:
        parts.append(str(date_from))
    if date_to:
        parts.append(f"to_{date_to}")
    return "_".join(parts) + "." + ext


# ============================================================
# XLSX HELPERS
# ============================================================

def _xlsx_header_style():
    """Bold white text on dark blue background."""
    fill = PatternFill("solid", fgColor="1F3864")
    font = Font(bold=True, color="FFFFFF")
    alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    return fill, font, alignment


def _apply_xlsx_header(ws, headers: list[str], row: int = 1):
    fill, font, alignment = _xlsx_header_style()
    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=row, column=col_idx, value=header)
        cell.fill = fill
        cell.font = font
        cell.alignment = alignment
    ws.row_dimensions[row].height = 18


def _autofit_xlsx(ws):
    for col_cells in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col_cells[0].column)
        for cell in col_cells:
            if cell.value:
                max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[col_letter].width = min(max_len + 4, 40)


def _xlsx_response(wb, filename: str) -> HttpResponse:
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    response = HttpResponse(
        buf.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


# ============================================================
# PDF HELPERS
# ============================================================

def _pdf_doc(buf, title: str):
    """Return a SimpleDocTemplate bound to an in-memory buffer."""
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=title,
    )
    return doc


def _pdf_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ReportTitle",
        fontSize=16,
        fontName="Helvetica-Bold",
        spaceAfter=6,
        textColor=colors.HexColor("#1F3864"),
    ))
    styles.add(ParagraphStyle(
        name="SectionHeading",
        fontSize=12,
        fontName="Helvetica-Bold",
        spaceBefore=12,
        spaceAfter=4,
        textColor=colors.HexColor("#1F3864"),
    ))
    styles.add(ParagraphStyle(
        name="SubHeading",
        fontSize=10,
        fontName="Helvetica-Bold",
        spaceBefore=8,
        spaceAfter=2,
        textColor=colors.HexColor("#374151"),
    ))
    styles.add(ParagraphStyle(
        name="BodySmall",
        fontSize=9,
        fontName="Helvetica",
        spaceAfter=2,
    ))
    return styles


def _pdf_table_style(header_rows: int = 1):
    header_bg = colors.HexColor("#1F3864")
    alt_row_bg = colors.HexColor("#F3F4F6")
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, header_rows - 1), header_bg),
        ("TEXTCOLOR", (0, 0), (-1, header_rows - 1), colors.white),
        ("FONTNAME", (0, 0), (-1, header_rows - 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, header_rows - 1), 8),
        ("ALIGN", (0, 0), (-1, header_rows - 1), "CENTER"),
        ("ROWBACKGROUNDS", (0, header_rows), (-1, -1), [colors.white, alt_row_bg]),
        ("FONTNAME", (0, header_rows), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, header_rows), (-1, -1), 7.5),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ])


def _pdf_response(buf, filename: str) -> HttpResponse:
    response = HttpResponse(buf.read(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


# ============================================================
# COMPANIES LIST (for frontend dropdown)
# ============================================================

class ExportContentNegotiation(DefaultContentNegotiation):
    """Treat the export ``format`` query parameter as file format, not renderer."""

    def select_renderer(self, request, renderers, format_suffix=None):
        django_request = request._request
        original_query = django_request.GET
        if "format" not in original_query:
            return super().select_renderer(request, renderers, format_suffix)

        django_request.GET = original_query.copy()
        django_request.GET.pop("format", None)
        try:
            return super().select_renderer(request, renderers, format_suffix)
        finally:
            django_request.GET = original_query


class ExportCompanyListAPIView(APIView):
    """
    GET /api/reports/export/companies/

    Returns the list of all active companies — used by the frontend to
    populate the company selector in the Export UI.

    Permission: export_reports
    """
    permission_classes = [HasAppPermission]
    permission_key = "export_reports"

    def get(self, request):
        companies = (
            Company.objects
            .filter(is_active=True)
            .order_by("symbol")
            .values("id", "symbol", "name", "sector")
        )
        accessible_ids = get_accessible_company_ids(request.user)
        if accessible_ids is not None:
            companies = companies.filter(pk__in=accessible_ids)
        return Response(list(companies))


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
            NewsArticle.objects
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


# ============================================================
# TRADING (DAILY PRICE) EXPORT
# ============================================================

class ExportTradingAPIView(APIView):
    """
    GET /api/reports/export/trading/

    Query params
    ------------
    format      csv | xlsx | pdf  (default: csv)
    company_id  integer           (optional)
    date_from   YYYY-MM-DD        (optional)
    date_to     YYYY-MM-DD        (optional)

    Permission: export_reports
    """
    permission_classes = [HasAppPermission]
    permission_key = "export_reports"
    content_negotiation_class = ExportContentNegotiation

    MAX_ROWS = 10_000

    def get(self, request):
        fmt = request.query_params.get("format", "csv").lower()
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

        if fmt not in ("csv", "xlsx", "pdf"):
            return _bad_request("format must be csv, xlsx, or pdf.")

        qs = DailyPrice.objects.select_related("company").order_by("-date", "company__symbol")

        qs = qs.filter(company__in=companies)
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)

        qs = qs[: self.MAX_ROWS]

        if not qs.exists():
            return Response(
                {"message": "No data found for the selected filters."},
                status=status.HTTP_204_NO_CONTENT,
            )

        HEADERS = ["Symbol", "Company Name", "Date", "Open", "High", "Low", "Close", "Volume", "Turnover"]

        def _row(p):
            return [
                p.company.symbol,
                p.company.name,
                str(p.date),
                float(p.open),
                float(p.high),
                float(p.low),
                float(p.close),
                int(p.volume),
                float(p.turnover),
            ]

        rows = [_row(p) for p in qs]
        fname = _filename("trading_export", companies, date_from, date_to, fmt)

        if fmt == "csv":
            response = HttpResponse(content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = f'attachment; filename="{fname}"'
            response.write("\ufeff")
            writer = csv.writer(response)
            writer.writerow(HEADERS)
            writer.writerows(rows)
            return response

        if fmt == "xlsx":
            if not OPENPYXL_AVAILABLE:
                return _bad_request("XLSX export requires openpyxl.")
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Trading Data"
            _apply_xlsx_header(ws, HEADERS)
            for row in rows:
                ws.append(row)
            # Format numeric columns
            for row_cells in ws.iter_rows(min_row=2):
                for cell in row_cells[3:]:  # Open, High, Low, Close, Volume, Turnover
                    cell.alignment = Alignment(horizontal="right")
            _autofit_xlsx(ws)
            ws.freeze_panes = "A2"
            return _xlsx_response(wb, fname)

        if fmt == "pdf":
            if not REPORTLAB_AVAILABLE:
                return _bad_request("PDF export requires reportlab.")
            buf = io.BytesIO()
            doc = _pdf_doc(buf, "Trading Data Export")
            styles = _pdf_styles()
            story = []

            title_txt = "Trading Data Export"
            if companies:
                title_txt += f" — {', '.join(c.symbol for c in companies)}"
            story.append(Paragraph(title_txt, styles["ReportTitle"]))

            meta_lines = []
            if date_from or date_to:
                meta_lines.append(f"Period: {date_from or '—'} to {date_to or '—'}")
            meta_lines.append(f"Total records: {len(rows)}")
            meta_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            for line in meta_lines:
                story.append(Paragraph(line, styles["BodySmall"]))
            story.append(Spacer(1, 0.4 * cm))

            table_data = [HEADERS]
            for r in rows:
                table_data.append([
                    r[0], r[1][:25], r[2],
                    f"{r[3]:,.2f}", f"{r[4]:,.2f}", f"{r[5]:,.2f}", f"{r[6]:,.2f}",
                    f"{r[7]:,}", f"{r[8]:,.2f}",
                ])

            col_widths = [1.5*cm, 4*cm, 2.2*cm, 1.8*cm, 1.8*cm, 1.8*cm, 1.8*cm, 2.2*cm, 2.9*cm]
            tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
            tbl.setStyle(_pdf_table_style())
            story.append(tbl)
            doc.build(story)
            buf.seek(0)
            return _pdf_response(buf, fname)


# ============================================================
# FLOORSHEET EXPORT
# ============================================================

class ExportBrokerActivityAPIView(APIView):
    """Export aggregated broker activity from sampled floorsheet rows."""

    permission_classes = [HasAppPermission]
    permission_key = "export_reports"
    content_negotiation_class = ExportContentNegotiation

    def get(self, request):
        fmt = request.query_params.get("format", "csv").lower()
        company_ids = request.query_params.getlist("company_id")
        companies, err = _resolve_companies(company_ids, request.user)
        if err:
            return err
        date_from, err = _parse_date(request.query_params.get("date_from", ""), "date_from")
        if err:
            return err
        date_to, err = _parse_date(request.query_params.get("date_to", ""), "date_to")
        if err:
            return err
        range_err = _validate_date_range(date_from, date_to)
        if range_err:
            return range_err
        if fmt not in ("csv", "xlsx"):
            return _bad_request("Broker activity export supports csv and xlsx only.")

        company_scope = [company.pk for company in companies]
        activity = build_broker_activity(
            company_ids=company_scope,
            start_date=date_from,
            end_date=date_to,
        )
        sampled_dates = sampled_floorsheet_dates(
            company_ids=company_scope,
            start_date=date_from,
            end_date=date_to,
        )
        if not activity["brokers"]:
            return Response(
                {"message": "No floorsheet activity found for the selected filters."},
                status=status.HTTP_204_NO_CONTENT,
            )

        period_start = date_from or (min(sampled_dates) if sampled_dates else "")
        period_end = date_to or (max(sampled_dates) if sampled_dates else "")
        sampled_text = ", ".join(str(day) for day in sampled_dates)
        headers = [
            "Sampled Period Start", "Sampled Period End", "Sampled Trading Sessions",
            "Broker", "Broker-side Buy Qty", "Broker-side Sell Qty",
            "Net Buy/Sell Qty", "Total Activity", "Trades",
        ]
        rows = [[
            str(period_start), str(period_end), sampled_text, row["broker"],
            row["buy_quantity"], row["sell_quantity"], row["net_quantity"],
            row["total_quantity"], row["trades"],
        ] for row in activity["brokers"]]
        fname = _filename("broker_activity_export", companies, date_from, date_to, fmt)

        if fmt == "csv":
            response = HttpResponse(content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = f'attachment; filename="{fname}"'
            response.write("\ufeff")
            writer = csv.writer(response)
            writer.writerow(headers)
            writer.writerows(rows)
            return response

        if not OPENPYXL_AVAILABLE:
            return _bad_request("XLSX export requires openpyxl.")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Broker Activity"
        _apply_xlsx_header(ws, headers)
        for row in rows:
            ws.append(row)
        _autofit_xlsx(ws)
        ws.freeze_panes = "A2"
        return _xlsx_response(wb, fname)


class ExportFloorsheetAPIView(APIView):
    """
    GET /api/reports/export/floorsheet/

    Query params
    ------------
    format      csv | xlsx  (default: csv; PDF not offered — too many rows)
    company_id  integer      (optional)
    date_from   YYYY-MM-DD   (optional)
    date_to     YYYY-MM-DD   (optional)

    Permission: export_reports
    """
    permission_classes = [HasAppPermission]
    permission_key = "export_reports"
    content_negotiation_class = ExportContentNegotiation

    MAX_ROWS = 20_000

    def get(self, request):
        fmt = request.query_params.get("format", "csv").lower()
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

        if fmt not in ("csv", "xlsx"):
            return _bad_request("Floorsheet export supports csv and xlsx only.")

        qs = (
            FloorsheetTransaction.objects
            .select_related("company")
            .order_by("-date", "-id")
        )

        qs = qs.filter(company__in=companies)
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)

        qs = qs[: self.MAX_ROWS]

        if not qs.exists():
            return Response(
                {"message": "No data found for the selected filters."},
                status=status.HTTP_204_NO_CONTENT,
            )

        HEADERS = [
            "Symbol", "Date", "Transaction ID",
            "Buyer Broker", "Seller Broker",
            "Quantity", "Rate", "Amount",
        ]

        def _row(f):
            return [
                f.company.symbol,
                str(f.date),
                f.transaction_id,
                f.buyer_broker,
                f.seller_broker,
                int(f.quantity),
                float(f.rate),
                float(f.amount) if f.amount is not None else "",
            ]

        rows = [_row(f) for f in qs]
        fname = _filename("floorsheet_export", companies, date_from, date_to, fmt)

        if fmt == "csv":
            response = HttpResponse(content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = f'attachment; filename="{fname}"'
            response.write("\ufeff")
            writer = csv.writer(response)
            writer.writerow(HEADERS)
            writer.writerows(rows)
            return response

        if fmt == "xlsx":
            if not OPENPYXL_AVAILABLE:
                return _bad_request("XLSX export requires openpyxl.")
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Floorsheet"
            _apply_xlsx_header(ws, HEADERS)
            for row in rows:
                ws.append(row)
            _autofit_xlsx(ws)
            ws.freeze_panes = "A2"
            return _xlsx_response(wb, fname)


# ============================================================
# COMBINED ANALYSIS REPORT (PDF + XLSX)
# ============================================================

class ExportReportAPIView(APIView):
    """
    GET /api/reports/export/report/

    Generates a combined analysis report for a company over a date range.
    Includes: trading summary, news summary, sentiment distribution,
    floorsheet summary, and analysis metrics.

    Query params
    ------------
    format      pdf | xlsx  (default: pdf)
    company_id  integer     (required for a meaningful report;
                             optional — if omitted a market-wide summary
                             is generated)
    date_from   YYYY-MM-DD  (optional)
    date_to     YYYY-MM-DD  (optional)

    Permission: export_reports
    """
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
        price_qs = DailyPrice.objects.select_related("company")
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
        news_qs = NewsArticle.objects.all()
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
        analysis_qs = DailyAnalysis.objects.all()
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
