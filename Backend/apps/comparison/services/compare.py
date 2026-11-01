"""
Side-by-side profile of tracked companies, built only from stored data.

One code path serves every tracked company.  A figure that cannot be computed is
``None`` and listed in ``data_quality.null_fields`` with a reason code; it is
never 0 and never estimated.  A company whose profile raises is returned as an
error entry so the other companies still come back.

Sources (see docs/features/stock-comparison.md for the formulas):
    prices      DailyPrice (crawled) via market_data.services.movers for the session change
    shares      Company.listed_shares (QuarterlyReport.share_count is empty)
    fundamentals the latest QuarterlyReport; CompanyEarnings is not used
    dividends   DividendAnnouncement, by company and then by symbol
    technicals  the latest CompanyTechnicalSnapshot
    brokers     FloorsheetTransaction for one session
"""

import logging
from datetime import time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Max, Min, Q, Sum
from django.utils import timezone

from apps.analysis.services.brokers import _base_queryset
from apps.floorsheet.models import Broker, FloorsheetTransaction
from apps.market_data.models import DailyPrice
from apps.market_data.services.market_stats import tracked_companies
from apps.market_data.services.movers import company_rows
from apps.market_data.services.price_adjustments import adjustment_sessions
from apps.market_data.services.trading_days import is_market_day
from apps.market_intelligence.models import CompanyTechnicalSnapshot
from apps.market_intelligence.services.momentum import MIN_SESSIONS
from apps.reports.models import DividendAnnouncement, QuarterlyReport

logger = logging.getLogger(__name__)

MIN_SYMBOLS, MAX_SYMBOLS = 2, 5
DEFAULT_FACE_VALUE = Decimal("100")
TREND_DAYS = 90
WEEK52_DAYS = 365
VOLUME_SESSIONS = 10
TOP_BROKERS = 5
# A raw close series that spans an unadjusted book closure distorts any indicator
# whose lookback reaches it.  RSI(14) / MACD(26, 9) smoothing fades after ~50 sessions.
LOOKBACK_SESSIONS = {"technicals.rsi": 50, "technicals.macd_label": 50, "technicals.sma50": 50, "technicals.sma200": 200}
# Leverage and asset-based ratios of banks, finance companies and insurers are
# structurally different from hydro, telecom or manufacturing companies.
FINANCIAL_SECTORS = {
    "commercial bank", "development bank", "finance", "microfinance",
    "life insurance", "non life insurance",
}

# The 18:00 NPT price-crawl chain (crawl_daily_prices) has normally stored the day's closes by then.
EVENING_CRAWL_DONE = time(18, 30)

TWO = Decimal("0.01")


def expected_latest_session(now=None):
    """
    Latest session whose crawled close should be stored by now: today once the
    evening price crawl has run, else the previous market day.  Holidays come from
    TradingHoliday, so an unentered holiday reads as a missed session.
    """
    now = timezone.localtime(now)
    day = now.date()
    if not (is_market_day(day) and now.time() >= EVENING_CRAWL_DONE):
        day -= timedelta(days=1)
        while not is_market_day(day):
            day -= timedelta(days=1)
    return day


class ComparisonError(ValueError):
    """A request the comparison cannot serve; ``code`` is machine-readable."""

    def __init__(self, code, message, **details):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


def _q(value, places=TWO):
    """Round for display; None stays None."""
    return value.quantize(places, rounding=ROUND_HALF_UP) if value is not None else None


