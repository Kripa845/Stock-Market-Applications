"""
/api/market-calendar/ -- BS month calendar of NEPSE sessions and corporate-action events.

The index is whole-market; events cover the tracked companies the user may access
(services.calendar).
"""

from datetime import date

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.market_calendar.services import calendar, month_summary, monthly_returns, weekday_summary
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
    """
    ?weeks=6&scope=tracked -- the tracked companies' average move by weekday over the last
    N trading weeks.  scope: tracked or tracked:<sector>, narrowed to the companies the user
    may access.  ``scopes`` lists what the picker can offer this user.
    """

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
        scope = request.query_params.get("scope", "").strip() or weekday_summary.DEFAULT_SCOPE
        company_ids = get_accessible_company_ids(request.user)
        try:
            data = weekday_summary.weekday_summary(weeks, scope=scope, company_ids=company_ids)
        except weekday_summary.ScopeError as exc:
            return Response({"detail": str(exc)}, status=400)
        except weekday_summary.NoSessions as exc:
            return Response({"detail": str(exc)}, status=404)
        data["scopes"] = weekday_summary.scope_catalogue(company_ids)
        return Response(weekday_summary.to_json(data))


class MonthSummaryAPIView(APIView):
    """
    ?index=NEPSE&calendar=bs&months=12 -- NEPSE day by day: one row per BS (bs) or AD (ad) month,
    newest first, one tile per day with the index change.  Whole market, so no company scope.
    """

    permission_classes = [HasAppPermission]
    permission_key = "view_market_data"

    def get(self, request):
        params = request.query_params
        try:
            months = int(params.get("months") or month_summary.DEFAULT_MONTHS)
        except ValueError:
            months = None
        try:
            data = month_summary.month_summary(
                index_code=params.get("index", "").strip().upper() or month_summary.DEFAULT_INDEX,
                mode=params.get("calendar", "").strip() or month_summary.BS,
                months=months,
            )
        except month_summary.SummaryError as exc:
            return Response({"detail": str(exc)}, status=400)
        except month_summary.NoIndexData as exc:
            return Response({"detail": str(exc)}, status=404)
        return Response(weekday_summary.to_json(data))


class MonthlyReturnsAPIView(APIView):
    """
    ?index=NEPSE -- NEPSE month by month: one row per BS year (newest first), one tile per BS
    month with that month's index return, the year's return, an AVG row and sidebar stats.
    Whole market, so no company scope.
    """

    permission_classes = [HasAppPermission]
    permission_key = "view_market_data"

    def get(self, request):
        try:
            data = monthly_returns.monthly_returns(
                index_code=request.query_params.get("index", "").strip().upper() or month_summary.DEFAULT_INDEX,
            )
        except month_summary.SummaryError as exc:
            return Response({"detail": str(exc)}, status=400)
        except month_summary.NoIndexData as exc:
            return Response({"detail": str(exc)}, status=404)
        return Response(weekday_summary.to_json(data))
