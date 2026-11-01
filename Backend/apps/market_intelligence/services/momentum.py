"""
RSI(14) and MACD(12, 26, 9) on CompanyTechnicalSnapshot, from crawled DailyPrice closes.

* RSI uses Wilder's smoothing: the first average gain / loss is the simple mean of
  the first 14 changes, then ``avg = (prev * 13 + current) / 14``.
  RSI = 100 - 100 / (1 + avg_gain / avg_loss); avg_loss = 0 gives 100.  When both
  averages are 0 (no price movement for the whole lookback) RSI is undefined and
  stays NULL rather than reading "overbought".
* EMAs are seeded with the simple mean of their first N values
  (multiplier 2 / (N + 1)).  MACD = EMA12 - EMA26, signal = EMA9 of MACD,
  histogram = MACD - signal.
* Every value is NULL until the company has MIN_SESSIONS closes.

Closes are the session dates the snapshots use (``_trading_calendar``), in date
order.  Prices are NOT adjusted for bonus / right shares, so values right after a
book closure are distorted; see market_data/services/price_adjustments.py.

Writes touch only the four momentum columns and only rows whose value changed, so
re-running is idempotent.  One company failing is logged and does not stop the rest.
"""

import logging
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction

from apps.market_data.models import DailyPrice
from apps.market_intelligence.models import CompanyTechnicalSnapshot
from apps.market_intelligence.services.snapshots import _configured_excluded_dates, _trading_calendar

logger = logging.getLogger(__name__)

RSI_PERIOD = 14
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9
MIN_SESSIONS = 35
FIELDS = ("rsi_14", "macd", "macd_signal", "macd_hist")
FOUR_PLACES = Decimal("0.0001")


def _round(value):
    return value.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP) if value is not None else None


def wilder_rsi(closes, period=RSI_PERIOD):
    """RSI per close (None until ``period`` changes exist)."""
    closes = [Decimal(value) for value in closes]
    result = [None] * len(closes)
    if len(closes) <= period:
        return result
    changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    avg_gain = sum((max(c, 0) for c in changes[:period]), Decimal("0")) / period
    avg_loss = sum((max(-c, 0) for c in changes[:period]), Decimal("0")) / period

    def rsi(gain, loss):
        if loss == 0:
            return Decimal("100") if gain > 0 else None
        return Decimal("100") - Decimal("100") / (1 + gain / loss)

    result[period] = rsi(avg_gain, avg_loss)
    for i in range(period + 1, len(closes)):
        change = changes[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(change, 0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-change, 0)) / period
        result[i] = rsi(avg_gain, avg_loss)
    return result


def ema(values, period):
    """EMA seeded with the SMA of the first ``period`` non-None values; None before that."""
    result = [None] * len(values)
    start = next((i for i, value in enumerate(values) if value is not None), None)
    if start is None or len(values) - start < period:
        return result
    seed_end = start + period - 1
    current = sum(values[start:seed_end + 1], Decimal("0")) / period
    result[seed_end] = current
    multiplier = Decimal("2") / (period + 1)
    for i in range(seed_end + 1, len(values)):
        current = (values[i] - current) * multiplier + current
        result[i] = current
    return result


def macd(closes, fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL):
    """(macd, signal, histogram) lists aligned with ``closes``."""
    closes = [Decimal(value) for value in closes]
    fast_ema, slow_ema = ema(closes, fast), ema(closes, slow)
    line = [f - s if f is not None and s is not None else None for f, s in zip(fast_ema, slow_ema)]
    signal_line = ema(line, signal)
    hist = [m - s if m is not None and s is not None else None for m, s in zip(line, signal_line)]
    return line, signal_line, hist


def momentum_series(closes):
    """Per-close dict of the four stored values; all None before MIN_SESSIONS closes."""
    rsi = wilder_rsi(closes)
    line, signal_line, hist = macd(closes)
    rows = []
    for i in range(len(closes)):
        if i + 1 < MIN_SESSIONS:
            rows.append(dict.fromkeys(FIELDS))
        else:
            rows.append({
                "rsi_14": _round(rsi[i]), "macd": _round(line[i]),
                "macd_signal": _round(signal_line[i]), "macd_hist": _round(hist[i]),
            })
    return rows


def compute_momentum_snapshots(company_ids=None, dry_run=False):
    """Fill the momentum columns on every snapshot row of each company (all when None)."""
    prices = DailyPrice.objects.filter(source="crawled").order_by("date", "company_id", "pk")
    sessions, _ = _trading_calendar(list(prices.only("company_id", "date", "close", "volume")), _configured_excluded_dates())
    session_set = set(sessions)
    snapshots = CompanyTechnicalSnapshot.objects.all()
    if company_ids is not None:
        snapshots = snapshots.filter(company_id__in=company_ids)
    targets = sorted(set(snapshots.values_list("company_id", flat=True)))

    result = {"companies": 0, "rows_updated": 0, "rows_unchanged": 0, "rows_without_price": 0, "failed": []}
    for company_id in targets:
        try:
            closes = [
                (day, close) for day, close in
                prices.filter(company_id=company_id).values_list("date", "close")
                if day in session_set
            ]
            values = dict(zip((day for day, _ in closes), momentum_series([close for _, close in closes])))
            changed = []
            for snapshot in CompanyTechnicalSnapshot.objects.filter(company_id=company_id).only("id", "date", *FIELDS):
                new = values.get(snapshot.date)
                if new is None:
                    # A snapshot whose date has no crawled close: leave it to the snapshot rebuild.
                    result["rows_without_price"] += 1
                    continue
                if all(getattr(snapshot, field) == new[field] for field in FIELDS):
                    result["rows_unchanged"] += 1
                    continue
                for field in FIELDS:
                    setattr(snapshot, field, new[field])
                changed.append(snapshot)
            if changed and not dry_run:
                with transaction.atomic():
                    CompanyTechnicalSnapshot.objects.bulk_update(changed, FIELDS, batch_size=500)
            result["rows_updated"] += len(changed)
            result["companies"] += 1
        except Exception:
            logger.exception("Momentum indicators failed for company %s", company_id)
            result["failed"].append(company_id)
    return result
