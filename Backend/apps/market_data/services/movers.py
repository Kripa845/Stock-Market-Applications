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
    Max,
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
from apps.floorsheet.models import FloorsheetTransaction
from apps.market_data.services.trading_calendar import latest_trading_date, previous_trading_sessions
from apps.market_data.services.market_stats import PRICE_SOURCE, tracked_companies


# CHANGED: more periods for the full movers page. Periods are trading sessions
# (NEPSE trades 5 days a week), not calendar days.
PERIODS = {
    "1D":   {"sessions": 1,   "label": "Today"},
    "2S":   {"sessions": 2,   "label": "2 sessions"},
    "3S":   {"sessions": 3,   "label": "3 sessions"},
    "5S":   {"sessions": 5,   "label": "5 sessions"},
    "7S":   {"sessions": 7,   "label": "7 sessions"},
    "20S":  {"sessions": 20,  "label": "1 month"},
    "60S":  {"sessions": 60,  "label": "3 months"},
    "80S":  {"sessions": 80,  "label": "4 months"},
    "120S": {"sessions": 120, "label": "6 months"},
    "240S": {"sessions": 240, "label": "1 year"},
}
PERIOD_ALIASES = {
    "2D": "2S", "3D": "3S", "5D": "5S", "7D": "7S",
    "1W": "5S", "1M": "20S", "3M": "60S", "4M": "80S", "6M": "120S", "1Y": "240S",
}

ADJUSTMENT_TOLERANCE_PCT = Decimal("0.05")
CORPORATE_ACTION_PCT = Decimal("10")   # one-session threshold (NEPSE daily circuit)
CIRCUIT_THRESHOLD_PCT = Decimal("9.9")
SPARKLINE_SESSIONS = 7

RANKED = ("gainer", "loser", "unchanged")
# missing_price: no crawled row on as_of at all (crawl gap, or no trades listed by the source);
# not_traded: a row exists but with zero / no volume.
EXCLUSION_REASONS = ("missing_price", "not_traded", "missing_previous_session", "prev_close_zero", "possible_corporate_action")
NOT_RANKABLE_TODAY = ("missing_price", "not_traded")

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
    "company_id", "symbol", "name", "sector", "logo_url", "bucket",
    "close", "prev_close", "change", "change_pct",
    "raw_prev_close", "close_to_close_change_pct", "change_basis", "adjusted", "unadjusted",
    "possible_corporate_action", "volume", "turnover", "transactions", "price_source",
)


def normalize_period(value):
    key = (value or "1D").strip().upper()
    key = PERIOD_ALIASES.get(key, key)
    return key if key in PERIODS else None


# NEW: a move bigger than this over N sessions can't be a real price move
# (daily circuit is +-10%, compounded), so it is treated as a corporate action.
def corporate_action_threshold(sessions):
    if sessions <= 1:
        return CORPORATE_ACTION_PCT
    return ((Decimal("1.1") ** sessions - 1) * 100).quantize(Decimal("0.01"))


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


