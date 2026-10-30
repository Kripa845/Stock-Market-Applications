"""
Footprint (order flow) for one company-day: per time bucket and price row, the traded volume
split into buy / sell by the tick rule.  Built from FloorsheetTransaction; nothing is stored.

Rules (from the floorsheet audit of 2026-10-30):

* Board lots only (trade_filters.board_lots): odd lots print away from the market.
* Trades run in contract-number order, the exchange's own sequence (it matched trade-time
  order on every stored row).
* Pre-open auction fills are a separate ``pre_open`` group: volume per price row, never
  classified, never in a bar.  An auction is not aggressive buying or selling.
* Tick rule on continuous-session trades only: an uptick is a buy, a downtick a sell, an
  unchanged price carries the previous direction.  Until the day's first price change a trade
  is ``unclassified``.  The result is an ESTIMATE (the floorsheet has no aggressor flag); the
  direction carries across bars within the day.
* Bar close = the floorsheet's own last continuous-session trade in the bar, never the
  official DailyPrice close (that differs from the last trade on ~27.5% of days).  Open, high
  and low likewise come from the bar's own trades.
* A company-day with untimed trades (date-only ShareSansar rows) cannot be bucketed or split
  into pre-open: it returns one daily bar (``start`` None, ``untimed`` True), still in
  contract-number order.  Times are never invented.
"""

from decimal import ROUND_FLOOR, Decimal

from apps.floorsheet.models import FloorsheetTransaction
from apps.floorsheet.services.intraday_candles import INTERVAL_MINUTES, bucket_start_for
from apps.floorsheet.services.trade_filters import board_lots, is_pre_open

BUY, SELL, UNCLASSIFIED = 1, -1, 0
DEFAULT_ROW_SIZE = Decimal("0.1")       # NEPSE's tick


def price_row(rate, row_size):
    """Bottom edge of the ``row_size``-wide price row holding ``rate``."""
    return (rate / row_size).to_integral_value(rounding=ROUND_FLOOR) * row_size


def _levels(rows):
    """{price: [buy, sell, unclassified]} -> list, highest price first."""
    return [
        {"price": price, "buy": buy, "sell": sell, "unclassified": unk,
         "volume": buy + sell + unk, "delta": buy - sell}
        for price, (buy, sell, unk) in sorted(rows.items(), reverse=True)
    ]


def footprint(company, day, interval="5m", row_size=DEFAULT_ROW_SIZE):
    if interval not in INTERVAL_MINUTES:
        raise ValueError(f"interval must be one of {', '.join(INTERVAL_MINUTES)}")
    row_size = Decimal(str(row_size))
    if row_size <= 0:
        raise ValueError("row_size must be positive")

    trades = list(
        board_lots(FloorsheetTransaction.objects.filter(company=company, date=day))
        .order_by("transaction_id", "pk")
        .values_list("trade_time", "rate", "quantity")
    )
    untimed = any(when is None for when, _, _ in trades)

    pre_rows, pre_volume, pre_trades = {}, 0, 0
    bars = {}
    last_rate, direction = None, UNCLASSIFIED
    for when, rate, quantity in trades:
        if not untimed and is_pre_open(when):
            pre_rows.setdefault(price_row(rate, row_size), [0, 0, 0])[2] += quantity
            pre_volume += quantity
            pre_trades += 1
            continue

        if last_rate is not None and rate != last_rate:
            direction = BUY if rate > last_rate else SELL
        last_rate = rate

        start = None if untimed else bucket_start_for(when, INTERVAL_MINUTES[interval], day)
        bar = bars.get(start)
        if bar is None:
            bar = bars[start] = {"start": start, "open": rate, "high": rate, "low": rate, "close": rate,
                                 "volume": 0, "trades": 0, "rows": {}}
        bar["high"] = max(bar["high"], rate)
        bar["low"] = min(bar["low"], rate)
        bar["close"] = rate                       # last continuous-session trade so far
        bar["volume"] += quantity
        bar["trades"] += 1
        bar["rows"].setdefault(price_row(rate, row_size), [0, 0, 0])[
            0 if direction == BUY else 1 if direction == SELL else 2
        ] += quantity

    out_bars = []
    for bar in bars.values():
        levels = _levels(bar.pop("rows"))
        buy = sum(level["buy"] for level in levels)
        sell = sum(level["sell"] for level in levels)
        out_bars.append({**bar, "buy": buy, "sell": sell, "unclassified": bar["volume"] - buy - sell,
                         "delta": buy - sell, "levels": levels})

    return {
        "date": day,
        "interval": interval,
        "row_size": row_size,
        "untimed": untimed,
        "pre_open": {"volume": pre_volume, "trades": pre_trades, "levels": _levels(pre_rows)} if pre_trades else None,
        "bars": out_bars,
    }
