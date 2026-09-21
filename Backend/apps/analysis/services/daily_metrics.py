

# from __future__ import annotations

# from collections import namedtuple
# from decimal import Decimal, DivisionByZero, InvalidOperation

# # ---------------------------------------------------------------------
# # Tunable application constants
# # ---------------------------------------------------------------------

# #: Number of previous TRADING SESSIONS in the volume baseline.
# BASELINE_SESSIONS = 20

# #: Application threshold for flagging a volume anomaly.
# #: This is a project convention, not a universal financial law.
# VOLUME_ANOMALY_THRESHOLD = Decimal("1.5")

# #: When history is shorter than ``BASELINE_SESSIONS`` we still publish a
# #: provisional ratio for display, but we never raise an anomaly flag off
# #: a partial baseline — a 3-session average is too noisy to trust.
# ANOMALY_REQUIRES_FULL_BASELINE = True

# #: Identifier stored on every row so the frontend can explain the signal.
# PRESSURE_METHOD = "OHLCV_PRICE_VOLUME"

# # Pressure score weights.  Maximum magnitude is 50 + 30 + 20 = 100.
# WEIGHT_DIRECTION = Decimal("50")
# WEIGHT_VWAP = Decimal("30")
# WEIGHT_CONVICTION = Decimal("20")

# #: With no price direction to confirm it, the VWAP term contributes at
# #: half weight, so a flat close cannot on its own be called pressure.
# NEUTRAL_DIRECTION_VWAP_DAMPING = Decimal("0.5")

# #: Volume ratio at which conviction starts and saturates.
# CONVICTION_FLOOR = Decimal("1.0")
# CONVICTION_CEILING = Decimal("1.5")

# #: |score| must reach this before the day is labelled buying/selling.
# PRESSURE_BAND = Decimal("25")

# # Rounding targets.
# VWAP_PRECISION = Decimal("0.0001")
# RATIO_PRECISION = Decimal("0.01")
# SCORE_PRECISION = Decimal("0.01")
# VOLUME_AVG_PRECISION = Decimal("0.01")
# RETURN_PRECISION = Decimal("0.0001")


# VolumeBaseline = namedtuple(
#     "VolumeBaseline",
#     [
#         "average",
#         "ratio",
#         "anomaly",
#         "sessions_used",
#         "sufficient_history",
#     ],
# )


# # ---------------------------------------------------------------------
# # Small helpers
# # ---------------------------------------------------------------------

# def _to_decimal(value):
#     """Best-effort Decimal conversion; ``None`` for anything unusable."""
#     if value is None:
#         return None

#     if isinstance(value, Decimal):
#         return value

#     try:
#         return Decimal(str(value).replace(",", "").strip())
#     except (InvalidOperation, ValueError, AttributeError):
#         return None


# def _quantize(value, precision):
#     if value is None:
#         return None

#     try:
#         return value.quantize(precision)
#     except (InvalidOperation, AttributeError):
#         return None


# def _clamp(value, lower, upper):
#     return max(lower, min(upper, value))


# # ---------------------------------------------------------------------
# # 1. DAILY VWAP
# # ---------------------------------------------------------------------

# def calculate_daily_vwap(turnover, volume):
#     """
#     Daily VWAP = daily turnover / daily volume, for ONE trading day.

#     This is deliberately not a 30-day aggregate.  The 30-day aggregate is
#     a separate summary metric, ``calculate_period_vwap`` below.

#     Returns ``None`` — never zero and never a raised exception — when the
#     inputs cannot produce a meaningful average price:

#     * volume is missing, zero or negative (division by zero)
#     * turnover is missing/NULL
#     * turnover is negative

#     ``None`` is the honest answer here: a day with no volume has no
#     volume-weighted average price, and storing 0.0 would silently poison
#     every downstream comparison of close against VWAP.
#     """
#     turnover_value = _to_decimal(turnover)
#     volume_value = _to_decimal(volume)

#     if turnover_value is None or volume_value is None:
#         return None

#     if volume_value <= 0 or turnover_value < 0:
#         return None

#     try:
#         return _quantize(turnover_value / volume_value, VWAP_PRECISION)
#     except (DivisionByZero, InvalidOperation):
#         return None


# def calculate_period_vwap(rows):
#     """
#     Aggregate VWAP across several days = SUM(turnover) / SUM(volume).

