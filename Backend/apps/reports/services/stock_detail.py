


"""
Technical indicators and quarterly financials for the Stock Detail page.

Suggested location: Backend/apps/reports/services/stock_detail.py

ASSUMPTIONS to verify against the real code (I have not seen these files):
  * apps.market_data.models.DailyPrice has company, date, open, high, low, close, volume
  * The registry's "pivots" indicator returns, for the last bar, the levels to show
    (check PP against your current page: 335.33 for NICA in the screenshot).
"""

from decimal import Decimal

from apps.market_data.models import DailyPrice
from apps.market_intelligence.indicators.registry import compute
from apps.market_intelligence.models import CompanyTechnicalSnapshot
from apps.reports.models import QuarterlyReport

HISTORY_SESSIONS = 420      # enough for EMA 180 / SMA 200 to settle
MIN_SESSIONS = 35           # same warm-up as CompanyTechnicalSnapshot RSI / MACD
QUARTERS_SHOWN = 8


# ──────────────────────────────────────────────────────────────────────────────
# Technical indicators (computed from crawled daily prices, nothing scraped)
# ──────────────────────────────────────────────────────────────────────────────

def _f(value):
    return None if value is None else float(value)


def _last(values):
    return values[-1] if values else None


def _trend_vs_price(close, ma):
    """Price above the average is Bullish, below is Bearish."""
    if ma is None or close is None:
        return None
    if close > ma:
        return "Bullish"
    if close < ma:
        return "Bearish"
    return "Neutral"


def _rsi_signal(rsi):
    if rsi is None:
        return None
    if rsi >= 70:
        return "Overbought"
    if rsi <= 30:
        return "Oversold"
    return "Neutral"


