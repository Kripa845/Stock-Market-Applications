"""
GET export/companies/ -- the company dropdown on the Export page.
"""

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.companies.models import Company
from apps.users.company_access import get_accessible_company_ids
from apps.users.permissions import HasAppPermission


# ============================================================
# COMPANIES LIST (for frontend dropdown)
# ============================================================

class ExportCompanyListAPIView(APIView):
    
    permission_classes = [HasAppPermission]
    permission_key = "view_reports"

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
