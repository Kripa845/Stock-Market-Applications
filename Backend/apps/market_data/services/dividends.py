"""
Proposed dividends for every listed company (spider ``dividends``, ShareSansar + Merolagani).

SCOPE: the whole market, not only the tracked companies: a symbol does not need a
Company row.  Every input comes from crawled data:

    bonus % / cash %, dates           ShareSansar "Proposed Dividend"  (DividendAnnouncement)
    face value (paid-up per share)    ShareSansar company page          (DividendAnnouncement.face_value)
    EPS per fiscal year and quarter   Merolagani company page           (CompanyEarnings)
    price                             latest crawled close: MarketStockDaily (whole market)
                                      or DailyPrice (tracked companies), whichever is newer

Calculated per row (``dividend_rows``), never stored, so a new price shows at once:

    cash_dps            cash % / 100 x face value
    dividend_yield_pct  cash_dps / price x 100
    cash_payout_pct     cash_dps / EPS x 100                       (full-year EPS, same FY)
    payout_pct          (cash % + bonus %) / 100 x face value / EPS x 100
    ex_bonus_price      price / (1 + bonus % / 100), only while the price is still cum-bonus
                        (price date before the book closure date)

Status.  ShareSansar publishes no AGM or SEBON approval, so ``infer_status`` derives it
from the crawled dates; SEBON approval is never inferred (set it in the admin).  Stages
only move forward, so a re-crawl keeps an admin-set later stage.
"""

import re
from decimal import Decimal

from django.db.models import F, OuterRef, Q, Subquery
from django.utils import timezone

from apps.companies.models import Company
from apps.market_data.models import CompanyEarnings, DailyPrice, DividendAnnouncement
from apps.market_indices.models import MarketStockDaily

PRICE_SOURCE = "crawled"
FULL_YEAR_QUARTER = 4
HUNDRED = Decimal(100)

UNITS = {
    "bonus_pct": "percent of face value",
    "cash_pct": "percent of face value",
    "face_value": "NPR",
    "price": "NPR",
    "eps": "NPR",
    "cash_dps": "NPR per share",
    "dividend_yield_pct": "percent",
    "cash_payout_pct": "percent",
    "payout_pct": "percent",
    "ex_bonus_price": "NPR",
}

STATUS_NOTE = (
    "Proposed: announced, book closure not yet passed. AGM approved: inferred once the book "
    "closure date has passed (the AGM approving the dividend is held on that register). "
    "SEBON approved: not published by the source, set in the admin only. Distributed: a "
    "distribution or bonus listing date has been published and reached."
)

FISCAL_YEAR_RE = re.compile(r"^\s*(?:FY\s*:?\s*)?(\d{2,4})\s*[/-]\s*(\d{2,4})\s*$", re.IGNORECASE)


def normalise_fiscal_year(text):
    """'2081/2082', '2081/82', '081-082', 'FY:082-083' -> '2081/2082'; anything else -> ''."""
    match = FISCAL_YEAR_RE.match(str(text or ""))
    if not match:
        return ""
    start, end = match.groups()
    # Short forms drop the Bikram Sambat millennium: '081' / '81' is 2081.
    first = int(start) if len(start) == 4 else 2000 + int(start)
    if int(end) % (10 ** len(end)) != (first + 1) % (10 ** len(end)):
        return ""
    return f"{first}/{first + 1}"


def later_status(current, inferred):
    order = DividendAnnouncement.STATUS_ORDER
    return max(current or order[0], inferred, key=order.index)


def infer_status(*, book_closure_date, distribution_date, bonus_listing_date, today):
    Status = DividendAnnouncement.Status
    if any(day and day <= today for day in (distribution_date, bonus_listing_date)):
        return Status.DISTRIBUTED
    if book_closure_date and book_closure_date < today:
        return Status.AGM_APPROVED
    return Status.PROPOSED


def _known_face_value(symbol):
    return (
        DividendAnnouncement.objects
        .filter(symbol=symbol, face_value__isnull=False)
        .order_by("-fiscal_year")
        .values_list("face_value", flat=True)
        .first()
    )


