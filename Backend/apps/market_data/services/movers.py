"""
Tracked-company movers: the ONE definition of a session's change, used by
/api/market/movers/, /api/market/summary/, the top lists, the watchlist, the
landing page and the Tracked Companies page.

SCOPE: active tracked companies, ``DailyPrice.source == "crawled"`` only.
Never describes the whole NEPSE market.

Sessions (apps.market_data.services.trading_calendar)
    as_of      latest stored trading date <= the requested date (default: the
               latest date with crawled prices).  If today's crawl has not
               landed, this is the last completed trading day.
    base date  the trading date N sessions before as_of (N = 1, 5 or 20).
               Weekends and holidays have no rows, so they are skipped
               automatically; nothing counts calendar days.

Per company
    close            DailyPrice.close on as_of
    raw_prev_close   DailyPrice.close on the base date -- that exact date must
                     exist for the company, otherwise the row is excluded.
    close_to_close_change_pct = (close - raw_prev_close) * 100 / raw_prev_close
    change_pct
        1 session : DailyPrice.source_change_pct (ShareSansar's own % change,
                    measured against the exchange's ADJUSTED previous close)
                    when stored; otherwise close_to_close_change_pct.
        N sessions: the source % changes compounded over the N sessions when
                    every one of them is stored; otherwise close-to-close
                    (marked unadjusted).
    prev_close       raw_prev_close, except on adjusted rows where it is the
                     exchange's adjusted reference implied by the source %:
                     close / (1 + change_pct / 100).
    change           close - prev_close
    adjusted         source basis and |change_pct - close_to_close| > 0.05
                     (e.g. a bonus-share book closure).
    unadjusted       close-to-close basis (no source % for the whole period).

Buckets (every tracked company lands in exactly one)
    not_traded                 no row on as_of, or volume 0
    missing_previous_session   no row on the base date
    prev_close_zero            raw_prev_close is 0
    possible_corporate_action  close-to-close basis and |change| > 10%: with no
                               source % and no corporate-action data, such a
                               move cannot be told apart from a price
                               adjustment, so it is not ranked.
    gainer / loser / unchanged change_pct > 0 / < 0 / == 0.  Exactly zero, the
                               same rule MarketBreadthSnapshot uses (no
                               tolerance band).

    gainers + losers + unchanged + sum(excluded counts) == tracked_count
"""

from datetime import timedelta
from decimal import Decimal

from django.db.models import (
    BooleanField,
    Case,
    CharField,
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    FloatField,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
    When,
    Window,
)
from django.db.models.functions import Abs, Cast, Coalesce, Exp, Ln, RowNumber

from apps.crawler_runs.models import CrawlRun
from apps.market_data.models import DailyPrice
from apps.market_data.services.trading_calendar import latest_trading_date, previous_trading_sessions
from apps.market_data.services.market_stats import PRICE_SOURCE, tracked_companies


PERIODS = {
    "1D": {"sessions": 1, "label": "1 session"},
    "5S": {"sessions": 5, "label": "5 sessions"},
    "20S": {"sessions": 20, "label": "20 sessions"},
}
PERIOD_ALIASES = {"1W": "5S", "1M": "20S"}

ADJUSTMENT_TOLERANCE_PCT = Decimal("0.05")
CORPORATE_ACTION_PCT = Decimal("10")
CIRCUIT_THRESHOLD_PCT = Decimal("9.9")
SPARKLINE_SESSIONS = 7

RANKED = ("gainer", "loser", "unchanged")
EXCLUSION_REASONS = ("not_traded", "missing_previous_session", "prev_close_zero", "possible_corporate_action")

PCT = DecimalField(max_digits=24, decimal_places=6)
# Percentages are computed in double precision and cast back to numeric(24,6):
# SQLite keeps whole-number decimals as integers and would integer-divide.
FLOAT = FloatField()
ONE = Value(1.0, output_field=FLOAT)
HUNDRED = Value(100.0, output_field=FLOAT)


def _float(name):
    return Cast(F(name), FLOAT)
PRICE = DecimalField(max_digits=15, decimal_places=2)
MONEY = DecimalField(max_digits=18, decimal_places=2)

NO_DATA_ACTION = (
    "Run the price crawl: `cd Backend/crawlers && scrapy crawl trading_data` "
    "(or the 18:00 crawl_daily_prices task)."
)