#     Kept as a clearly separate summary metric so it can never be
#     mistaken for, or overwrite, the per-day VWAP above.  ``rows`` is any
#     iterable of objects exposing ``turnover`` and ``volume``.
#     """
#     total_turnover = Decimal("0")
#     total_volume = Decimal("0")

#     for row in rows:
#         turnover_value = _to_decimal(getattr(row, "turnover", None))
#         volume_value = _to_decimal(getattr(row, "volume", None))

#         if turnover_value is None or volume_value is None:
#             continue

#         if volume_value <= 0 or turnover_value < 0:
#             continue

#         total_turnover += turnover_value
#         total_volume += volume_value

#     if total_volume <= 0:
#         return None

#     return _quantize(total_turnover / total_volume, VWAP_PRECISION)


# # ---------------------------------------------------------------------
# # 2. VOLUME BASELINE AND ANOMALY
# # ---------------------------------------------------------------------

# def calculate_volume_baseline(today_volume, previous_volumes):
#     """
#     Compare today's volume against the mean of the PREVIOUS trading
#     sessions.

#     ``previous_volumes`` must contain only sessions strictly before the
#     day being analysed — today's own volume is never part of its own
#     baseline, otherwise a genuine spike partially cancels itself out.
#     The caller is responsible for supplying real trading sessions, which
#     is how weekends and holidays are handled: they simply never appear.

#     Insufficient-history policy (explicit, by design):

#     * 0 prior sessions       -> average None, ratio None, anomaly False
#     * 1..19 prior sessions   -> provisional average and ratio are
#                                 published for display, but ``anomaly``
#                                 stays False and ``sufficient_history``
#                                 is False
#     * >= 20 prior sessions   -> full baseline, anomaly flag is live
#     * average of zero        -> ratio None, anomaly False (no division)
#     """
#     usable = []

#     for volume in previous_volumes or []:
#         value = _to_decimal(volume)
#         if value is not None and value >= 0:
#             usable.append(value)

#     # Only the most recent BASELINE_SESSIONS sessions count.
#     window = usable[:BASELINE_SESSIONS]
#     sessions_used = len(window)
#     sufficient = sessions_used >= BASELINE_SESSIONS

#     if sessions_used == 0:
#         return VolumeBaseline(None, None, False, 0, False)

#     average = sum(window) / Decimal(sessions_used)
#     average = _quantize(average, VOLUME_AVG_PRECISION)

#     today_value = _to_decimal(today_volume)

#     if average is None or average <= 0 or today_value is None:
#         return VolumeBaseline(average, None, False, sessions_used, sufficient)

#     try:
#         ratio = _quantize(today_value / average, RATIO_PRECISION)
#     except (DivisionByZero, InvalidOperation):
#         return VolumeBaseline(average, None, False, sessions_used, sufficient)

#     anomaly = ratio is not None and ratio >= VOLUME_ANOMALY_THRESHOLD

#     if ANOMALY_REQUIRES_FULL_BASELINE and not sufficient:
#         anomaly = False

#     return VolumeBaseline(average, ratio, anomaly, sessions_used, sufficient)


# # ---------------------------------------------------------------------
# # 3. PRESSURE PROXY  (method: OHLCV_PRICE_VOLUME)
# # ---------------------------------------------------------------------

# def _price_direction(close, previous_close):
#     """+1 / 0 / -1, and 0 when previous_close is missing."""
#     close_value = _to_decimal(close)
#     previous_value = _to_decimal(previous_close)

#     if close_value is None or previous_value is None:
#         return Decimal("0"), False

#     if close_value > previous_value:
#         return Decimal("1"), True
#     if close_value < previous_value:
#         return Decimal("-1"), True

#     return Decimal("0"), True


# def _vwap_position(close, vwap):
#     """+1 when the close is above daily VWAP, -1 below, 0 if unavailable."""
#     close_value = _to_decimal(close)
#     vwap_value = _to_decimal(vwap)

#     if close_value is None or vwap_value is None or vwap_value <= 0:
#         return Decimal("0"), False

#     if close_value > vwap_value:
#         return Decimal("1"), True
#     if close_value < vwap_value:
#         return Decimal("-1"), True

#     return Decimal("0"), True


# def _volume_conviction(volume_ratio):
#     """
#     Map the volume ratio onto a 0..1 conviction weight.