def upsert_dividend(data, *, source, today=None):
    """
    Save one crawled row.  ``data``: symbol, company_name, fiscal_year (any spelling),
    source_id, bonus_pct / cash_pct (Decimal or None = none), announcement_date,
    book_closure_date, distribution_date, bonus_listing_date (date or None).

    Returns "created", "updated" or "skipped" (no symbol / fiscal year and no source id).
    """
    today = today or timezone.localdate()
    symbol = (data.get("symbol") or "").strip().upper()
    fiscal_year = normalise_fiscal_year(data.get("fiscal_year"))
    source_id = str(data.get("source_id") or "").strip()
    missing = [name for name, value in (("symbol", symbol), ("fiscal_year", fiscal_year)) if not value]

    rows = DividendAnnouncement.objects
    if not missing:
        row = rows.filter(symbol=symbol, fiscal_year=fiscal_year).first()
    elif source_id:
        row = rows.filter(source=source, source_id=source_id).first()
    else:
        return "skipped"
    created = row is None
    if created:
        row = DividendAnnouncement(symbol=symbol, fiscal_year=fiscal_year)

    row.symbol, row.fiscal_year = symbol, fiscal_year
    row.company = Company.objects.filter(symbol__iexact=symbol).first() if symbol else None
    row.company_name = (data.get("company_name") or "").strip()[:300]
    row.bonus_pct = data.get("bonus_pct") or Decimal(0)
    row.cash_pct = data.get("cash_pct") or Decimal(0)
    for field in ("announcement_date", "book_closure_date", "distribution_date", "bonus_listing_date"):
        setattr(row, field, data.get(field))
    if row.face_value is None and symbol:
        row.face_value = _known_face_value(symbol)
    row.status = later_status(None if created else row.status, infer_status(
        book_closure_date=row.book_closure_date,
        distribution_date=row.distribution_date,
        bonus_listing_date=row.bonus_listing_date,
        today=today,
    ))
    row.missing_fields = missing
    row.source, row.source_id = source, source_id
    row.scraped_at = timezone.now()
    row.save()

    if source_id and not missing:
        # The same source row stored earlier without its symbol / fiscal year is now complete.
        (rows.filter(source=source, source_id=source_id).exclude(pk=row.pk)
         .filter(Q(symbol="") | Q(fiscal_year="")).delete())
    return "created" if created else "updated"


def save_face_value(symbol, face_value):
    """Fill the face value on this symbol's rows that do not have one yet; returns rows changed."""
    symbol = (symbol or "").strip().upper()
    if not symbol or face_value is None or face_value <= 0:
        return 0
    return DividendAnnouncement.objects.filter(symbol=symbol, face_value__isnull=True).update(face_value=face_value)


def save_eps(symbol, fiscal_year, quarter, eps, *, source):
    """Upsert one EPS figure; returns False when the symbol / fiscal year / quarter is unusable."""
    symbol = (symbol or "").strip().upper()
    fiscal_year = normalise_fiscal_year(fiscal_year)
    if not symbol or not fiscal_year or eps is None or quarter not in (1, 2, 3, 4):
        return False
    CompanyEarnings.objects.update_or_create(
        symbol=symbol, fiscal_year=fiscal_year, quarter=quarter,
        defaults={"eps": eps, "source": source, "scraped_at": timezone.now()},
    )
    return True


# ----------------------------------------------------------------------
# Read side
# ----------------------------------------------------------------------

def _pct(numerator, denominator):
    if numerator is None or not denominator or denominator <= 0:
        return None
    return (numerator / denominator * HUNDRED).quantize(Decimal("0.01"))


def _latest_price(row):
    candidates = [
        (row["market_close_date"], row["market_close"]),
        (row["tracked_close_date"], row["tracked_close"]),
    ]
    candidates = [c for c in candidates if c[0] and c[1] is not None]
    return max(candidates, key=lambda c: c[0]) if candidates else (None, None)