ROW_FIELDS = (
    "company_id", "symbol", "name", "sector", "bucket",
    "close", "prev_close", "change", "change_pct",
    "raw_prev_close", "close_to_close_change_pct", "change_basis", "adjusted", "unadjusted",
    "possible_corporate_action", "volume", "turnover", "transactions", "price_source",
)


def normalize_period(value):
    key = (value or "1D").strip().upper()
    key = PERIOD_ALIASES.get(key, key)
    return key if key in PERIODS else None


def resolve_sessions(requested_date=None, sessions=1):
    """(as_of, base_date, window_dates) from the crawled trading calendar; any part may be None."""
    if requested_date is None:
        as_of = latest_trading_date()
    else:
        latest = previous_trading_sessions(requested_date + timedelta(days=1), 1)
        as_of = latest[0] if latest else None
    if as_of is None:
        return None, None, []

    earlier = previous_trading_sessions(as_of, sessions)
    base_date = earlier[-1] if len(earlier) == sessions else None
    window_dates = [as_of] + earlier[: sessions - 1]   # the N sessions after base_date
    return as_of, base_date, window_dates


def annotated_companies(as_of, base_date, window_dates, company_ids=None):
    """Tracked companies annotated with the period's prices, change and bucket (SQL only)."""
    sessions = len(window_dates)
    prices = DailyPrice.objects.filter(company=OuterRef("pk"), source=PRICE_SOURCE)
    today = prices.filter(date=as_of)

    def today_value(field, output_field):
        return Subquery(today.values(field)[:1], output_field=output_field)

    companies = tracked_companies(company_ids).annotate(
        close=today_value("close", PRICE),
        volume=today_value("volume", IntegerField()),
        turnover=today_value("turnover", MONEY),
        transactions=today_value("transactions", IntegerField()),
        price_source=today_value("source", CharField()),
        source_pct_today=today_value("source_change_pct", PCT),
        raw_prev_close=(
            Subquery(prices.filter(date=base_date).values("close")[:1], output_field=PRICE)
            if base_date else Value(None, output_field=PRICE)
        ),
    )

    window = prices.filter(date__in=window_dates, source_change_pct__isnull=False).order_by().values("company")
    companies = companies.annotate(
        window_known=Coalesce(
            Subquery(window.annotate(n=Count("id")).values("n")[:1], output_field=IntegerField()),
            Value(0),
        ),
        window_log=Subquery(
            window.annotate(s=Sum(Ln(ONE + _float("source_change_pct") / HUNDRED))).values("s")[:1],
            output_field=FLOAT,
        ),
        close_to_close_change_pct=Case(
            When(raw_prev_close__gt=0, close__isnull=False, then=Cast(
                (_float("close") - _float("raw_prev_close")) * HUNDRED / _float("raw_prev_close"), PCT)),
            default=Value(None),
            output_field=PCT,
        ),
    )

    if sessions == 1:
        has_source = Q(source_pct_today__isnull=False)
        source_pct = F("source_pct_today")
    else:
        has_source = Q(window_known=sessions)
        source_pct = Cast((Exp(F("window_log")) - ONE) * HUNDRED, PCT)

    companies = companies.annotate(
        change_basis=Case(When(has_source, then=Value("source")), default=Value("close_to_close"), output_field=CharField()),
        change_pct=Case(When(has_source, then=source_pct), default=F("close_to_close_change_pct"), output_field=PCT),
    ).annotate(
        basis_gap=Abs(F("change_pct") - F("close_to_close_change_pct")),
        prev_close=Case(
            # The stored close unless the source % reflects an adjustment; the
            # source % is rounded to 2 decimals, so implying a price from it
            # would be slightly off for ordinary sessions.
            When(change_basis="close_to_close", then=F("raw_prev_close")),
            When(basis_gap__lte=ADJUSTMENT_TOLERANCE_PCT, then=F("raw_prev_close")),
            When(change_pct__isnull=False, close__isnull=False, then=Cast(
                _float("close") * HUNDRED / (HUNDRED + _float("change_pct")), PCT)),
            default=Value(None),
            output_field=PCT,
        ),
    ).annotate(
        change=ExpressionWrapper(F("close") - F("prev_close"), output_field=PCT),
        adjusted=Case(
            When(change_basis="source", basis_gap__gt=ADJUSTMENT_TOLERANCE_PCT, then=Value(True)),
            default=Value(False),
            output_field=BooleanField(),
        ),
        unadjusted=Case(When(change_basis="close_to_close", then=Value(True)), default=Value(False), output_field=BooleanField()),
        bucket=Case(
            When(Q(close__isnull=True) | Q(volume__isnull=True) | Q(volume=0), then=Value("not_traded")),
            When(raw_prev_close__isnull=True, then=Value("missing_previous_session")),
            When(raw_prev_close__lte=0, then=Value("prev_close_zero")),
            When(
                Q(change_basis="close_to_close")
                & (Q(close_to_close_change_pct__gt=CORPORATE_ACTION_PCT) | Q(close_to_close_change_pct__lt=-CORPORATE_ACTION_PCT)),
                then=Value("possible_corporate_action"),
            ),
            When(change_pct__gt=0, then=Value("gainer")),
            When(change_pct__lt=0, then=Value("loser")),
            default=Value("unchanged"),
            output_field=CharField(),
        ),
    ).annotate(
        possible_corporate_action=Case(
            When(bucket="possible_corporate_action", then=Value(True)),
            default=Value(False),
            output_field=BooleanField(),
        ),
    )
    return companies


