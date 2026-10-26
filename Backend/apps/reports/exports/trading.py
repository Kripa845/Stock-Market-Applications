"""
GET export/trading/ -- daily prices as CSV, XLSX or PDF.
"""

import csv
import io
from datetime import datetime

from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.market_data.models import DailyPrice
from apps.users.permissions import HasAppPermission
from apps.reports.exports.common import (
    Alignment,
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

        qs = DailyPrice.objects.filter(source="crawled").select_related("company").order_by("-date", "company__symbol")

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