def build_technicals(company):
    # Same filter as calculate_stock_performance: real crawled prices only
    qs = (
        DailyPrice.objects.filter(company=company, source="crawled", close__gt=0)
        .order_by("-date")[:HISTORY_SESSIONS]
    )
    rows = list(reversed(list(qs)))

    if not rows:
        return {"status": "no_data", "indicators": [], "pivots": None}

    data = {
        "open": [_f(r.open) for r in rows],
        "high": [_f(r.high) for r in rows],
        "low": [_f(r.low) for r in rows],
        "close": [_f(r.close) for r in rows],
        "volume": [_f(r.volume) for r in rows],
        "date": [r.date for r in rows],
    }
    close = data["close"][-1]

    def run(indicator_id, **params):
        return compute(indicator_id, data, params)["outputs"]

    rsi = _last(run("rsi", period=14)["value"])
    macd_out = run("macd", fast=12, slow=26, signal=9)
    macd, macd_signal = _last(macd_out["macd"]), _last(macd_out["signal"])

    indicators = [
        {"key": "rsi_14", "label": "RSI (14)", "value": rsi, "signal": _rsi_signal(rsi)},
        {
            "key": "macd",
            "label": "MACD",
            "value": macd,
            "signal": (
                None if macd is None or macd_signal is None
                else "Bullish" if macd > macd_signal else "Bearish"
            ),
        },
    ]
    for ma_id, label, period in (
        ("ema", "EMA 5", 5), ("ema", "EMA 20", 20), ("ema", "EMA 180", 180),
        ("sma", "SMA 50", 50), ("sma", "SMA 200", 200),
    ):
        value = _last(run(ma_id, period=period)["value"])
        indicators.append({
            "key": label.lower().replace(" ", "_"),
            "label": label,
            "value": value,
            "signal": _trend_vs_price(close, value),
        })

    pivot_out = run("pivots", timeframe="D")
    pivots = {key: _last(pivot_out[src]) for key, src in (
        ("s3", "s3"), ("s2", "s2"), ("s1", "s1"), ("pp", "p"), ("r1", "r1"), ("r2", "r2"), ("r3", "r3"),
    )}

    snapshot = (
        CompanyTechnicalSnapshot.objects.filter(company=company).order_by("-date").first()
    )

    return {
        "status": "ok" if len(rows) >= MIN_SESSIONS else "insufficient_history",
        "as_of": rows[-1].date.isoformat(),
        "sessions": len(rows),
        "possible_corporate_action": bool(snapshot and snapshot.possible_corporate_action),
        "indicators": indicators,
        "pivots": pivots,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Quarterly financials (filed figures + per-share values derived from them)
# ──────────────────────────────────────────────────────────────────────────────

def _div(numerator, denominator):
    if numerator is None or not denominator:
        return None
    return numerator / Decimal(denominator)


def _q2(value):
    return None if value is None else value.quantize(Decimal("0.01"))


def _eps(r):
    """Annualised EPS as filed, else net profit / shares x 4 / quarter (filings are cumulative)."""
    if r.eps is not None:
        return r.eps
    per_share = _div(r.net_profit, r.share_count)
    return None if per_share is None else _q2(per_share * 4 / r.quarter)


def _book_value(r):
    return r.book_value if r.book_value is not None else _q2(_div(r.net_worth, r.share_count))


def _dpps(r):
    return r.dpps if r.dpps is not None else _q2(_div(r.distributable_profit, r.share_count))


def _prev_fiscal_year(fy):
    # Stored as "2082/2083" -> "2081/2082"
    start, end = fy.split("/")
    return f"{int(start) - 1}/{int(end) - 1}"


def _yoy_flag(current, previous):
    """Higher is better for every metric shown. None when either side is missing."""
    if current is None or previous is None:
        return None
    if current > previous:
        return "better"
    if current < previous:
        return "worse"
    return "same"


METRICS = (
    # key, label, unit, getter
    ("net_profit", "Net profit", "rs", lambda r: r.net_profit),
    ("net_worth", "Net worth", "rs", lambda r: r.net_worth),
    ("distributable_profit", "Distributable profit", "rs", lambda r: r.distributable_profit),
    ("eps", "EPS annualized (Rs.)", "per_share", _eps),
    (
    "eps",
    "EPS annualized (Rs.)",
    "per_share",
    _eps,
),
(
    "quarterly_eps",
    "Individual-quarter EPS (Rs.)",
    "per_share",
    lambda r: r.quarterly_eps,
),
    ("book_value", "Net worth / share (Rs.)", "per_share", _book_value),
    ("dpps", "Distributable profit / share (Rs.)", "per_share", _dpps),
)


def _previous_period(fiscal_year, quarter):
    """The quarter before (fiscal_year, quarter); Q1 rolls back to Q4 of the previous year."""
    if quarter > 1:
        return fiscal_year, quarter - 1
    return _prev_fiscal_year(fiscal_year), 4


# def build_financials(company):
#     by_period = {
#         (r.fiscal_year, r.quarter): r
#         for r in QuarterlyReport.objects.filter(company=company)
#     }
#     if not by_period:
#         return {"status": "no_data", "quarters": [], "rows": []}

#     # Always show 8 consecutive quarters ending at the newest filed one,
#     # so a quarter that was never filed appears as a gap instead of being skipped.
#     periods = [max(by_period)]
#     while len(periods) < QUARTERS_SHOWN:
#         periods.append(_previous_period(*periods[-1]))

#     rows = []
#     for key, label, unit, getter in METRICS:
#         cells = []
#         for fiscal_year, quarter in periods:
#             r = by_period.get((fiscal_year, quarter))
#             prior = by_period.get((_prev_fiscal_year(fiscal_year), quarter))
#             value = getter(r) if r else None
#             cells.append({
#                 "value": _f(value),
#                 "yoy": _yoy_flag(value, getter(prior) if prior else None),
#             })
#         rows.append({"key": key, "label": label, "unit": unit, "values": cells})

#     quarters = []
#     for i, (fiscal_year, quarter) in enumerate(periods):
#         r = by_period.get((fiscal_year, quarter))
#         quarters.append({
#             "fiscal_year": fiscal_year,
#             "quarter": quarter,
#             "reported_on": r.reported_on.isoformat() if r and r.reported_on else None,
#             "is_latest": i == 0,
#             "filed": r is not None,
#         })

#     return {"status": "ok", "quarters": quarters, "rows": rows}
def build_financials(company):
    by_period = {
        (r.fiscal_year, r.quarter): r
        for r in QuarterlyReport.objects.filter(company=company)
    }

    if not by_period:
        return {
            "status": "no_data",
            "quarters": [],
            "rows": [],
        }

    # Show 8 consecutive quarters ending at the newest filed quarter.
    # Missing quarters remain empty instead of being skipped.
    periods = [max(by_period)]

    while len(periods) < QUARTERS_SHOWN:
        periods.append(
            _previous_period(*periods[-1])
        )

    rows = []

    for key, label, unit, getter in METRICS:
        cells = []

        for fiscal_year, quarter in periods:
            current_report = by_period.get(
                (fiscal_year, quarter)
            )

            previous_year_report = by_period.get(
                (_prev_fiscal_year(fiscal_year), quarter)
            )

            value = (
                getter(current_report)
                if current_report
                else None
            )

            previous_value = (
                getter(previous_year_report)
                if previous_year_report
                else None
            )

            cells.append({
                "value": _f(value),
                "yoy": _yoy_flag(
                    value,
                    previous_value,
                ),
            })

        rows.append({
            "key": key,
            "label": label,
            "unit": unit,
            "values": cells,
        })

    quarters = []

    for i, (fiscal_year, quarter) in enumerate(periods):
        report = by_period.get(
            (fiscal_year, quarter)
        )

        quarters.append({
            "fiscal_year": fiscal_year,
            "quarter": quarter,
            "reported_on": (
                report.reported_on.isoformat()
                if report and report.reported_on
                else None
            ),
            "is_latest": i == 0,
            "filed": report is not None,
        })

    return {
        "status": "ok",
        "quarters": quarters,
        "rows": rows,
    }

# ──────────────────────────────────────────────────────────────────────────────
# Thin DRF views. Copy the permission / company-access handling from your existing
# /companies/<id>/performance/ view so these endpoints behave the same way.
# ──────────────────────────────────────────────────────────────────────────────
#
# from django.shortcuts import get_object_or_404
# from rest_framework.permissions import IsAuthenticated
# from rest_framework.response import Response
# from rest_framework.views import APIView
# from apps.companies.models import Company
#
# class CompanyTechnicalsView(APIView):
#     permission_classes = [IsAuthenticated]          # <- match the performance view
#     def get(self, request, pk):
#         company = get_object_or_404(Company, pk=pk)
#         return Response(build_technicals(company))
#
# class CompanyFinancialsView(APIView):
#     permission_classes = [IsAuthenticated]
#     def get(self, request, pk):
#         company = get_object_or_404(Company, pk=pk)
#         return Response(build_financials(company))
#
# urls.py:
#   path("companies/<int:pk>/technicals/", CompanyTechnicalsView.as_view()),
#   path("companies/<int:pk>/financials/", CompanyFinancialsView.as_view()),


