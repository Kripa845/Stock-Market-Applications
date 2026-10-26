"""
Which calendar days NEPSE trades.

Two inputs, nothing hardcoded elsewhere:
  * ``settings.NEPSE_TRADING_WEEKS``: the trading week in force on each date
    (Sunday-Thursday until 2026-04-05, Monday-Friday from 2026-04-06).
  * ``TradingHoliday``: admin-entered closures that fall on a trading weekday.

This answers "should the market be open on this date?" -- for scheduling and
for the market-intelligence calendar.  Questions about history ("which
sessions did trade?") keep using ``trading_calendar``, which reads dates
actually present in DailyPrice.
"""

from datetime import date, datetime
from functools import lru_cache

from django.conf import settings
from django.utils import timezone

from apps.market_data.models import TradingHoliday


@lru_cache(maxsize=8)
def _weeks(config):
    return tuple(sorted((date.fromisoformat(start), frozenset(days)) for start, days in config))


def trading_weekdays(value: date | None = None):
    """Python weekday numbers (Monday=0) on which NEPSE trades on ``value`` (default: today)."""
    value = value or timezone.localdate()
    weekdays = frozenset(settings.NEPSE_TRADING_WEEKDAYS)
    for start, days in _weeks(tuple((start, tuple(days)) for start, days in settings.NEPSE_TRADING_WEEKS)):
        if start <= value:
            weekdays = days
    return weekdays


def is_trading_weekday(value: date) -> bool:
    return value.weekday() in trading_weekdays(value)


def is_market_day(value: date | None = None) -> bool:
    """True when ``value`` (default: today in Asia/Kathmandu) is a weekday session and not a holiday."""
    value = value or timezone.localdate()
    return is_trading_weekday(value) and not TradingHoliday.objects.filter(date=value).exists()


def is_market_open(moment: datetime | None = None) -> bool:
    """True during the 11:00-15:00 Asia/Kathmandu session of a market day (holidays included)."""
    from apps.floorsheet.services.intraday_candles import NPT, session_bounds

    moment = (moment or timezone.now()).astimezone(NPT)
    session_open, session_close = session_bounds(moment.date())
    return is_market_day(moment.date()) and session_open <= moment <= session_close


def market_closed_reason(value: date | None = None) -> str | None:
    """Why the market is closed on ``value``, or None when it is a market day."""
    value = value or timezone.localdate()
    if not is_trading_weekday(value):
        return f"{value:%A} is not a NEPSE trading day"
    holiday = TradingHoliday.objects.filter(date=value).first()
    if holiday:
        return f"trading holiday: {holiday.name}"
    return None
