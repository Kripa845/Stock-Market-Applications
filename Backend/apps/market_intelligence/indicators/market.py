"""Indicators that need more than one stock's prices: breadth, relative strength and tick data.

Breadth functions take ``universe``: one dict per company mapping date -> (close, volume, high, low),
plus the sorted list of ``dates`` to report on. Relative-strength functions take the stock's closes
and a ``benchmark`` series aligned to the same dates (None where the benchmark has no value).
"""

from datetime import timedelta
from math import log

from .core import check_period, combine, lag, pearson, rolling_multi, sma


def _per_company_sma(series, period):
    """SMA over each company's own trading days, returned as date -> value."""
    days = sorted(series)
    closes = [series[d][0] for d in days]
    return dict(zip(days, sma(closes, period)))


def advance_decline(universe, dates):
    net, line, total = [None] * len(dates), [None] * len(dates), 0.0
    previous = [dict(zip(sorted(s)[1:], sorted(s)[:-1])) for s in universe]
    for i, day in enumerate(dates):
        advances = declines = counted = 0
        for series, prev_of in zip(universe, previous):
            if day in series and day in prev_of:
                counted += 1
                change = series[day][0] - series[prev_of[day]][0]
                advances += change > 0
                declines += change < 0
        if counted:
            total += advances - declines
            net[i], line[i] = float(advances - declines), total
    return {"net": net, "line": line}


def ad_volume_line(universe, dates):
    out, total = [None] * len(dates), 0.0
    previous = [dict(zip(sorted(s)[1:], sorted(s)[:-1])) for s in universe]
    for i, day in enumerate(dates):
        counted, net = 0, 0.0
        for series, prev_of in zip(universe, previous):
            if day in series and day in prev_of:
                counted += 1
                close, volume = series[day][0], series[day][1]
                prev_close = series[prev_of[day]][0]
                net += volume if close > prev_close else -volume if close < prev_close else 0.0
        if counted:
            total += net
            out[i] = total
    return out


def percent_above_ma(universe, dates, fast=20, medium=50, slow=200):
    result = {}
    for key, period in (("above_fast", fast), ("above_medium", medium), ("above_slow", slow)):
        averages = [_per_company_sma(s, period) for s in universe]
        values = []
        for day in dates:
            eligible = above = 0
            for series, avg in zip(universe, averages):
                if avg.get(day) is not None:
                    eligible += 1
                    above += series[day][0] > avg[day]
            values.append(100 * above / eligible if eligible else None)
        result[key] = values
    return result


def net_new_highs_lows(universe, dates, weeks=52):
    """New 52-week highs minus new lows; a company counts only once it has ``weeks`` of history."""
    span = timedelta(weeks=check_period(weeks))
    out = [None] * len(dates)
    sorted_days = [sorted(s) for s in universe]
    for i, day in enumerate(dates):
        eligible = net = 0
        for series, days in zip(universe, sorted_days):
            if day not in series or days[0] > day - span:
                continue
            window = [series[d] for d in days if day - span < d <= day]
            eligible += 1
            high, low = series[day][2], series[day][3]
            net += (high >= max(w[2] for w in window)) - (low <= min(w[3] for w in window))
        out[i] = float(net) if eligible else None
    return out


def ratio(close, benchmark):
    return combine(lambda c, b: c / b, close, benchmark)


def spread(close, benchmark):
    return combine(lambda c, b: c - b, close, benchmark)


def relative_strength(close, benchmark):
    return combine(lambda c, b: c / b * 100, close, benchmark)


def mansfield_rs(close, benchmark, period=200):
    rs = relative_strength(close, benchmark)
    return combine(lambda r, avg: (r / avg - 1) * 100, rs, sma(rs, period))


def correlation(close, benchmark, period=20):
    return rolling_multi([close, benchmark], check_period(period, 2), pearson)


def log_correlation(close, benchmark, period=20):
    def returns(series):
        return combine(lambda c, p: log(c / p) if c > 0 and p > 0 else None, series, lag(series, 1))
    return rolling_multi([returns(close), returns(benchmark)], check_period(period, 2), pearson)


def tick_buy_sell(trades, dates):
    """Daily buy / sell volume by the tick rule.

    ``trades`` are (date, sequence, price, quantity) in execution order. A trade above the
    previous price is a buy, below is a sell; an unchanged price takes the previous trade's
    side (zero-tick rule). The first trade, with no previous price, is not classified.
    """
    buys, sells = {}, {}
    last_price = last_side = None
    for day, _, price, quantity in trades:
        side = None
        if last_price is not None:
            side = "buy" if price > last_price else "sell" if price < last_price else last_side
        if side == "buy":
            buys[day] = buys.get(day, 0.0) + quantity
        elif side == "sell":
            sells[day] = sells.get(day, 0.0) + quantity
        if side:
            last_side = side
        last_price = price
    traded = {t[0] for t in trades}
    return {
        "buy": [buys.get(d, 0.0) if d in traded else None for d in dates],
        "sell": [sells.get(d, 0.0) if d in traded else None for d in dates],
    }
