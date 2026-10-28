"""
Quarterly report ratios (Market -> Quarterly Report).  Pure functions, no Django imports,
so they can be tested without a database.  Every function returns None when the result
would be meaningless; the API sends null and the UI shows "n/m".

    EPS          annualized EPS as filed, else net profit / shares x 4 / quarter
    BV           book value as filed, else net worth / shares
    DPPS         as filed, else distributable profit / shares (can be negative)
    PE / PB      LTP / EPS, LTP / BV                         n/m when EPS / BV <= 0
    DPPS yield   DPPS / LTP x 100
    N-year avg   the mean of the yearly DPPS in the AVG_WINDOW_YEARS fiscal years ending at the
                 company's newest year, divided by the years present; the source's own average
                 (report.dpps_avg) is used instead only when its window matches; n/m below
                 AVG_MIN_YEARS either way
    YoY          (DPPS - same quarter last year) / |last year| x 100, n/m when last year <= 0;
                 last year as given by the source (report.previous_dpps), else last year's report
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

# The only place the averaging window is set; the API sends it so the column labels follow.
AVG_WINDOW_YEARS = 3
AVG_MIN_YEARS = 2
# nepsetrading's dpps_avg5 covers 5 years; a different window can't reuse it.
SOURCE_AVG_WINDOW_YEARS = 5

QUARTERS = (1, 2, 3, 4)
HUNDRED = Decimal(100)


def _d(value):
    return None if value is None or value == "" else Decimal(str(value))


def _round(value, places=2):
    return None if value is None else value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def fiscal_year_start(fiscal_year):
    """'2082/2083' -> 2082."""
    return int(str(fiscal_year).split("/")[0])


def previous_fiscal_year(fiscal_year):
    start = fiscal_year_start(fiscal_year)
    return f"{start - 1}/{start}"


# ---------- Price-based ratios ----------

def calc_pe(price, eps):
    """Price / EPS; n/m when EPS is zero or negative."""
    price, eps = _d(price), _d(eps)
    if price is None or eps is None or eps <= 0:
        return None
    return _round(price / eps)


def calc_pb(price, book_value):
    """Price / book value; n/m when book value is zero or negative."""
    price, bv = _d(price), _d(book_value)
    if price is None or bv is None or bv <= 0:
        return None
    return _round(price / bv)


def calc_yield(value, price):
    """value / price x 100, for the DPPS yield and the N-year average yield."""
    value, price = _d(value), _d(price)
    if value is None or price is None or price <= 0:
        return None
    return _round(value / price * HUNDRED)


# ---------- Averages ----------

@dataclass
class AvgResult:
    average: Decimal | None
    years_used: int


def n_year_average(yearly_values, window=AVG_WINDOW_YEARS, min_years=AVG_MIN_YEARS):
    """
    Mean of the newest ``window`` slots of ``yearly_values`` (newest first, None = no data
    for that year).  Divides by the years actually present, not by ``window``; negative
    years are real results and are kept.  n/m below ``min_years``.
    """
    values = [_d(v) for v in list(yearly_values)[:window] if v is not None]
    if len(values) < min_years:
        return AvgResult(None, len(values))
    return AvgResult(_round(sum(values) / len(values)), len(values))


def dpps_window(dpps_by_year, as_of_fiscal_year, window=AVG_WINDOW_YEARS):
    """
    Yearly DPPS for the ``window`` fiscal years ending at the newest year on file that is
    not after ``as_of_fiscal_year``, newest first, None for a missing year.  Anchoring on
    the newest year on file keeps Q1-Q3 (no full-year DPPS yet) from dropping a year.
    """
    limit = fiscal_year_start(as_of_fiscal_year)
    starts = {fiscal_year_start(fy): value for fy, value in dpps_by_year.items() if fiscal_year_start(fy) <= limit}
    if not starts:
        return []
    newest = max(starts)
    return [starts.get(newest - offset) for offset in range(window)]


# ---------- Year over year ----------

def calc_yoy(current, previous):
    """(current - previous) / |previous| x 100; n/m when previous is missing, zero or negative."""
    current, previous = _d(current), _d(previous)
    if current is None or previous is None or previous <= 0:
        return None
    return _round((current - previous) / abs(previous) * HUNDRED)


# ---------- Per-share figures ----------

def per_share(total, share_count):
    total, shares = _d(total), _d(share_count)
    if total is None or shares is None or shares <= 0:
        return None
    return _round(total / shares)


def report_eps(report):
    """Annualized EPS as filed, else cumulative net profit / shares scaled to a full year."""
    if report.eps is not None:
        return _d(report.eps)
    eps = per_share(report.net_profit, report.share_count)
    return None if eps is None or report.quarter not in QUARTERS else _round(eps * 4 / report.quarter)


def report_book_value(report):
    return _d(report.book_value) if report.book_value is not None else per_share(report.net_worth, report.share_count)


def report_dpps(report):
    return _d(report.dpps) if report.dpps is not None else per_share(report.distributable_profit, report.share_count)


# ---------- One table row ----------

def build_report_row(report, ltp, dpps_by_year, previous_report=None):
    """
    One table row.

    report           a QuarterlyReport (or any object with its attributes and ``company``)
    ltp              latest price, or None
    dpps_by_year     {fiscal_year: yearly DPPS} for this company
    previous_report  the same quarter of the previous fiscal year, for YoY on DPPS
    """
    ltp = _d(ltp)
    eps, bv, dpps = report_eps(report), report_book_value(report), report_dpps(report)
    if report.previous_dpps is not None:
        previous_dpps = _d(report.previous_dpps)
    else:
        previous_dpps = report_dpps(previous_report) if previous_report is not None else None
    if report.dpps_avg is not None and AVG_WINDOW_YEARS == SOURCE_AVG_WINDOW_YEARS:
        years = report.dpps_avg_years or AVG_WINDOW_YEARS
        avg = AvgResult(_round(_d(report.dpps_avg)) if years >= AVG_MIN_YEARS else None, years)
    else:
        avg = n_year_average(dpps_window(dpps_by_year, report.fiscal_year))

    return {
        "symbol": report.company.symbol,
        "name": report.company.name,
        "reported_on": report.reported_on,
        "ltp": ltp,
        "eps": eps,
        "bv": bv,
        "pe": calc_pe(ltp, eps),
        "pb": calc_pb(ltp, bv),
        "dpps": dpps,
        "dpps_yield": calc_yield(dpps, ltp),
        "avg_dpps": avg.average,
        "avg_years_used": avg.years_used,
        "avg_yield": calc_yield(avg.average, ltp),
        "previous_dpps": previous_dpps,
        "yoy": calc_yoy(dpps, previous_dpps),
    }