def parse_symbols(raw):
    """Upper-cased symbols from ``?symbols=``, validated against the tracked companies."""
    symbols = [part.strip().upper() for part in (raw or "").split(",") if part.strip()]
    if not symbols:
        raise ComparisonError("symbols_required", "Pass ?symbols=A,B with 2 to 5 tracked symbols.")
    duplicates = sorted({s for s in symbols if symbols.count(s) > 1})
    if duplicates:
        raise ComparisonError("duplicate_symbols", f"Duplicate symbols: {', '.join(duplicates)}.",
                              duplicate_symbols=duplicates)
    if not MIN_SYMBOLS <= len(symbols) <= MAX_SYMBOLS:
        raise ComparisonError("symbol_count", f"Compare {MIN_SYMBOLS} to {MAX_SYMBOLS} symbols; got {len(symbols)}.")
    companies = {c.symbol: c for c in tracked_companies().filter(symbol__in=symbols)}
    unknown = [s for s in symbols if s not in companies]
    if unknown:
        raise ComparisonError(
            "unknown_symbols",
            f"Not a tracked company: {', '.join(unknown)}. Only the tracked companies can be compared.",
            invalid_symbols=unknown,
        )
    return [companies[s] for s in symbols]


def previous_fiscal_year(fiscal_year):
    """'2083/2084' -> '2082/2083'; None when the format is not YYYY/YYYY."""
    try:
        start, end = (int(part) for part in fiscal_year.split("/"))
    except (AttributeError, ValueError):
        return None
    return f"{start - 1}/{end - 1}"


def ttm_eps(company, report):
    """
    (value, reason).  Filed EPS is annualized and cumulative within the fiscal year,
    so at Q4 it is the annual EPS.  For Q1-Q3 the trailing figure needs last year's
    Q4 and same quarter:  cum(n) = eps * n / 4;  TTM = cum_now(n) + cum_prev(4) - cum_prev(n).
    """
    if report is None:
        return None, "no_data"
    if report.eps is None:
        return None, "no_data"
    if report.quarter == 4:
        return report.eps, None
    prior_year = previous_fiscal_year(report.fiscal_year)
    prior = {
        r.quarter: r.eps for r in QuarterlyReport.objects.filter(
            company=company, fiscal_year=prior_year, quarter__in=(4, report.quarter), eps__isnull=False,
        )
    }
    if 4 not in prior or report.quarter not in prior:
        return None, "needs_more_quarterly_data"
    n = Decimal(report.quarter) / 4
    return report.eps * n + prior[4] - prior[report.quarter] * n, None


class _Profile:
    def __init__(self):
        self.sections = {"general": {}, "fundamentals": {}, "technicals": {}}
        self.null_fields = []
        self.warnings = []

    def put(self, section, field, value, reason=None, note=None):
        self.sections[section][field] = value
        if value is None:
            entry = {"field": f"{section}.{field}", "reason": reason or "no_data"}
            if note:
                entry["note"] = note
            self.null_fields.append(entry)
        return value

    def warn(self, code, detail, **extra):
        self.warnings.append({"code": code, "detail": detail, **extra})


def _price_block(profile, company):
    prices = DailyPrice.objects.filter(company=company, source="crawled")
    latest = prices.order_by("-date").first()
    if latest is None:
        # Only fallback the spec allows: the live feed's last trade, labelled as such.
        ltp, prev = company.ltp, company.previous_close
        change = (ltp - prev) / prev * 100 if ltp is not None and prev else None
        profile.put("general", "ltp", ltp, "no_data")
        profile.put("general", "ltp_source", "company_live_feed" if ltp is not None else None, "no_data")
        profile.put("general", "previous_close", prev, "no_data")
        profile.put("general", "change_pct", _q(change), "no_data")
        if ltp is not None:
            profile.warn("ltp_from_live_feed", "No crawled DailyPrice; ltp is Company.ltp from the intraday feed.",
                         prices_updated_at=company.prices_updated_at)
        for field in ("price_trend_3m", "week52_low", "week52_high"):
            profile.put("general", field, None, "no_data")
        profile.put("technicals", "volume_trend", None, "no_data")
        return None, ltp

    _, rows = company_rows([company.id], requested_date=latest.date)
    row = rows.get(company.id) or {}
    profile.put("general", "ltp", latest.close)
    profile.put("general", "ltp_source", "daily_price")
    profile.put("general", "previous_close", row.get("prev_close"), row.get("bucket") or "no_data")
    profile.put("general", "change_pct", _q(row.get("change_pct")), row.get("bucket") or "no_data")
    if row.get("adjusted"):
        profile.warn("previous_close_adjusted",
                     "Session change uses the exchange's adjusted previous close (book closure).")

    trend = list(prices.filter(date__gte=latest.date - timedelta(days=TREND_DAYS))
                 .order_by("date").values("date", "close"))
    profile.put("general", "price_trend_3m", trend or None, "no_data")

    first_date = prices.aggregate(first=Min("date"))["first"]
    if first_date > latest.date - timedelta(days=WEEK52_DAYS):
        profile.put("general", "week52_low", None, "insufficient_history")
        profile.put("general", "week52_high", None, "insufficient_history")
    else:
        window = prices.filter(date__gt=latest.date - timedelta(days=WEEK52_DAYS)).aggregate(low=Min("low"), high=Max("high"))
        profile.put("general", "week52_low", window["low"])
        profile.put("general", "week52_high", window["high"])

    volumes = list(prices.order_by("-date").values("date", "volume")[:VOLUME_SESSIONS])[::-1]
    profile.put("technicals", "volume_trend", volumes or None, "no_data")
    return latest.date, latest.close


