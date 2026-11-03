
from datetime import date
from statistics import stdev

from apps.market_data.models import DailyPrice
from apps.market_data.services.market_beta import calculate_beta


def calculate_stock_performance(company):
    """
    Calculate historical stock performance metrics
    using real crawled DailyPrice records.

    Price periods are measured in trading sessions.
    """

    # STEP 1: Fetch historical price records

    records = list(
        DailyPrice.objects.filter(
            company=company,
            source="crawled",
        )
        .order_by("-date")
        .values(
            "date",
            "high",
            "low",
            "close",
            "volume",
        )[:350]
    )

    records.reverse()

    if not records:
        return {}

    # STEP 2: Extract valid closing prices

    valid_records = [
        row for row in records
        if row["close"] is not None and float(row["close"]) > 0
    ]

    if not valid_records:
        return {}

    closes = [float(row["close"]) for row in valid_records]

    highs = [
        float(row["high"])
        if row["high"] is not None else None
        for row in valid_records
    ]

    lows = [
        float(row["low"])
        if row["low"] is not None else None
        for row in valid_records
    ]

    volumes = [
        float(row["volume"])
        if row["volume"] is not None else None
        for row in valid_records
    ]

    current_price = closes[-1]
    latest_date = valid_records[-1]["date"]

    # STEP 3: Percentage change helper

    def percentage_change(sessions):
        if len(closes) <= sessions:
            return None

        previous_price = closes[-(sessions + 1)]

        if previous_price == 0:
            return None

        result = (
            (current_price - previous_price)
            / previous_price
        ) * 100

        return round(result, 2)

    # STEP 4: Average volume helper

    def average_volume(sessions):
        values = volumes[-sessions:]

        if len(values) < sessions or any(v is None for v in values):
            return None

        return round(sum(values) / sessions, 2)

    # STEP 5: Average closing price helper

    def average_price(sessions):
        values = closes[-sessions:]

        if len(values) < sessions:
            return None

        return round(sum(values) / sessions, 2)

    # STEP 6: Year-to-date change

    year_start = date(latest_date.year, 1, 1)

    previous_year_record = (
        DailyPrice.objects.filter(
            company=company,
            source="crawled",
            date__lt=year_start,
            close__gt=0,
        )
        .order_by("-date")
        .values("close")
        .first()
    )

    ytd_change = None

    if previous_year_record:
        previous_close = float(previous_year_record["close"])

        ytd_change = round(
            ((current_price - previous_close) / previous_close) * 100,
            2,
        )

    # STEP 7: Three-month and 52-week highs/lows

    recent_highs = highs[-63:]
    recent_lows = lows[-63:]

    three_month_high = (
        round(max(v for v in recent_highs if v is not None), 2)
        if len(recent_highs) == 63 and all(v is not None for v in recent_highs)
        else None
    )

    three_month_low = (
        round(min(v for v in recent_lows if v is not None), 2)
        if len(recent_lows) == 63 and all(v is not None for v in recent_lows)
        else None
    )

    year_highs = highs[-252:]
    year_lows = lows[-252:]

    fifty_two_week_high = (
        max(year_highs)
        if len(year_highs) == 252 and all(v is not None for v in year_highs)
        else None
    )

    fifty_two_week_low = (
        min(year_lows)
        if len(year_lows) == 252 and all(v is not None for v in year_lows)
        else None
    )

    # STEP 8: Distance from 52-week high/low

    from_52_week_high = None
    from_52_week_low = None

    if fifty_two_week_high:
        from_52_week_high = round(
            ((current_price - fifty_two_week_high) / fifty_two_week_high) * 100,
            2,
        )

    if fifty_two_week_low:
        from_52_week_low = round(
            ((current_price - fifty_two_week_low) / fifty_two_week_low) * 100,
            2,
        )

    # STEP 9: Calculate daily returns

    daily_returns = []

    for i in range(1, len(closes)):
        previous_close = closes[i - 1]

        daily_return = (
            (closes[i] - previous_close) / previous_close
        )

        daily_returns.append(daily_return)

    # STEP 10: One-month daily volatility

    volatility = None

    monthly_returns = daily_returns[-21:]

    if len(monthly_returns) >= 2:
        volatility = round(stdev(monthly_returns) * 100, 2)

    # STEP 11: Calculate beta against NEPSE

    beta_data = calculate_beta(company)

    # STEP 12: Return performance metrics

    return {
        "current_price": round(current_price, 2),

        "week_change": percentage_change(5),
        "month_change": percentage_change(21),
        "three_month_change": percentage_change(63),
        "six_month_change": percentage_change(126),
        "ytd_change": ytd_change,
        "year_change": percentage_change(252),

        "three_month_high": three_month_high,
        "three_month_low": three_month_low,

        "fifty_two_week_high": (
            round(fifty_two_week_high, 2)
            if fifty_two_week_high is not None else None
        ),

        "fifty_two_week_low": (
            round(fifty_two_week_low, 2)
            if fifty_two_week_low is not None else None
        ),

        "from_52_week_high": from_52_week_high,
        "from_52_week_low": from_52_week_low,

        "avg_price_180d": average_price(180),
        "avg_price_350d": average_price(350),

        "avg_volume_1w": average_volume(5),
        "avg_volume_1m": average_volume(21),
        "avg_volume_6m": average_volume(126),
        "avg_volume_12m": average_volume(252),

        "daily_volatility_1m": volatility,

        "beta_vs_nepse_1y": beta_data,
    }