#     ratio <= 1.0 -> 0.0   (no more volume than usual, no conviction)
#     ratio >= 1.5 -> 1.0   (at or past the anomaly threshold, full weight)
#     in between   -> linear
#     """
#     ratio = _to_decimal(volume_ratio)

#     if ratio is None or ratio <= CONVICTION_FLOOR:
#         return Decimal("0"), ratio is not None

#     span = CONVICTION_CEILING - CONVICTION_FLOOR
#     conviction = (ratio - CONVICTION_FLOOR) / span

#     return _clamp(conviction, Decimal("0"), Decimal("1")), True


# def calculate_pressure(close, previous_close, vwap, volume_ratio):
#     """
#     Transparent OHLCV pressure proxy.

#     The score is defined exactly as::

#         D = price direction      -> +1 / 0 / -1   (close vs previous_close)
#         V = VWAP position        -> +1 / 0 / -1   (close vs daily VWAP)
#         C = volume conviction    -> 0.0 .. 1.0    (from volume_ratio)

#         vwap_weight = 30, halved to 15 when D == 0

#         score = 50 * D  +  vwap_weight * V  +  20 * D * C

#         score in [-100, +100]

#         score >= +25  -> "buying"
#         score <= -25  -> "selling"
#         otherwise     -> "neutral"

#     Every missing input degrades to a zero contribution rather than an
#     exception, so a day with no previous close, no VWAP and no volume
#     history scores exactly 0 and is reported as neutral with the reasons
#     recorded in the returned metadata.

#     This describes the relationship between published price, published
#     volume and published VWAP.  It does NOT observe order-book depth and
#     must never be presented as proof of real buying or selling interest.
#     """
#     direction, has_previous_close = _price_direction(close, previous_close)
#     vwap_signal, has_vwap = _vwap_position(close, vwap)
#     conviction, has_volume_ratio = _volume_conviction(volume_ratio)

#     vwap_weight = WEIGHT_VWAP
#     if direction == 0:
#         vwap_weight = WEIGHT_VWAP * NEUTRAL_DIRECTION_VWAP_DAMPING

#     score = (
#         (WEIGHT_DIRECTION * direction)
#         + (vwap_weight * vwap_signal)
#         + (WEIGHT_CONVICTION * direction * conviction)
#     )

#     score = _clamp(score, Decimal("-100"), Decimal("100"))
#     score = _quantize(score, SCORE_PRECISION)

#     if score >= PRESSURE_BAND:
#         label = "buying"
#     elif score <= -PRESSURE_BAND:
#         label = "selling"
#     else:
#         label = "neutral"

#     missing = []
#     if not has_previous_close:
#         missing.append("previous_close")
#     if not has_vwap:
#         missing.append("vwap")
#     if not has_volume_ratio:
#         missing.append("volume_ratio")

#     return {
#         "pressure": label,
#         "pressure_score": score,
#         "pressure_method": PRESSURE_METHOD,
#         "components": {
#             "price_direction": int(direction),
#             "vwap_position": int(vwap_signal),
#             "volume_conviction": _quantize(conviction, SCORE_PRECISION),
#             "vwap_weight": vwap_weight,
#         },
#         "missing_inputs": missing,
#         "is_complete": not missing,
#     }


# def calculate_daily_return_pct(close, previous_close):
#     """Percentage change against the previous close, separate from VWAP."""
#     close_value = _to_decimal(close)
#     previous_value = _to_decimal(previous_close)

#     if close_value is None or previous_value is None or previous_value <= 0:
#         return None

#     change = (close_value - previous_value) / previous_value * Decimal("100")
#     return _quantize(change, RETURN_PRECISION)


# # ---------------------------------------------------------------------
# # ORCHESTRATION
# # ---------------------------------------------------------------------

# def _deduplicate_chronologically(prices):
#     """
#     Sort ascending by date and collapse duplicate dates.

#     ``DailyPrice`` has a unique (company, date) constraint so duplicates
#     should not reach us, but this function is also fed by tests and by
#     in-memory row lists, so it defends anyway.  The last occurrence of a
#     date wins, which matches ``update_or_create`` semantics upstream.
#     """
#     by_date = {}

#     for row in prices:
#         row_date = getattr(row, "date", None)
#         if row_date is None:
#             continue
#         by_date[row_date] = row

#     return [by_date[key] for key in sorted(by_date)]