def _face_value(company):
    fv = (DividendAnnouncement.objects
          .filter(Q(company=company) | Q(company__isnull=True, symbol=company.symbol), face_value__isnull=False)
          .order_by("-fiscal_year").values_list("face_value", flat=True).first())
    return (fv, "dividend_announcement") if fv is not None else (DEFAULT_FACE_VALUE, "default_100")


def _latest_dividend(company):
    return (DividendAnnouncement.objects
            .filter(Q(company=company) | Q(company__isnull=True, symbol=company.symbol))
            .exclude(fiscal_year="")
            .order_by("-fiscal_year").first())


def _brokers(company, requested_date):
    """(date, buy rows, sell rows) for one session; synthetic TX- rows excluded."""
    day = requested_date or (FloorsheetTransaction.objects.filter(company=company)
                             .aggregate(d=Max("date"))["d"])
    if day is None:
        return None, None, None
    queryset = _base_queryset(company=company, date=day)
    total = queryset.aggregate(q=Sum("quantity"))["q"]
    if not total:
        return day, None, None
    sides = {}
    for side, field in (("buy", "_buyer_broker_clean"), ("sell", "_seller_broker_clean")):
        sides[side] = list(queryset.exclude(**{field: ""}).values(field)
                           .annotate(qty=Sum("quantity")).order_by("-qty", field)[:TOP_BROKERS])
    numbers = {int(r[f]) for side, f in (("buy", "_buyer_broker_clean"), ("sell", "_seller_broker_clean"))
               for r in sides[side] if str(r[f]).isdigit()}
    names = dict(Broker.objects.filter(broker_no__in=numbers).values_list("broker_no", "name"))

    def shape(rows, field):
        out = []
        for r in rows:
            number = int(r[field]) if str(r[field]).isdigit() else None
            out.append({
                "broker_no": number if number is not None else r[field],
                "broker_name": names.get(number),
                "quantity": r["qty"],
                "pct_of_day_volume": _q(Decimal(r["qty"]) * 100 / Decimal(total)),
            })
        return out

    return day, shape(sides["buy"], "_buyer_broker_clean"), shape(sides["sell"], "_seller_broker_clean")