def _with_metrics(row):
    price_date, price = _latest_price(row)
    face_value, eps = row["face_value"], row["eps"]
    bonus_pct, cash_pct = row["bonus_pct"], row["cash_pct"]

    cash_dps = (cash_pct / HUNDRED * face_value).quantize(Decimal("0.0001")) if face_value else None
    total_dps = (bonus_pct + cash_pct) / HUNDRED * face_value if face_value else None
    # After book closure the crawled price is already ex-bonus: adjusting it again would be wrong.
    cum_bonus = price_date is not None and (row["book_closure_date"] is None or price_date < row["book_closure_date"])
    ex_bonus_price = (
        (price / (1 + bonus_pct / HUNDRED)).quantize(Decimal("0.01"))
        if price is not None and bonus_pct > 0 and cum_bonus else None
    )

    flags = [f"missing_{field}" for field in row["missing_fields"] or []]
    if price is None:
        flags.append("no_price")
    if face_value is None:
        flags.append("no_face_value")
    if eps is None:
        flags.append("no_eps")

    return {
        "id": row["id"],
        "symbol": row["symbol"],
        "name": row["company_name"] or row["tracked_name"] or "",
        "logo_url": row["logo_url"],
        "fiscal_year": row["fiscal_year"],
        "status": row["status"],
        "bonus_pct": bonus_pct,
        "cash_pct": cash_pct,
        "total_pct": bonus_pct + cash_pct,
        "announcement_date": row["announcement_date"],
        "book_closure_date": row["book_closure_date"],
        "distribution_date": row["distribution_date"],
        "bonus_listing_date": row["bonus_listing_date"],
        "face_value": face_value,
        "price": price,
        "price_date": price_date,
        "eps": eps,
        "cash_dps": cash_dps,
        "dividend_yield_pct": _pct(cash_dps, price),
        "cash_payout_pct": _pct(cash_dps, eps),
        "payout_pct": _pct(total_dps, eps),
        "ex_bonus_price": ex_bonus_price,
        "flags": flags,
        "scraped_at": row["scraped_at"],
    }


def fiscal_years():
    # order_by(): Meta.ordering would otherwise be part of the DISTINCT.
    years = (DividendAnnouncement.objects.exclude(fiscal_year="").order_by()
             .values_list("fiscal_year", flat=True).distinct())
    return sorted(years, reverse=True)


def dividend_rows(fiscal_year=None, status=None):
    """Rows for one fiscal year (plus rows with no fiscal year, so they stay visible) or all."""
    rows = DividendAnnouncement.objects.all()
    if fiscal_year:
        rows = rows.filter(Q(fiscal_year=fiscal_year) | Q(fiscal_year=""))
    if status:
        rows = rows.filter(status=status)

    market = (MarketStockDaily.objects
              .filter(symbol=OuterRef("symbol"), source=PRICE_SOURCE, close__isnull=False)
              .order_by("-date"))
    tracked = (DailyPrice.objects
               .filter(company_id=OuterRef("company_id"), source=PRICE_SOURCE)
               .order_by("-date"))
    full_year_eps = CompanyEarnings.objects.filter(
        symbol=OuterRef("symbol"), fiscal_year=OuterRef("fiscal_year"), quarter=FULL_YEAR_QUARTER,
    )
    rows = (
        rows.annotate(
            market_close=Subquery(market.values("close")[:1]),
            market_close_date=Subquery(market.values("date")[:1]),
            tracked_close=Subquery(tracked.values("close")[:1]),
            tracked_close_date=Subquery(tracked.values("date")[:1]),
            eps=Subquery(full_year_eps.values("eps")[:1]),
            tracked_name=F("company__name"),
            logo_url=F("company__logo_url"),
        )
        .order_by(F("book_closure_date").desc(nulls_last=True), F("announcement_date").desc(nulls_last=True), "symbol")
        .values(
            "id", "symbol", "company_name", "tracked_name", "logo_url", "fiscal_year", "status",
            "bonus_pct", "cash_pct", "face_value", "announcement_date", "book_closure_date",
            "distribution_date", "bonus_listing_date", "missing_fields", "scraped_at",
            "market_close", "market_close_date", "tracked_close", "tracked_close_date", "eps",
        )
    )
    return [_with_metrics(row) for row in rows]


def last_updated():
    """When a dividend row was last written by the crawler, and the last dividend crawl run."""
    from apps.crawler_runs.models import CrawlRun

    scraped = (DividendAnnouncement.objects.exclude(scraped_at=None)
               .order_by("-scraped_at").values_list("scraped_at", flat=True).first())
    run = (CrawlRun.objects.filter(crawl_type=CrawlRun.CrawlType.DIVIDENDS)
           .order_by("-created_at").values("id", "status", "started_at", "completed_at").first())
    return {"last_scraped_at": scraped, "last_crawl": run}