# def build_analysis_rows(prices):
#     """
#     Turn a list of ``DailyPrice``-like rows into per-day analysis dicts.

#     Pure function: no database writes, no ``now()``, no randomness.  The
#     same input list always produces the same output, which is what makes
#     the whole analysis layer reproducible.

#     A single chronological pass carries the previous close forward and
#     keeps a rolling list of previous session volumes, so the baseline for
#     day N only ever sees days N-1 .. N-20.
#     """
#     ordered = _deduplicate_chronologically(prices)

#     previous_volumes = []          # most recent first
#     previous_close = None
#     results = []

#     for row in ordered:
#         close = getattr(row, "close", None)
#         volume = getattr(row, "volume", None)
#         turnover = getattr(row, "turnover", None)

#         vwap = calculate_daily_vwap(turnover, volume)

#         baseline = calculate_volume_baseline(volume, previous_volumes)

#         pressure = calculate_pressure(
#             close=close,
#             previous_close=previous_close,
#             vwap=vwap,
#             volume_ratio=baseline.ratio,
#         )

#         results.append(
#             {
#                 "date": row.date,
#                 "close_price": close,
#                 "volume": volume,
#                 "turnover": turnover,
#                 "vwap": vwap,
#                 "previous_close": previous_close,
#                 "daily_return_pct": calculate_daily_return_pct(
#                     close,
#                     previous_close,
#                 ),
#                 "volume_average": baseline.average,
#                 "volume_ratio": baseline.ratio,
#                 "volume_anomaly": baseline.anomaly,
#                 "volume_baseline_sessions": baseline.sessions_used,
#                 "has_sufficient_history": baseline.sufficient_history,
#                 "pressure": pressure["pressure"],
#                 "pressure_score": pressure["pressure_score"],
#                 "pressure_method": pressure["pressure_method"],
#                 "pressure_components": pressure["components"],
#                 "pressure_missing_inputs": pressure["missing_inputs"],
#             }
#         )

#         # Advance the rolling state AFTER the row has been scored.
#         previous_close = close

#         volume_value = _to_decimal(volume)
#         if volume_value is not None and volume_value >= 0:
#             previous_volumes.insert(0, volume_value)
#             del previous_volumes[BASELINE_SESSIONS:]

#     return results


# def rebuild_company_analysis(company, since=None, persist=True):
#     """
#     Recompute and store ``DailyAnalysis`` for one company.

#     Always loads BASELINE_SESSIONS extra days of warm-up history before
#     ``since`` so the first stored day still gets a full 20-session
#     baseline instead of a truncated one.

#     Returns the list of computed row dicts.  Designed to be called from
#     the Celery analysis task, not from a request handler.
#     """
#     # Imported here to keep the pure-maths part of this module importable
#     # without the Django app registry being ready.
#     from apps.analysis.models import DailyAnalysis
#     from apps.market_data.models import DailyPrice

#     queryset = DailyPrice.objects.filter(company=company).order_by("date")

#     if since is not None:
#         warmup_dates = list(
#             DailyPrice.objects
#             .filter(company=company, date__lt=since)
#             .order_by("-date")
#             .values_list("date", flat=True)[:BASELINE_SESSIONS]
#         )
#         if warmup_dates:
#             queryset = queryset.filter(date__gte=min(warmup_dates))

#     prices = list(queryset)
#     rows = build_analysis_rows(prices)

#     if since is not None:
#         stored_rows = [row for row in rows if row["date"] >= since]
#     else:
#         stored_rows = rows

#     if not persist:
#         return stored_rows

#     for row in stored_rows:
#         if row["close_price"] is None or row["volume"] is None:
#             # close_price and volume are NOT NULL on DailyAnalysis; a row
#             # this broken is skipped rather than crashing the whole pass.
#             continue

#         DailyAnalysis.objects.update_or_create(
#             company=company,
#             date=row["date"],
#             defaults={
#                 "vwap": row["vwap"],
#                 "close_price": row["close_price"],
#                 "volume": row["volume"],
#                 "previous_close": row["previous_close"],
#                 "daily_return_pct": row["daily_return_pct"],
#                 "volume_average": row["volume_average"],
#                 "volume_ratio": row["volume_ratio"],
#                 "volume_anomaly": row["volume_anomaly"],
#                 "volume_baseline_sessions": row["volume_baseline_sessions"],
#                 "has_sufficient_history": row["has_sufficient_history"],
#                 "pressure": row["pressure"],
#                 "pressure_score": row["pressure_score"],
#                 "pressure_method": row["pressure_method"],
#             },
#         )

