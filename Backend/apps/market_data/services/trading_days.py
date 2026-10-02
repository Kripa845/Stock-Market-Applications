"""
Which calendar days NEPSE trades.

Two inputs, nothing hardcoded elsewhere:
  * ``settings.NEPSE_TRADING_WEEKDAYS``: the trading week (Monday-Friday).
  * ``TradingHoliday``: admin-entered closures that fall on a weekday.

This answers "should the market be open on this date?" -- for scheduling.
Questions about history ("which sessions did trade?") keep using
``trading_calendar``, which reads dates actually present in DailyPrice.
"""

from datetime import date

from django.conf import settings
from django.utils import timezone

from apps.market_data.models import TradingHoliday


def trading_weekdays():
    """Python weekday numbers (Monday=0) on which NEPSE trades."""
    return frozenset(settings.NEPSE_TRADING_WEEKDAYS)


def is_trading_weekday(value: date) -> bool:
    return value.weekday() in trading_weekdays()


def is_market_day(value: date | None = None) -> bool:
    """True when ``value`` (default: today in Asia/Kathmandu) is a weekday session and not a holiday."""
    value = value or timezone.localdate()
    return is_trading_weekday(value) and not TradingHoliday.objects.filter(date=value).exists()


def market_closed_reason(value: date | None = None) -> str | None:
    """Why the market is closed on ``value``, or None when it is a market day."""
    value = value or timezone.localdate()
    if not is_trading_weekday(value):
        return f"{value:%A} is not a NEPSE trading day"
    holiday = TradingHoliday.objects.filter(date=value).first()
    if holiday:
        return f"trading holiday: {holiday.name}"
    return None