def _rows(queryset):
    return list(queryset.values(*ROW_FIELDS[1:], company_id=F("id")))


def _attach_sparklines(rows, as_of):
    """Last 7 crawled closes (<= as_of) for every listed company, in one windowed query."""
    company_ids = [row["company_id"] for row in rows]
    recent = (
        DailyPrice.objects
        .filter(source=PRICE_SOURCE, company_id__in=company_ids, date__lte=as_of)
        .annotate(position=Window(RowNumber(), partition_by=[F("company_id")], order_by=F("date").desc()))
        .filter(position__lte=SPARKLINE_SESSIONS)
        .order_by("company_id", "date")
        .values_list("company_id", "date", "close")
    )
    by_company = {}
    for company_id, day, close in recent:
        by_company.setdefault(company_id, []).append({"date": day, "close": close})
    for row in rows:
        row["sparkline"] = by_company.get(row["company_id"], [])
    return rows


def provenance():
    """Where the numbers come from: the table, the source value, and the last price crawl."""
    last_crawl = (
        CrawlRun.objects
        .filter(crawl_type=CrawlRun.CrawlType.TRADING, source="trading_data", status=CrawlRun.Status.SUCCESS)
        .order_by("-completed_at")
        .values("id", "status", "started_at", "completed_at")
        .first()
    )
    # A standalone `scrapy crawl trading_data` is recorded by CrawlRunPipeline with the default
    # crawl_type, so the latest crawled trade date is reported too, straight from the table.
    return {
        "table": DailyPrice._meta.db_table,
        "price_source": PRICE_SOURCE,
        "change_source": "ShareSansar company-price-history (per_change), else close-to-close",
        "latest_crawled_trade_date": latest_trading_date(),
        "last_price_crawl": last_crawl,
    }