#     return stored_rows
"""
Per-trading-day analytics derived from ``DailyPrice``.

Everything in this module is a pure function of its arguments so the
numbers are deterministic and unit-testable without a database.  The
database-writing orchestration lives at the bottom in
``rebuild_company_analysis``.

Three metrics are defined here:

1. Daily VWAP      = daily turnover / daily volume      (per trading day)
2. Volume baseline = mean volume of the PREVIOUS 20 TRADING SESSIONS
3. Pressure proxy  = transparent OHLCV score, method ``OHLCV_PRICE_VOLUME``

None of these read the order book.  The pressure score is a proxy built
from published OHLCV data only; it is not evidence of real buying or
selling interest.  Broker-level net positions are a separate concern and
live in ``apps.analysis.services.brokers``.
"""

from __future__ import annotations

from collections import namedtuple
from decimal import Decimal, DivisionByZero, InvalidOperation

# ---------------------------------------------------------------------
# Tunable application constants
# ---------------------------------------------------------------------

#: Number of previous TRADING SESSIONS in the volume baseline.
BASELINE_SESSIONS = 20

#: Application threshold for flagging a volume anomaly.
#: This is a project convention, not a universal financial law.
VOLUME_ANOMALY_THRESHOLD = Decimal("1.5")

#: When history is shorter than ``BASELINE_SESSIONS`` we still publish a
#: provisional ratio for display, but we never raise an anomaly flag off
#: a partial baseline — a 3-session average is too noisy to trust.
ANOMALY_REQUIRES_FULL_BASELINE = True

#: Identifier stored on every row so the frontend can explain the signal.
PRESSURE_METHOD = "OHLCV_PRICE_VOLUME"

# Pressure score weights.  Maximum magnitude is 50 + 30 + 20 = 100.
WEIGHT_DIRECTION = Decimal("50")
WEIGHT_VWAP = Decimal("30")
WEIGHT_CONVICTION = Decimal("20")

#: With no price direction to confirm it, the VWAP term contributes at
#: half weight, so a flat close cannot on its own be called pressure.
NEUTRAL_DIRECTION_VWAP_DAMPING = Decimal("0.5")

#: Volume ratio at which conviction starts and saturates.
CONVICTION_FLOOR = Decimal("1.0")
CONVICTION_CEILING = Decimal("1.5")

#: |score| must reach this before the day is labelled buying/selling.
PRESSURE_BAND = Decimal("25")

# Rounding targets.
VWAP_PRECISION = Decimal("0.0001")
RATIO_PRECISION = Decimal("0.01")
SCORE_PRECISION = Decimal("0.01")
VOLUME_AVG_PRECISION = Decimal("0.01")
RETURN_PRECISION = Decimal("0.0001")


VolumeBaseline = namedtuple(
    "VolumeBaseline",
    [
        "average",
        "ratio",
        "anomaly",
        "sessions_used",
        "sufficient_history",
    ],
)


# ---------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------

def _to_decimal(value):
    """Best-effort Decimal conversion; ``None`` for anything unusable."""
    if value is None:
        return None

    if isinstance(value, Decimal):
        return value

    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError, AttributeError):
        return None


def _quantize(value, precision):
    if value is None:
        return None

    try:
        return value.quantize(precision)
    except (InvalidOperation, AttributeError):
        return None


def _clamp(value, lower, upper):
    return max(lower, min(upper, value))


# ---------------------------------------------------------------------
# 1. DAILY VWAP
# ---------------------------------------------------------------------

def calculate_daily_vwap(turnover, volume):
    """
    Daily VWAP = daily turnover / daily volume, for ONE trading day.

    This is deliberately not a 30-day aggregate.  The 30-day aggregate is
    a separate summary metric, ``calculate_period_vwap`` below.

    Returns ``None`` — never zero and never a raised exception — when the
    inputs cannot produce a meaningful average price:

    * volume is missing, zero or negative (division by zero)
    * turnover is missing/NULL
    * turnover is negative

    ``None`` is the honest answer here: a day with no volume has no
    volume-weighted average price, and storing 0.0 would silently poison
    every downstream comparison of close against VWAP.
    """
    turnover_value = _to_decimal(turnover)
    volume_value = _to_decimal(volume)

    if turnover_value is None or volume_value is None:
        return None

    if volume_value <= 0 or turnover_value < 0:
        return None

    try:
        return _quantize(turnover_value / volume_value, VWAP_PRECISION)
    except (DivisionByZero, InvalidOperation):
        return None


