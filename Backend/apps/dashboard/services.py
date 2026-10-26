"""
services.py (quarterly report calculations)

Pure functions with no Django imports in the math, so they are easy to test.
Every function returns None when the result would be meaningless (shown as
"n/m" in the UI).
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Optional

# Change these to switch the window without touching any other code.
AVG_WINDOW_YEARS = 3
AVG_MIN_YEARS = 2


def _d(value) -> Optional[Decimal]:
    return None if value is None else Decimal(str(value))


def _round(value: Optional[Decimal], places: int = 2) -> Optional[Decimal]:
    return None if value is None else value.quantize(Decimal(10) ** -places)


# ---------- Price-based ratios ----------

def calc_pe(price, eps) -> Optional[Decimal]:
    """Price / EPS. n/m when EPS is zero or negative."""
    price, eps = _d(price), _d(eps)
    if price is None or eps is None or eps <= 0:
        return None
    return _round(price / eps)


def calc_pb(price, book_value) -> Optional[Decimal]:
    """Price / Book value. n/m when book value is zero or negative."""
    price, bv = _d(price), _d(book_value)
    if price is None or bv is None or bv <= 0:
        return None
    return _round(price / bv)


def calc_yield(value, price) -> Optional[Decimal]:
    """value / price * 100, used for both DPPS yield and N-year average yield."""
    value, price = _d(value), _d(price)
    if value is None or price is None or price <= 0:
        return None
    return _round(value / price * 100)


# ---------- Averages ----------

@dataclass
class AvgResult:
    average: Optional[Decimal]
    years_used: int


def n_year_average(
    yearly_values: Iterable,
    window: int = AVG_WINDOW_YEARS,
    min_years: int = AVG_MIN_YEARS,
) -> AvgResult:
    """
    Average of the most recent `window` yearly values.

    yearly_values must be ordered newest first. Years with no data (None) are
    skipped. We divide by the number of years actually used (not by `window`),
    so a company with only 2 years of history is averaged over 2. Negative
    values are kept, because they are real results.
    """
    values = [_d(v) for v in list(yearly_values)[:window] if v is not None]
    if len(values) < min_years:
        return AvgResult(None, len(values))
    return AvgResult(_round(sum(values) / len(values)), len(values))


# ---------- Year over year ----------

def calc_yoy(current, previous) -> Optional[Decimal]:
    """
    (current - previous) / |previous| * 100.
    n/m when previous is missing, zero, or negative (the percentage would mislead).
    """
    current, previous = _d(current), _d(previous)
    if current is None or previous is None or previous <= 0:
        return None
    return _round((current - previous) / abs(previous) * 100)


# ---------- Per-share from raw figures (optional) ----------

def per_share(total, share_count) -> Optional[Decimal]:
    total, shares = _d(total), _d(share_count)
    if total is None or shares is None or shares <= 0:
        return None
    return _round(total / shares)


# ---------- One table row ----------

def build_report_row(report, ltp, yearly_dpps_newest_first, previous_year_eps=None) -> dict:
    """
    Builds the dict for one row of the table.

    report: QuarterlyReport instance (or any object with the same attributes)
    ltp: current Last Traded Price
    yearly_dpps_newest_first: list of DPPS values, newest fiscal year first
    previous_year_eps: EPS of the same quarter last year, for YoY
        (change this to profit or DPPS if that is the metric you want to track)
    """
    avg = n_year_average(yearly_dpps_newest_first)
    price_for_ratios = report.price_on_report_date or ltp  # remove the fallback to always use LTP

    return {
        "symbol": report.company.symbol,
        "name": report.company.name,
        "ltp": _d(ltp),
        "eps": _d(report.eps),
        "bv": _d(report.book_value),
        "pe": calc_pe(price_for_ratios, report.eps),
        "pb": calc_pb(price_for_ratios, report.book_value),
        "dpps": _d(report.dpps),
        "dpps_yield": calc_yield(report.dpps, ltp),
        "avg_dpps": avg.average,
        "avg_years_used": avg.years_used,  # show "(2y)" in the UI when below the window
        "avg_yield": calc_yield(avg.average, ltp),
        "yoy": calc_yoy(report.eps, previous_year_eps),
    }