def company_profile(company, adjustments=None, broker_date=None):
    profile = _Profile()
    adjustments = adjustments or []
    financial = company.sector.strip().lower() in FINANCIAL_SECTORS

    price_date, ltp = _price_block(profile, company)
    expected = expected_latest_session()
    if price_date is not None and price_date < expected:
        profile.warn("stale_price", f"Latest crawled close is {price_date}; the {expected} session is missing.")

    # ---- size: listed shares, paid-up, reserve ----
    shares = company.listed_shares
    face_value, face_value_source = _face_value(company)
    if face_value_source == "default_100":
        profile.warn("face_value_assumed", "No face value in DividendAnnouncement; using the NEPSE default of 100.")
    report = QuarterlyReport.objects.filter(company=company).order_by("-fiscal_year", "-quarter").first()
    book_value = report.book_value if report else None
    bv_reason = "no_data" if report is None or book_value is None else None

    g = "general"
    profile.put(g, "listed_shares", shares, "no_data")
    profile.put(g, "face_value", face_value)
    profile.put(g, "face_value_source", face_value_source)
    profile.put(g, "market_cap", _q(ltp * shares) if ltp is not None and shares else None,
                "no_data" if shares is None else "no_price")
    paid_up = Decimal(shares) * face_value if shares else None
    profile.put(g, "paid_up_capital", _q(paid_up), "no_data")
    reserve = book_value * shares - paid_up if book_value is not None and shares else None
    profile.put(g, "reserve_surplus", _q(reserve), bv_reason or "no_data")

    eps, eps_reason = ttm_eps(company, report)
    profile.put(g, "eps_ttm", eps, eps_reason)
    profile.put(g, "eps_reported", report.eps if report else None, "no_data")
    profile.put(g, "eps_reported_flag", "same_as_ttm_until_quarterly_history_backfilled" if report else None, "no_data")
    if report and report.quarter != 4:
        profile.warn("eps_reported_annualized",
                     f"Latest report is {report.fiscal_year} Q{report.quarter}; its EPS is annualized as filed, not trailing.")

    buy_date, buys, sells = _brokers(company, broker_date)
    profile.put(g, "brokers_date", buy_date, "no_data")
    profile.put(g, "top_buy_brokers", buys, "no_data")
    profile.put(g, "top_sell_brokers", sells, "no_data")
    if buy_date and price_date and buy_date != price_date and broker_date is None:
        profile.warn("brokers_date_differs", f"Floorsheet is for {buy_date}; prices are for {price_date}.")

    # ---- fundamentals ----
    f = "fundamentals"
    profile.put(f, "report_period", f"{report.fiscal_year} Q{report.quarter}" if report else None, "no_data")
    if eps is None or ltp is None:
        profile.put(f, "pe", None, eps_reason if eps is None else "no_price")
    elif eps <= 0:
        profile.put(f, "pe", None, "negative_eps")
    else:
        profile.put(f, "pe", _q(ltp / eps))
    if book_value is None or ltp is None:
        profile.put(f, "pb", None, bv_reason or "no_price")
    elif book_value <= 0:
        profile.put(f, "pb", None, "non_positive_book_value")
    else:
        profile.put(f, "pb", _q(ltp / book_value))
    if eps is None or book_value is None:
        profile.put(f, "roe", None, eps_reason if eps is None else bv_reason)
    elif book_value <= 0:
        profile.put(f, "roe", None, "non_positive_book_value")
    else:
        profile.put(f, "roe", _q(eps / book_value * 100))

    dividend = _latest_dividend(company)
    if dividend is None:
        profile.put(f, "dividend", None, "no_dividend_history")
        profile.put(f, "dividend_yield", None, "no_dividend_history")
    else:
        total = dividend.cash_pct + dividend.bonus_pct
        profile.put(f, "dividend", {
            "fiscal_year": dividend.fiscal_year, "cash_pct": dividend.cash_pct,
            "bonus_pct": dividend.bonus_pct, "total_pct": total,
            "status": dividend.status, "book_closure_date": dividend.book_closure_date,
        })
        if ltp is None or ltp <= 0:
            profile.put(f, "dividend_yield", None, "no_price")
        else:
            profile.put(f, "dividend_yield", _q(total * face_value / 100 / ltp * 100))
        profile.put(f, "dividend_yield_basis", "cash_plus_bonus_at_face_value")

    for field in ("yoy_profit_growth", "earning_trend_5q", "peg"):
        profile.put(f, field, None, "needs_more_quarterly_data")
    sector_note = ("Banks, finance companies and insurers carry deposits / policy liabilities, so D/E and ROA "
                   "are not comparable with hydro, telecom or manufacturing companies.") if financial else None
    for field in ("ps", "roa", "debt_equity"):
        profile.put(f, field, None, "no_source_column", note=sector_note if field != "ps" else None)

    # ---- technicals ----
    t = "technicals"
    snapshot = CompanyTechnicalSnapshot.objects.filter(company=company).order_by("-date").first()
    if snapshot is None:
        for field in ("rsi", "macd", "macd_signal", "macd_hist", "macd_label", "sma50", "sma200"):
            profile.put(t, field, None, "no_data")
    else:
        if snapshot.history_sessions < MIN_SESSIONS:
            momentum_reason = "insufficient_history"
        elif snapshot.possible_corporate_action:
            momentum_reason = "possible_corporate_action"
        else:
            momentum_reason = "not_computed"
        rsi_reason = "no_price_movement" if snapshot.rsi_14 is None and snapshot.macd is not None else momentum_reason
        profile.put(t, "rsi", snapshot.rsi_14, rsi_reason)
        profile.put(t, "macd", snapshot.macd, momentum_reason)
        profile.put(t, "macd_signal", snapshot.macd_signal, momentum_reason)
        profile.put(t, "macd_hist", snapshot.macd_hist, momentum_reason)
        label = None
        if snapshot.macd is not None and snapshot.macd_signal is not None:
            label = "Bullish" if snapshot.macd > snapshot.macd_signal else "Bearish"
        profile.put(t, "macd_label", label, momentum_reason)
        # The snapshot leaves DMAs empty on a flagged day and before 50 / 200 sessions.
        dma_reason = "possible_corporate_action" if snapshot.possible_corporate_action else "insufficient_history"
        for field, value in (("sma50", snapshot.dma_50), ("sma200", snapshot.dma_200)):
            block = {"value": value, "above": ltp > value} if value is not None and ltp is not None else None
            profile.put(t, field, block, dma_reason if value is None else "no_price")
        if price_date and snapshot.date != price_date:
            profile.warn("snapshot_behind_price", f"Snapshot is for {snapshot.date}; prices are for {price_date}.")

    # ---- unadjusted bonus / right sessions inside a lookback ----
    if adjustments and price_date:
        recent = list(DailyPrice.objects.filter(company=company, source="crawled", date__lte=price_date)
                      .order_by("-date").values_list("date", flat=True)[:max(LOOKBACK_SESSIONS.values())])
        affected = {}
        for event in adjustments:
            fields = [name for name, n in LOOKBACK_SESSIONS.items() if event["date"] in recent[:n]]
            if event["date"] > price_date - timedelta(days=WEEK52_DAYS):
                fields += ["general.week52_low", "general.week52_high"]
            if fields:
                affected[event["date"]] = fields
        if affected:
            profile.warn(
                "unadjusted_price_adjustment",
                "Prices are not adjusted for bonus / right shares; these fields span a book closure.",
                sessions=[{"date": day, "fields": fields} for day, fields in sorted(affected.items())],
            )

    return {
        "symbol": company.symbol,
        "name": company.name,
        "sector": company.sector,
        **profile.sections,
        "data_quality": {
            "price_as_of": price_date,
            "expected_latest_session": expected,
            "snapshot_as_of": snapshot.date if snapshot else None,
            "report_period": profile.sections["fundamentals"]["report_period"],
            "brokers_as_of": profile.sections["general"]["brokers_date"],
            "null_fields": profile.null_fields,
            "warnings": profile.warnings,
            "price_adjustment_sessions": adjustments,
        },
    }


def compare_companies(companies, broker_date=None):
    """One profile per company, in the order given; a failing company becomes an error entry."""
    adjustments = adjustment_sessions([c.id for c in companies])
    results = []
    for company in companies:
        try:
            results.append(company_profile(company, adjustments.get(company.id, []), broker_date))
        except Exception:
            logger.exception("Comparison profile failed for %s", company.symbol)
            results.append({
                "symbol": company.symbol, "name": company.name, "sector": company.sector,
                "error": "computation_failed",
                "detail": "This company's profile could not be built; the others are unaffected.",
            })
    return results