def calculate_period_vwap(rows):
    """
    Aggregate VWAP across several days = SUM(turnover) / SUM(volume).

    Kept as a clearly separate summary metric so it can never be
    mistaken for, or overwrite, the per-day VWAP above.  ``rows`` is any
    iterable of objects exposing ``turnover`` and ``volume``.
    """
    total_turnover = Decimal("0")
    total_volume = Decimal("0")

    for row in rows:
        turnover_value = _to_decimal(getattr(row, "turnover", None))
        volume_value = _to_decimal(getattr(row, "volume", None))

        if turnover_value is None or volume_value is None:
            continue

        if volume_value <= 0 or turnover_value < 0:
            continue

        total_turnover += turnover_value
        total_volume += volume_value

    if total_volume <= 0:
        return None

    return _quantize(total_turnover / total_volume, VWAP_PRECISION)


# ---------------------------------------------------------------------
# 2. VOLUME BASELINE AND ANOMALY
# ---------------------------------------------------------------------

def calculate_volume_baseline(today_volume, previous_volumes):
    """
    Compare today's volume against the mean of the PREVIOUS trading
    sessions.

    ``previous_volumes`` must contain only sessions strictly before the
    day being analysed — today's own volume is never part of its own
    baseline, otherwise a genuine spike partially cancels itself out.
    The caller is responsible for supplying real trading sessions, which
    is how weekends and holidays are handled: they simply never appear.

    Insufficient-history policy (explicit, by design):

    * 0 prior sessions       -> average None, ratio None, anomaly False
    * 1..19 prior sessions   -> provisional average and ratio are
                                published for display, but ``anomaly``
                                stays False and ``sufficient_history``
                                is False
    * >= 20 prior sessions   -> full baseline, anomaly flag is live
    * average of zero        -> ratio None, anomaly False (no division)
    """
    usable = []

    for volume in previous_volumes or []:
        value = _to_decimal(volume)
        if value is not None and value >= 0:
            usable.append(value)

    # Only the most recent BASELINE_SESSIONS sessions count.
    window = usable[:BASELINE_SESSIONS]
    sessions_used = len(window)
    sufficient = sessions_used >= BASELINE_SESSIONS

    if sessions_used == 0:
        return VolumeBaseline(None, None, False, 0, False)

    average = sum(window) / Decimal(sessions_used)
    average = _quantize(average, VOLUME_AVG_PRECISION)

    today_value = _to_decimal(today_volume)

    if average is None or average <= 0 or today_value is None:
        return VolumeBaseline(average, None, False, sessions_used, sufficient)

    try:
        ratio = _quantize(today_value / average, RATIO_PRECISION)
    except (DivisionByZero, InvalidOperation):
        return VolumeBaseline(average, None, False, sessions_used, sufficient)

    anomaly = ratio is not None and ratio >= VOLUME_ANOMALY_THRESHOLD

    if ANOMALY_REQUIRES_FULL_BASELINE and not sufficient:
        anomaly = False

    return VolumeBaseline(average, ratio, anomaly, sessions_used, sufficient)


# ---------------------------------------------------------------------
# 3. PRESSURE PROXY  (method: OHLCV_PRICE_VOLUME)
# ---------------------------------------------------------------------

def _price_direction(close, previous_close):
    """+1 / 0 / -1, and 0 when previous_close is missing."""
    close_value = _to_decimal(close)
    previous_value = _to_decimal(previous_close)

    if close_value is None or previous_value is None:
        return Decimal("0"), False

    if close_value > previous_value:
        return Decimal("1"), True
    if close_value < previous_value:
        return Decimal("-1"), True

    return Decimal("0"), True


def _vwap_position(close, vwap):
    """+1 when the close is above daily VWAP, -1 below, 0 if unavailable."""
    close_value = _to_decimal(close)
    vwap_value = _to_decimal(vwap)

    if close_value is None or vwap_value is None or vwap_value <= 0:
        return Decimal("0"), False

    if close_value > vwap_value:
        return Decimal("1"), True
    if close_value < vwap_value:
        return Decimal("-1"), True

    return Decimal("0"), True


