from datetime import date
from apps.api_schema import document_api_view

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.comparison.services.compare import ComparisonError, compare_companies, parse_symbols
from apps.comparison.services.coverage import coverage_report
from apps.market_data.services.market_stats import tracked_companies
from apps.users.company_access import filter_company_queryset, get_accessible_company_ids, has_company_access
from apps.users.permissions import HasAppPermission


def _error(exc, status=400):
    return Response({"detail": exc.message, "code": exc.code, **exc.details}, status=status)


@document_api_view('Company comparison')
class CompareAPIView(APIView):
    """GET /api/compare/?symbols=ADBL,CHCL[&date=YYYY-MM-DD for the broker tables]"""

    permission_classes = [HasAppPermission]
    permission_key = "view_analysis"

    permission_keys = ['view_analysis', 'view_stock_comparison']
    def get(self, request):
        try:
            companies = parse_symbols(request.query_params.get("symbols"))
        except ComparisonError as exc:
            return _error(exc)
        denied = [c.symbol for c in companies if not has_company_access(request.user, c.pk)]
        if denied:
            return Response({"detail": f"You do not have access to: {', '.join(denied)}.",
                             "code": "company_access_denied", "denied_symbols": denied}, status=403)

        broker_date = None
        if request.query_params.get("date"):
            try:
                broker_date = date.fromisoformat(request.query_params["date"])
            except ValueError:
                return Response({"detail": "date must be YYYY-MM-DD.", "code": "invalid_date"}, status=400)
        return Response({
            "results": compare_companies(companies, broker_date=broker_date),
            "universe_label": "tracked companies",
        })


@document_api_view('Company comparison')
class CompareCompaniesAPIView(APIView):
    """GET /api/compare/companies/[?sector=Hydropower] -- the picker list."""

    permission_classes = [HasAppPermission]
    permission_key = "view_analysis"

    permission_keys = ['view_analysis', 'view_stock_comparison']
    def get(self, request):
        companies = filter_company_queryset(tracked_companies(), request.user, "id").order_by("symbol")
        sectors = sorted(set(companies.values_list("sector", flat=True)))
        sector = (request.query_params.get("sector") or "").strip()
        if sector:
            companies = companies.filter(sector__iexact=sector)
        return Response({
            "results": list(companies.values("symbol", "name", "sector")),
            "sectors": sectors,
        })


@document_api_view('Company comparison')
class CompareCoverageAPIView(APIView):
    """GET /api/compare/coverage/ -- what each accessible tracked company is missing."""

    permission_classes = [HasAppPermission]
    permission_key = "view_analysis"

    permission_keys = ['view_analysis', 'view_stock_comparison']
    def get(self, request):
        return Response(coverage_report(company_ids=get_accessible_company_ids(request.user)))
