"""
/api/market-calendar/ -- BS month calendar of NEPSE sessions and corporate-action events.

The index is whole-market; events cover the tracked companies the user may access
(services.calendar).
"""

from datetime import date

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.market_calendar.services import calendar, weekday_summary
from apps.market_calendar.services.market_day import market_day
from apps.users.company_access import get_accessible_company_ids
from apps.users.permissions import HasAppPermission


class _CalendarView(APIView):
    permission_classes = [HasAppPermission]
    permission_key = "view_market_data"

    def build(self, request):
        raise NotImplementedError

    def get(self, request):
        try:
            return Response(self.build(request))
        except calendar.CalendarError as exc:
            return Response({"detail": str(exc)}, status=400)
        except calendar.IndexNotFound as exc:
            return Response({"detail": str(exc)}, status=404)


class CalendarMonthAPIView(_CalendarView):
    """?bs_year=2083&bs_month=7 (both or neither; default: today's BS month)."""

    def build(self, request):
        bs_year, bs_month = (request.query_params.get(key, "").strip() or None for key in ("bs_year", "bs_month"))
        return calendar.month_view(bs_year, bs_month, user=request.user)


class CalendarDayAPIView(_CalendarView):
    """
    ?date=YYYY-MM-DD (default: today).
    ?include=market adds that session's summary, gainers / losers, top volume / transactions
    and (with view_analysis) top brokers, for the tracked companies the user may access.
    """

    def build(self, request):
        raw = request.query_params.get("date", "").strip()
        try:
            day = date.fromisoformat(raw) if raw else None
        except ValueError:
            raise calendar.CalendarError("date must use YYYY-MM-DD format.") from None
        data = calendar.day_view(day, user=request.user)
        if "market" in request.query_params.get("include", "").split(","):
            data["market"] = market_day(
                data["date"],
                company_ids=get_accessible_company_ids(request.user),
                include_brokers=request.user.has_app_permission("view_analysis"),
            )
        return data


class WeekdaySummaryAPIView(APIView):
    """?weeks=6 -- the NEPSE index's average move by weekday over the last N trading weeks."""

    permission_classes = [HasAppPermission]
    permission_key = "view_market_data"

    def get(self, request):
        try:
            weeks = int(request.query_params.get("weeks") or weekday_summary.DEFAULT_WEEKS)
        except ValueError:
            weeks = None
        if weeks not in weekday_summary.WEEK_CHOICES:
            choices = ", ".join(map(str, weekday_summary.WEEK_CHOICES))
            return Response({"detail": f"weeks must be one of {choices}."}, status=400)
        try:
            return Response(weekday_summary.to_json(weekday_summary.weekday_summary(weeks)))
        except weekday_summary.IndexNotFound as exc:
            return Response({"detail": str(exc)}, status=404)