def _volume_conviction(volume_ratio):
    """
    Map the volume ratio onto a 0..1 conviction weight.

    ratio <= 1.0 -> 0.0   (no more volume than usual, no conviction)
    ratio >= 1.5 -> 1.0   (at or past the anomaly threshold, full weight)
    in between   -> linear
    """
    ratio = _to_decimal(volume_ratio)

    if ratio is None or ratio <= CONVICTION_FLOOR:
        return Decimal("0"), ratio is not None

    span = CONVICTION_CEILING - CONVICTION_FLOOR
    conviction = (ratio - CONVICTION_FLOOR) / span

    return _clamp(conviction, Decimal("0"), Decimal("1")), True


def calculate_pressure(close, previous_close, vwap, volume_ratio):
    """
    Transparent OHLCV pressure proxy.

    The score is defined exactly as::

        D = price direction      -> +1 / 0 / -1   (close vs previous_close)
        V = VWAP position        -> +1 / 0 / -1   (close vs daily VWAP)
        C = volume conviction    -> 0.0 .. 1.0    (from volume_ratio)

        vwap_weight = 30, halved to 15 when D == 0

        score = 50 * D  +  vwap_weight * V  +  20 * D * C

        score in [-100, +100]

        score >= +25  -> "buying"
        score <= -25  -> "selling"
        otherwise     -> "neutral"

    Every missing input degrades to a zero contribution rather than an
    exception, so a day with no previous close, no VWAP and no volume
    history scores exactly 0 and is reported as neutral with the reasons
    recorded in the returned metadata.

    This describes the relationship between published price, published
    volume and published VWAP.  It does NOT observe order-book depth and
    must never be presented as proof of real buying or selling interest.
    """
    direction, has_previous_close = _price_direction(close, previous_close)
    vwap_signal, has_vwap = _vwap_position(close, vwap)
    conviction, has_volume_ratio = _volume_conviction(volume_ratio)

    vwap_weight = WEIGHT_VWAP
    if direction == 0:
        vwap_weight = WEIGHT_VWAP * NEUTRAL_DIRECTION_VWAP_DAMPING

    score = (
        (WEIGHT_DIRECTION * direction)
        + (vwap_weight * vwap_signal)
        + (WEIGHT_CONVICTION * direction * conviction)
    )

    score = _clamp(score, Decimal("-100"), Decimal("100"))
    score = _quantize(score, SCORE_PRECISION)

    if score >= PRESSURE_BAND:
        label = "buying"
    elif score <= -PRESSURE_BAND:
        label = "selling"
    else:
        label = "neutral"

    missing = []
    if not has_previous_close:
        missing.append("previous_close")
    if not has_vwap:
        missing.append("vwap")
    if not has_volume_ratio:
        missing.append("volume_ratio")

    return {
        "pressure": label,
        "pressure_score": score,
        "pressure_method": PRESSURE_METHOD,
        "components": {
            "price_direction": int(direction),
            "vwap_position": int(vwap_signal),
            "volume_conviction": _quantize(conviction, SCORE_PRECISION),
            "vwap_weight": vwap_weight,
        },
        "missing_inputs": missing,
        "is_complete": not missing,
    }


def calculate_daily_return_pct(close, previous_close):
    """Percentage change against the previous close, separate from VWAP."""
    close_value = _to_decimal(close)
    previous_value = _to_decimal(previous_close)

    if close_value is None or previous_value is None or previous_value <= 0:
        return None

    change = (close_value - previous_value) / previous_value * Decimal("100")
    return _quantize(change, RETURN_PRECISION)


# ---------------------------------------------------------------------
# ORCHESTRATION
# ---------------------------------------------------------------------

def _deduplicate_chronologically(prices):
    """
    Sort ascending by date and collapse duplicate dates.

    ``DailyPrice`` has a unique (company, date) constraint so duplicates
    should not reach us, but this function is also fed by tests and by
    in-memory row lists, so it defends anyway.  The last occurrence of a
    date wins, which matches ``update_or_create`` semantics upstream.
    """
    by_date = {}

    for row in prices:
        row_date = getattr(row, "date", None)
        if row_date is None:
            continue
        by_date[row_date] = row

    return [by_date[key] for key in sorted(by_date)]