# CHANGED: new `adjusted` argument (True = use ShareSansar's adjusted %, False = close-to-close).
def annotated_companies(as_of, base_date, window_dates, company_ids=None, adjusted=True):
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

    # CHANGED: the Adjusted Price switch.
    if not adjusted:
        has_source = Q(pk__isnull=True)          # never true -> always close-to-close
        source_pct = F("source_pct_today")       # unused
    elif sessions == 1:
        has_source = Q(source_pct_today__isnull=False)
        source_pct = F("source_pct_today")
    else:
        has_source = Q(window_known=sessions)
        source_pct = Cast((Exp(F("window_log")) - ONE) * HUNDRED, PCT)

    # CHANGED: threshold scales with the number of sessions.
    threshold = corporate_action_threshold(sessions)

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
            When(close__isnull=True, then=Value("missing_price")),
            When(Q(volume__isnull=True) | Q(volume=0), then=Value("not_traded")),
            When(raw_prev_close__isnull=True, then=Value("missing_previous_session")),
            When(raw_prev_close__lte=0, then=Value("prev_close_zero")),
            When(
                Q(change_basis="close_to_close")
                & (Q(close_to_close_change_pct__gt=threshold) | Q(close_to_close_change_pct__lt=-threshold)),
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


def incomplete_session_warning(as_of, missing, tracked):
    """Text for when some tracked companies have no crawled row on as_of, else None."""
    if not missing:
        return None
    return (
        f"{missing} of {tracked} tracked companies have no crawled price for {as_of}, so counts and totals "
        f"cover only {tracked - missing}. The price crawl may be incomplete, or the source listed no trades for them."
    )


# CHANGED: `lean` skips unchanged / excluded rows and sparklines (use it for the dashboard card);
# `adjusted` is passed through.
def tracked_movers(period="1D", requested_date=None, company_ids=None, limit=5, lean=False, adjusted=True):
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

    companies = annotated_companies(as_of, base_date, window_dates, company_ids, adjusted)
    counts = companies.aggregate(
        tracked_count=Count("id"),
        gainers_count=Count("id", filter=Q(bucket="gainer")),
        losers_count=Count("id", filter=Q(bucket="loser")),
        unchanged_count=Count("id", filter=Q(bucket="unchanged")),
        **{f"{reason}_count": Count("id", filter=Q(bucket=reason)) for reason in EXCLUSION_REASONS},
    )

    gainers = _rows(companies.filter(bucket="gainer").order_by("-change_pct", "-turnover", "symbol")[:limit])
    losers = _rows(companies.filter(bucket="loser").order_by("change_pct", "-turnover", "symbol")[:limit])
    if lean:
        unchanged, excluded = [], []
    else:
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
        missing_price_count=counts["missing_price_count"],
        excluded_counts={reason: counts[f"{reason}_count"] for reason in EXCLUSION_REASONS},
    )
    warning = incomplete_session_warning(as_of, counts["missing_price_count"], counts["tracked_count"])
    if warning:
        result["warning"] = warning
    if base_date is None:
        result["reason"] = (
            f"fewer than {sessions + 1} crawled trading sessions up to {as_of}; "
            f"{PERIODS[period]['label']} needs a close {sessions} session(s) earlier"
        )
        result["action"] = "Back-fill older prices: `cd Backend/crawlers && scrapy crawl trading_data -a window_days=60`."
    return result


# NEW: paged, filterable list for the full "Tracked Top Gainers / Losers" page.
def tracked_movers_page(side="gainer", period="1D", sector=None, adjusted=True,
                        requested_date=None, page=1, page_size=20, company_ids=None):
    side = "loser" if side == "loser" else "gainer"
    period = normalize_period(period) or "1D"
    sessions = PERIODS[period]["sessions"]
    as_of, base_date, window_dates = resolve_sessions(requested_date, sessions)

    out = {
        "as_of": as_of,
        "period": period,
        "period_label": PERIODS[period]["label"],
        "base_date": base_date,
        "side": side,
        "sectors": sorted(set(tracked_companies(company_ids).values_list("sector", flat=True))),
        "total": 0,
        "page": page,
        "page_size": page_size,
        "rows": [],
    }
    if as_of is None or base_date is None:
        out["reason"] = "Not enough crawled sessions for this period."
        out["action"] = "Back-fill older prices: `cd Backend/crawlers && scrapy crawl trading_data -a window_days=300`."
        return out

    qs = annotated_companies(as_of, base_date, window_dates, company_ids, adjusted).filter(bucket=side)
    if sector:
        qs = qs.filter(sector=sector)

    order = ("-change_pct", "-turnover", "symbol") if side == "gainer" else ("change_pct", "-turnover", "symbol")
    out["total"] = qs.count()
    start = (page - 1) * page_size
    rows = _rows(qs.order_by(*order)[start:start + page_size])

    # Latest trade time per listed company on the as_of session (None until the floorsheet is crawled).
    last_trade = dict(
        FloorsheetTransaction.objects
        .filter(date=as_of, company_id__in=[r["company_id"] for r in rows])
        .values("company_id")
        .annotate(t=Max("trade_time"))
        .values_list("company_id", "t")
    )
    for r in rows:
        r["last_updated"] = last_trade.get(r["company_id"])
    out["rows"] = rows
    return out


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
    summary = {"trade_date": as_of, "previous_trade_date": base_date, **totals, "excluded_counts": excluded}
    warning = incomplete_session_warning(as_of, excluded["missing_price"], totals["tracked_count"])
    if warning:
        summary["warning"] = warning
    return summary


TOP_FIELDS = {"turnover": "turnover", "volume": "volume", "transactions": "transactions"}


def top_by(metric, requested_date=None, company_ids=None, limit=10):
    """Tracked companies that traded on as_of, by turnover / volume / transactions (NULLs last)."""
    field = TOP_FIELDS[metric]
    as_of, base_date, window_dates = resolve_sessions(requested_date, 1)
    if as_of is None:
        return {"trade_date": None, "metric": metric, "rows": [], "reason": "no completed trading day in DailyPrice (source=crawled)", "action": NO_DATA_ACTION}
    rows = _rows(
        annotated_companies(as_of, base_date, window_dates, company_ids)
        .exclude(bucket__in=NOT_RANKABLE_TODAY)
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