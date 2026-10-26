from rest_framework.response import Response
from rest_framework.views import APIView

from apps.market_data.api.serializers import DailyPriceSerializers
from apps.market_data.models import DailyPrice
from apps.market_data.services.price_source import requested_price_source
from apps.users.company_access import filter_company_queryset, require_company_access
from apps.users.permissions import HasAppPermission


class CompanyPriceList(APIView):
    permission_classes = [HasAppPermission]
    permission_key = "view_price_history"

    def get(self, request):
        prices = DailyPrice.objects.filter(
            company__is_active=True, source=requested_price_source(request)
        ).select_related("company")

        prices = filter_company_queryset(prices, request.user)

        company_id = request.query_params.get("company_id")
        if company_id:
            require_company_access(request.user, company_id)
            prices = prices.filter(company_id=company_id)

        serializer = DailyPriceSerializers(prices[:500], many=True)
        return Response(serializer.data)
