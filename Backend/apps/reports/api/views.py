"""
/api/market/dividends/ and /api/market/quarterly-report/ -- tracked-company fundamentals.
Not narrowed to the caller's companies.
"""

import hashlib
import re

from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.reports.models import DividendAnnouncement
from apps.reports.services import dividends, quarterly_reports
from apps.users.permissions import HasAppPermission

CACHE_SECONDS = 60


class DividendListAPIView(APIView):
    """
    GET /api/market/dividends/?fiscal_year=2082/2083|all&status=proposed

    Rows for every tracked company crawled from ShareSansar (see services.dividends); not
    narrowed to the caller's companies.
    No fiscal_year -> the latest crawled one.  Rows with no fiscal year are always included
    (``flags`` marks them).  Cached for 60 seconds per query.
    """
    permission_classes = [HasAppPermission]
    permission_key = "view_market_data"

    def get(self, request):
        status_filter = request.query_params.get("status", "").strip()
        if status_filter and status_filter not in DividendAnnouncement.Status.values:
            return Response({"detail": f"status must be one of {DividendAnnouncement.Status.values}."},
                            status=status.HTTP_400_BAD_REQUEST)
        requested = request.query_params.get("fiscal_year", "").strip()
        key = "market-api:dividends:" + hashlib.sha256(f"{requested}|{status_filter}".encode()).hexdigest()
        payload = cache.get(key)
        if payload is None:
            years = dividends.fiscal_years()
            fiscal_year = None if requested == "all" else (requested or (years[0] if years else None))
            payload = {
                "scope": "tracked_companies",
                "units": dividends.UNITS,
                "fiscal_year": fiscal_year or "all",
                "fiscal_years": years,
                "statuses": [{"value": value, "label": label} for value, label in DividendAnnouncement.Status.choices],
                "status_note": dividends.STATUS_NOTE,
                **dividends.last_updated(),
                "rows": dividends.dividend_rows(fiscal_year, status_filter or None),
            }
            cache.set(key, payload, CACHE_SECONDS)
        return Response(payload)


FISCAL_YEAR_PARAM = re.compile(r"^\d{4}/(\d{2}|\d{4})$")


def _quarterly_params(request, *, period=True):
    """(sector_code, fiscal_year, quarter, error_response) from the query string."""
    def bad(detail):
        return None, None, None, Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)

    sector = request.query_params.get("sector", "").strip().upper()
    if sector not in quarterly_reports.SECTORS:
        return bad(f"sector must be one of {sorted(quarterly_reports.SECTORS)}.")
    if not period:
        return sector, None, None, None

    raw_year = request.query_params.get("fiscal_year", "").strip()
    fiscal_year = None
    if raw_year:
        fiscal_year = dividends.normalise_fiscal_year(raw_year) if FISCAL_YEAR_PARAM.match(raw_year) else ""
        if not fiscal_year:
            return bad("fiscal_year must look like 2082/83 or 2082/2083.")

    raw_quarter = request.query_params.get("quarter", "").strip()
    quarter = None
    if raw_quarter:
        if raw_quarter not in ("1", "2", "3", "4"):
            return bad("quarter must be 1, 2, 3 or 4.")
        quarter = int(raw_quarter)
    return sector, fiscal_year, quarter, None


class QuarterlyReportAPIView(APIView):
    """
    GET /api/market/quarterly-report/?sector=BANKING&fiscal_year=2082/83&quarter=4

    The tracked companies of one sector that filed that quarter, with PE / PB / yields / YoY
    calculated on the latest crawled close (services.quarterly_reports).  A missing
    fiscal_year / quarter means the latest one filed in the sector.  Not narrowed to the
    caller's companies, like the dividends list.  Null values are "not meaningful".
    """
    permission_classes = [HasAppPermission]
    permission_key = "view_market_data"

    def get(self, request):
        sector, fiscal_year, quarter, error = _quarterly_params(request)
        if error:
            return error
        return Response(quarterly_reports.quarterly_report(sector, fiscal_year, quarter))


class QuarterlyReportPeriodsAPIView(APIView):
    """GET /api/market/quarterly-report/periods/?sector=BANKING -> fiscal years and quarters filed, newest first."""
    permission_classes = [HasAppPermission]
    permission_key = "view_market_data"

    def get(self, request):
        sector, _, _, error = _quarterly_params(request, period=False)
        if error:
            return error
        return Response({"sector": sector, "periods": quarterly_reports.periods(sector)})
