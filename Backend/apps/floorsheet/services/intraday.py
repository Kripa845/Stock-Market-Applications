from django.utils import timezone


def aggregate_intraday_trades(trades):
    """Group ordered, timestamped floorsheet trades into sparse 1-minute bars."""
    bars = []
    current_minute = None
    current_bar = None

    for trade in trades:
        local_time = timezone.localtime(trade.trade_time)
        minute = local_time.replace(second=0, microsecond=0)
        rate = float(trade.rate)
        quantity = int(trade.quantity)

        if minute != current_minute:
            if current_bar is not None:
                bars.append(current_bar)
            current_minute = minute
            current_bar = {
                "time": minute.isoformat(),
                "open": rate,
                "high": rate,
                "low": rate,
                "close": rate,
                "volume": quantity,
            }
            continue

        current_bar["high"] = max(current_bar["high"], rate)
        current_bar["low"] = min(current_bar["low"], rate)
        current_bar["close"] = rate
        current_bar["volume"] += quantity

    if current_bar is not None:
        bars.append(current_bar)
    return bars
