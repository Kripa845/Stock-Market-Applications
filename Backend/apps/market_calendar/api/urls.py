from django.urls import path

from apps.market_calendar.api.views import CalendarDayAPIView, CalendarMonthAPIView, WeekdaySummaryAPIView

# Mounted at /api/market-calendar/
urlpatterns = [
    path("month/", CalendarMonthAPIView.as_view(), name="market-calendar-month"),
    path("day/", CalendarDayAPIView.as_view(), name="market-calendar-day"),
    path("weekdays/", WeekdaySummaryAPIView.as_view(), name="market-calendar-weekdays"),
]