def build_analysis_rows(prices):
    """
    Turn a list of ``DailyPrice``-like rows into per-day analysis dicts.

    Pure function: no database writes, no ``now()``, no randomness.  The
    same input list always produces the same output, which is what makes
    the whole analysis layer reproducible.

    A single chronological pass carries the previous close forward and
    keeps a rolling list of previous session volumes, so the baseline for
    day N only ever sees days N-1 .. N-20.
    """
    ordered = _deduplicate_chronologically(prices)

    previous_volumes = []          # most recent first
    previous_close = None
    results = []

    for row in ordered:
        close = getattr(row, "close", None)
        volume = getattr(row, "volume", None)
        turnover = getattr(row, "turnover", None)

        vwap = calculate_daily_vwap(turnover, volume)

        baseline = calculate_volume_baseline(volume, previous_volumes)

        pressure = calculate_pressure(
            close=close,
            previous_close=previous_close,
            vwap=vwap,
            volume_ratio=baseline.ratio,
        )

        results.append(
            {
                "date": row.date,
                "close_price": close,
                "volume": volume,
                "turnover": turnover,
                "vwap": vwap,
                "previous_close": previous_close,
                "daily_return_pct": calculate_daily_return_pct(
                    close,
                    previous_close,
                ),
                "volume_average": baseline.average,
                "volume_ratio": baseline.ratio,
                "volume_anomaly": baseline.anomaly,
                "volume_baseline_sessions": baseline.sessions_used,
                "has_sufficient_history": baseline.sufficient_history,
                "pressure": pressure["pressure"],
                "pressure_score": pressure["pressure_score"],
                "pressure_method": pressure["pressure_method"],
                "pressure_components": pressure["components"],
                "pressure_missing_inputs": pressure["missing_inputs"],
            }
        )

        # Advance the rolling state AFTER the row has been scored.
        previous_close = close

        volume_value = _to_decimal(volume)
        if volume_value is not None and volume_value >= 0:
            previous_volumes.insert(0, volume_value)
            del previous_volumes[BASELINE_SESSIONS:]

    return results


def rebuild_company_analysis(company, since=None, persist=True):
    """
    Recompute and store ``DailyAnalysis`` for one company.

    Always loads BASELINE_SESSIONS extra days of warm-up history before
    ``since`` so the first stored day still gets a full 20-session
    baseline instead of a truncated one.

    Returns the list of computed row dicts.  Designed to be called from
    the Celery analysis task, not from a request handler.
    """
    # Imported here to keep the pure-maths part of this module importable
    # without the Django app registry being ready.
    from apps.analysis.models import DailyAnalysis
    from apps.market_data.models import DailyPrice

    queryset = DailyPrice.objects.filter(company=company).order_by("date")

    if since is not None:
        warmup_dates = list(
            DailyPrice.objects
            .filter(company=company, date__lt=since)
            .order_by("-date")
            .values_list("date", flat=True)[:BASELINE_SESSIONS]
        )
        if warmup_dates:
            queryset = queryset.filter(date__gte=min(warmup_dates))

    prices = list(queryset)
    rows = build_analysis_rows(prices)

    if since is not None:
        stored_rows = [row for row in rows if row["date"] >= since]
    else:
        stored_rows = rows

    if not persist:
        return stored_rows

    for row in stored_rows:
        if row["close_price"] is None or row["volume"] is None:
            # close_price and volume are NOT NULL on DailyAnalysis; a row
            # this broken is skipped rather than crashing the whole pass.
            continue

        DailyAnalysis.objects.update_or_create(
            company=company,
            date=row["date"],
            defaults={
                "vwap": row["vwap"],
                "close_price": row["close_price"],
                "volume": row["volume"],
                "previous_close": row["previous_close"],
                "daily_return_pct": row["daily_return_pct"],
                "volume_average": row["volume_average"],
                "volume_ratio": row["volume_ratio"],
                "volume_anomaly": row["volume_anomaly"],
                "volume_baseline_sessions": row["volume_baseline_sessions"],
                "has_sufficient_history": row["has_sufficient_history"],
                "pressure": row["pressure"],
                "pressure_score": row["pressure_score"],
                "pressure_method": row["pressure_method"],
            },
        )

    return stored_rows
