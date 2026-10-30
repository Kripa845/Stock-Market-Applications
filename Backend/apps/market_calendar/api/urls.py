from django.urls import path

from apps.market_calendar.api.views import (
    CalendarDayAPIView, CalendarMonthAPIView, MonthlyReturnsAPIView, MonthSummaryAPIView,
    WeekdaySummaryAPIView,
)

# Mounted at /api/market-calendar/
urlpatterns = [
    path("month/", CalendarMonthAPIView.as_view(), name="market-calendar-month"),
    path("day/", CalendarDayAPIView.as_view(), name="market-calendar-day"),
    path("months/", MonthSummaryAPIView.as_view(), name="market-calendar-months"),
    path("monthly/", MonthlyReturnsAPIView.as_view(), name="market-calendar-monthly"),
    path("weekdays/", WeekdaySummaryAPIView.as_view(), name="market-calendar-weekdays"),
]
