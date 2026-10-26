"""
GET export/brokers/ and export/floorsheet/ -- broker activity and raw trades.
"""

import csv

from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analysis.services.brokers import build_broker_activity, sampled_floorsheet_dates
from apps.floorsheet.models import FloorsheetTransaction
from apps.users.permissions import HasAppPermission
from apps.reports.exports.common import (
    _apply_xlsx_header,
    _autofit_xlsx,
    _bad_request,
    ExportContentNegotiation,
    _filename,
    openpyxl,
    OPENPYXL_AVAILABLE,
    _parse_date,
    _resolve_companies,
    _validate_date_range,
    _xlsx_response,
)


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