def tracked_movers(period="1D", requested_date=None, company_ids=None, limit=5):
    """Gainers / losers / unchanged / excluded for the tracked companies."""
    period = normalize_period(period) or "1D"
    sessions = PERIODS[period]["sessions"]
    as_of, base_date, window_dates = resolve_sessions(requested_date, sessions)

    result = {
        "as_of": as_of,
        "period": period,
        "period_label": PERIODS[period]["label"],
        "base_date": base_date,
        "gainers": [],
        "losers": [],
        "unchanged": [],
        "excluded": [],
        "provenance": provenance(),
    }
    if as_of is None:
        return {
            **result,
            "tracked_count": tracked_companies(company_ids).count(),
            "reason": "no completed trading day in DailyPrice (source=crawled)",
            "action": NO_DATA_ACTION,
        }

    companies = annotated_companies(as_of, base_date, window_dates, company_ids)
    counts = companies.aggregate(
        tracked_count=Count("id"),
        gainers_count=Count("id", filter=Q(bucket="gainer")),
        losers_count=Count("id", filter=Q(bucket="loser")),
        unchanged_count=Count("id", filter=Q(bucket="unchanged")),
        **{f"{reason}_count": Count("id", filter=Q(bucket=reason)) for reason in EXCLUSION_REASONS},
    )

    gainers = _rows(companies.filter(bucket="gainer").order_by("-change_pct", "-turnover", "symbol")[:limit])
    losers = _rows(companies.filter(bucket="loser").order_by("change_pct", "-turnover", "symbol")[:limit])
    unchanged = _rows(companies.filter(bucket="unchanged").order_by("-turnover", "symbol"))
    excluded = _rows(companies.exclude(bucket__in=RANKED).order_by("bucket", "symbol"))
    _attach_sparklines(gainers + losers + unchanged + excluded, as_of)

    result.update(
        gainers=gainers,
        losers=losers,
        unchanged=unchanged,
        excluded=excluded,
        tracked_count=counts["tracked_count"],
        gainers_count=counts["gainers_count"],
        losers_count=counts["losers_count"],
        unchanged_count=counts["unchanged_count"],
        not_traded_count=counts["not_traded_count"],
        excluded_counts={reason: counts[f"{reason}_count"] for reason in EXCLUSION_REASONS},
    )
    if base_date is None:
        result["reason"] = (
            f"fewer than {sessions + 1} crawled trading sessions up to {as_of}; "
            f"{PERIODS[period]['label']} needs a close {sessions} session(s) earlier"
        )
        result["action"] = "Back-fill older prices: `cd Backend/crawlers && scrapy crawl trading_data -a window_days=60`."
    return result


def tracked_summary(requested_date=None, company_ids=None):
    """One aggregate() over the same 1-session buckets the movers use."""
    as_of, base_date, window_dates = resolve_sessions(requested_date, 1)
    if as_of is None:
        return {"trade_date": None, "reason": "no completed trading day in DailyPrice (source=crawled)", "action": NO_DATA_ACTION}

    totals = annotated_companies(as_of, base_date, window_dates, company_ids).aggregate(
        tracked_count=Count("id"),
        advanced=Count("id", filter=Q(bucket="gainer")),
        declined=Count("id", filter=Q(bucket="loser")),
        unchanged=Count("id", filter=Q(bucket="unchanged")),
        **{f"{reason}_count": Count("id", filter=Q(bucket=reason)) for reason in EXCLUSION_REASONS},
        positive_circuit=Count("id", filter=Q(bucket="gainer", change_pct__gte=CIRCUIT_THRESHOLD_PCT)),
        negative_circuit=Count("id", filter=Q(bucket="loser", change_pct__lte=-CIRCUIT_THRESHOLD_PCT)),
        adjusted_count=Count("id", filter=Q(adjusted=True, bucket__in=RANKED)),
        total_turnover=Sum("turnover"),
        total_traded_shares=Sum("volume"),
        total_transactions=Sum("transactions"),
        transactions_reported=Count("transactions"),
    )
    excluded = {reason: totals.pop(f"{reason}_count") for reason in EXCLUSION_REASONS}
    return {"trade_date": as_of, "previous_trade_date": base_date, **totals, "excluded_counts": excluded}


TOP_FIELDS = {"turnover": "turnover", "volume": "volume", "transactions": "transactions"}


def top_by(metric, requested_date=None, company_ids=None, limit=10):
    """Tracked companies that traded on as_of, by turnover / volume / transactions (NULLs last)."""
    field = TOP_FIELDS[metric]
    as_of, base_date, window_dates = resolve_sessions(requested_date, 1)
    if as_of is None:
        return {"trade_date": None, "metric": metric, "rows": [], "reason": "no completed trading day in DailyPrice (source=crawled)", "action": NO_DATA_ACTION}
    rows = _rows(
        annotated_companies(as_of, base_date, window_dates, company_ids)
        .exclude(bucket="not_traded")
        .order_by(F(field).desc(nulls_last=True), "symbol")[:limit]
    )
    return {"trade_date": as_of, "metric": metric, "rows": rows}


def company_rows(company_ids, requested_date=None):
    """1-session rows (any bucket) for the given companies -- used by the watchlist."""
    as_of, base_date, window_dates = resolve_sessions(requested_date, 1)
    if as_of is None:
        return None, {}
    rows = _rows(annotated_companies(as_of, base_date, window_dates, company_ids))
    return as_of, {row["company_id"]: row for row in rows}
