
from statistics import covariance, variance

from apps.market_data.models import DailyPrice
from apps.market_indices.models import IndexDaily


def calculate_beta(company):
    """
    Calculate stock beta against the NEPSE index.

    Uses matching trading dates and daily percentage returns.
    A full-year beta requires 252 return observations.
    """

    stock_records = list(
        DailyPrice.objects.filter(
            company=company,
            source="crawled",
        )
        .order_by("-date")
        .values("date", "close")[:1000]
    )

    nepse_records = list(
        IndexDaily.objects.filter(
            index__code="NEPSE",
            source="crawled",
        )
        .order_by("-date")
        .values("date", "close")[:1000]
    )

    stock_prices = {
        row["date"]: float(row["close"])
        for row in stock_records
        if row["close"] is not None and float(row["close"]) > 0
    }

    nepse_prices = {
        row["date"]: float(row["close"])
        for row in nepse_records
        if row["close"] is not None and float(row["close"]) > 0
    }

    common_dates = sorted(
        set(stock_prices) & set(nepse_prices)
    )[-253:]

    if len(common_dates) < 31:
        return {
            "beta": None,
            "observations": max(0, len(common_dates) - 1),
            "status": "insufficient_data",
        }

    stock_returns = []
    market_returns = []

    for i in range(1, len(common_dates)):
        previous_date = common_dates[i - 1]
        current_date = common_dates[i]

        stock_return = (
            stock_prices[current_date] - stock_prices[previous_date]
        ) / stock_prices[previous_date]

        market_return = (
            nepse_prices[current_date] - nepse_prices[previous_date]
        ) / nepse_prices[previous_date]

        stock_returns.append(stock_return)
        market_returns.append(market_return)

    market_variance = variance(market_returns)

    if market_variance == 0:
        return {
            "beta": None,
            "observations": len(stock_returns),
            "status": "zero_market_variance",
        }

    beta = covariance(
        stock_returns,
        market_returns,
    ) / market_variance

    return {
        "beta": round(beta, 2),
        "observations": len(stock_returns),
        "status": (
            "full_year"
            if len(stock_returns) >= 252
            else "partial_history"
        ),
    }
