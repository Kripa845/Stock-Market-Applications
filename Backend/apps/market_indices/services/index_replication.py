"""
Reproduce NEPSE index and sub-index values from company-level data.

    Index = total market cap x K        K = published close / total market cap  (calibration day)

NEPSE's API does not publish the base index value (``/api/nots/index`` only has a
``baseYearMarketCapitalization``, already adjusted over the years), so the
"base value / base market cap" ratio is not used directly: K absorbs it and is
calibrated from one day whose published close is known.

Membership (index_rule):
    NEPSE            every listed equity, listed shares
    SENSITIVE        class "A" equities, listed shares
    FLOAT            every listed equity, public shares (stand-in for free float -> approximate)
    SENSITIVE_FLOAT  class "A" equities, public shares
    sub-indices      equities of the sub-index sector (Mutual Fund: mutual fund units), listed shares

Data, all from NEPSE's own API (market_data.services.live_prices._nepse_client):
    /api/nots/company/list            symbol, sectorName, instrumentType, status ("A" active, "D" delisted)
    /api/nots/nepse-data/today-price  per security for ONE business date: closePrice,
                                      previousDayClosePrice, marketCapitalization (Rs million,
                                      2 dp).  Only securities that traded that day are listed.
    /api/nots/security/{id}           stockListedShares, publicShares, security.shareGroupId.name,
                                      securityDailyTradeDto (last trade).  CURRENT values only.
Published closes come from IndexDaily (NEPSE's /api/nots/index/history, see nepse_indices),
always for the same business date as the prices.

The API is undocumented; the library swallows errors and returns {} / [].  Every
response is validated here and a missing or malformed one raises ReplicationError
(logged), so a partial day is never stored and a market cap is never silently low.
"""

import logging
import time
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Max

from apps.market_data.services.live_prices import LivePriceError, _nepse_client, fetch_day_summary
from apps.market_indices.models import CompanyDaily, IndexCalibration, IndexCheck, IndexDaily, MarketIndex
from apps.market_indices.sectors import normalise_sector

logger = logging.getLogger(__name__)

DIFF_TOLERANCE = Decimal("0.5")          # index points; larger differences are flagged
EQUITY = "Equity"
MUTUAL_FUNDS = "Mutual Funds"
MUTUAL_FUND_SECTOR = "Mutual Fund"
UNCLASSIFIED = "Unclassified"
ACTIVE = "A"
PRICE_PAGE_SIZE = 500                    # fetch_day_summary's single page
LOOKBACK_DAYS = 10                       # calendar days searched for an untraded security's last close
DETAIL_PAUSE_SECONDS = 0.25              # between security-detail calls (one per security)
MCAP_TOLERANCE = Decimal("10000")        # NEPSE rounds marketCapitalization to 0.01 Rs million
K_PLACES = Decimal("1e-30")
TWO_PLACES = Decimal("0.01")

MAIN_RULES = {
    "NEPSE": {"shares": "listed_shares"},
    "SENSITIVE": {"share_class": "A", "shares": "listed_shares"},
    "FLOAT": {"shares": "public_shares"},
    "SENSITIVE_FLOAT": {"share_class": "A", "shares": "public_shares"},
}


class ReplicationError(Exception):
    """NEPSE data, a published close or a calibration needed for the calculation is missing."""


def _decimal(value):
    try:
        return None if value is None else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- membership

def index_rule(index_code):
    """{"instrument", "shares", optional "sector" / "share_class"} for a MarketIndex code."""
    if index_code in MAIN_RULES:
        return {"instrument": EQUITY, **MAIN_RULES[index_code]}
    index = MarketIndex.objects.filter(code=index_code, kind=MarketIndex.KIND_SUB).first()
    if index is None or not index.sector_name:
        raise ReplicationError(f"unknown index {index_code!r}")
    instrument = MUTUAL_FUNDS if index.sector_name == MUTUAL_FUND_SECTOR else EQUITY
    return {"instrument": instrument, "sector": index.sector_name, "shares": "listed_shares"}


def _constituent_rows(day, rule):
    rows = CompanyDaily.objects.filter(date=day, instrument_type=rule["instrument"])
    if "sector" in rule:
        rows = rows.filter(sector=rule["sector"])
    if "share_class" in rule:
        rows = rows.filter(share_class=rule["share_class"])
    return list(rows)


def constituents(day, index_code):
    """CompanyDaily rows of the index's members on ``day``."""
    return _constituent_rows(day, index_rule(index_code))


def _market_cap(day, index_code):
    rule = index_rule(index_code)
    rows = _constituent_rows(day, rule)
    if not rows:
        raise ReplicationError(f"no company data for {index_code} on {day}: run the snapshot for that day first")
    missing = [row.symbol for row in rows if getattr(row, rule["shares"]) is None]
    if missing:
        raise ReplicationError(f"{index_code} {day}: no {rule['shares']} for {', '.join(missing)}")
    return sum((row.close * getattr(row, rule["shares"]) for row in rows), Decimal(0)), rows


def market_cap(day, index_code):
    """Total market cap (Rs) of the index's constituents on ``day``: sum of close x shares."""
    return _market_cap(day, index_code)[0]


# --------------------------------------------------------------------------- calibration

def published_close(index_code, day):
    """NEPSE's published close for that exact business date (IndexDaily)."""
    close = IndexDaily.objects.filter(index__code=index_code, date=day).values_list("close", flat=True).first()
    if close is None:
        raise ReplicationError(
            f"NEPSE's published {index_code} close for {day} is not stored: run `manage.py sync_market_indices`"
        )
    return close


def calibrate(index_code, day):
    """K = published close / total market cap on ``day``; saved as an IndexCalibration effective that day."""
    published = published_close(index_code, day)
    total, rows = _market_cap(day, index_code)
    k = (published / total).quantize(K_PLACES)
    calibration, _ = IndexCalibration.objects.update_or_create(
        index=MarketIndex.objects.get(code=index_code), effective_date=day,
        defaults={"k": k, "published_close": published, "market_cap": total.quantize(TWO_PLACES),
                  "constituents": len(rows)},
    )
    logger.info("calibrated %s on %s: K=%s (close %s / market cap %s, %d constituents)",
                index_code, day, k, published, total, len(rows))
    return calibration


def calibration_for(index_code, day):
    """The latest calibration effective on or before ``day``."""
    calibration = (IndexCalibration.objects.filter(index__code=index_code, effective_date__lte=day)
                   .order_by("-effective_date").first())
    if calibration is None:
        raise ReplicationError(f"{index_code} has no calibration on or before {day}: run calibrate first")
    return calibration


def compute_index(day, index_code):
    """Reproduced index value for ``day``: total market cap x K."""
    return (market_cap(day, index_code) * calibration_for(index_code, day).k).quantize(TWO_PLACES)


# --------------------------------------------------------------------------- verification

def _share_changes(before, after, field):
    """Readable list of constituents whose share count changed, joined or left."""
    old = {row.symbol: getattr(row, field) for row in before}
    new = {row.symbol: getattr(row, field) for row in after}
    changes = [f"{symbol} {field} {old[symbol]:,} -> {new[symbol]:,}"
               for symbol in sorted(old.keys() & new.keys()) if old[symbol] != new[symbol]]
    changes += [f"{symbol} joined" for symbol in sorted(new.keys() - old.keys())]
    changes += [f"{symbol} left" for symbol in sorted(old.keys() - new.keys())]
    return changes


def recalibration_reasons(day, index_code, calibration):
    """
    Why K may be stale on ``day``: constituent share counts or membership changed since
    the previous snapshot (bonus, right, IPO, merger, delisting).  A change between the
    calibration day and the previous snapshot is still reported until K is recalibrated.
    """
    rule = index_rule(index_code)
    rows = _constituent_rows(day, rule)
    base = CompanyDaily.objects.filter(date__lt=day, instrument_type=rule["instrument"])
    if "sector" in rule:
        base = base.filter(sector=rule["sector"])
    previous_day = base.aggregate(latest=Max("date"))["latest"]
    if previous_day is None:
        return []
    changes = _share_changes(_constituent_rows(previous_day, rule), rows, rule["shares"])
    if changes:
        return [f"since {previous_day}: " + "; ".join(changes)]
    if calibration.effective_date < previous_day:
        pending = _share_changes(_constituent_rows(calibration.effective_date, rule), rows, rule["shares"])
        if pending:
            return [f"since calibration on {calibration.effective_date}: " + "; ".join(pending)]
    return []


def verify_index(day, index_code):
    """Compare the reproduced value with NEPSE's published close for ``day`` and store an IndexCheck."""
    calibration = calibration_for(index_code, day)
    published = published_close(index_code, day)
    computed = (market_cap(day, index_code) * calibration.k).quantize(TWO_PLACES)
    diff = computed - published
    reasons = recalibration_reasons(day, index_code, calibration)
    check, _ = IndexCheck.objects.update_or_create(
        index=calibration.index, date=day,
        defaults={"calibration": calibration, "computed": computed, "published": published, "diff": diff,
                  "flagged": abs(diff) > DIFF_TOLERANCE, "needs_recalibration": bool(reasons),
                  "recalibration_reason": "\n".join(reasons)},
    )
    if check.flagged:
        logger.warning("index check %s %s: computed %s vs published %s (diff %+.2f > %s points)",
                       index_code, day, computed, published, diff, DIFF_TOLERANCE)
    if reasons:
        logger.warning("index check %s %s: recalibration needed (%s)", index_code, day, "; ".join(reasons))
    return check


def verify_day(day, index_codes=None):
    """Daily job body: verify every calibrated index (or ``index_codes``).  Failures are logged, not raised."""
    if index_codes is None:
        index_codes = sorted(set(IndexCalibration.objects.filter(effective_date__lte=day)
                                 .values_list("index__code", flat=True)))
    results = []
    for code in index_codes:
        try:
            results.append(verify_index(day, code))
        except ReplicationError as exc:
            logger.error("index check %s %s skipped: %s", code, day, exc)
            results.append({"index": code, "error": str(exc)})
    return results


def sectors_for(index_codes):
    """Normalised sectors a snapshot must cover for these indices (None = whole market)."""
    if any(code in MAIN_RULES for code in index_codes):
        return None
    return sorted({index_rule(code)["sector"] for code in index_codes})


# --------------------------------------------------------------------------- NEPSE data

class NepseSource:
    """NEPSE API calls used by the snapshot, each validated; logs in again once when a call comes back empty."""

    def __init__(self, client_factory=_nepse_client, pause=time.sleep):
        self._factory = client_factory
        self._client = None
        self._pause = pause
        self._prices = {}

    def _login(self):
        try:
            self._client = self._factory()
        except Exception as exc:
            raise ReplicationError(f"NEPSE login failed: {exc}") from exc
        return self._client

    @property
    def client(self):
        return self._client or self._login()

    def company_list(self):
        for attempt in (1, 2):
            try:
                rows = self.client.get_company_list(use_cache=False)
            except Exception as exc:
                logger.warning("NEPSE company list attempt %d failed: %s", attempt, exc)
                rows = None
            if isinstance(rows, list) and rows:
                return rows
            self._login()
        raise ReplicationError("NEPSE company list returned nothing usable (API changed, blocked or down)")

    def day_prices(self, day):
        """{symbol: today-price row} for ``day`` exactly (empty for a non-trading day)."""
        if day not in self._prices:
            rows = {}
            for attempt in (1, 2):
                try:
                    rows = fetch_day_summary(day, self.client)
                except LivePriceError as exc:
                    logger.warning("NEPSE day prices %s attempt %d failed: %s", day, attempt, exc)
                if rows:
                    break
                self._login()  # expired token: the library returns [] instead of raising
            if len(rows) >= PRICE_PAGE_SIZE:
                raise ReplicationError(f"NEPSE day prices for {day} hit the {PRICE_PAGE_SIZE}-row page limit")
            self._prices[day] = rows
        return self._prices[day]

    def security_detail(self, security_id, symbol):
        for attempt in (1, 2):
            self._pause(DETAIL_PAUSE_SECONDS)
            detail = self.client.get_security_details(security_id, use_cache=False)
            if (isinstance(detail, dict) and detail.get("stockListedShares") is not None
                    and isinstance(detail.get("security"), dict)):
                return detail
            logger.warning("NEPSE security detail %s (id %s) attempt %d unusable: %s",
                           symbol, security_id, attempt, sorted(detail) if isinstance(detail, dict) else type(detail))
            self._login()
        raise ReplicationError(f"NEPSE security detail for {symbol} (id {security_id}) returned nothing usable")


def listed_securities(source, sectors=None):
    """Active equities and mutual funds from NEPSE's company list, with their normalised sector."""
    securities = []
    for row in source.company_list():
        if not isinstance(row, dict) or row.get("status") != ACTIVE:
            continue
        instrument = row.get("instrumentType")
        if instrument not in (EQUITY, MUTUAL_FUNDS):
            continue
        if not row.get("id") or not row.get("symbol"):
            logger.warning("NEPSE company list row without id/symbol skipped: %s", row)
            continue
        if instrument == MUTUAL_FUNDS:
            sector = MUTUAL_FUND_SECTOR  # NEPSE files funds under their sponsor's sector
        else:
            sector = normalise_sector(row.get("sectorName"))
            if sector is None:
                logger.warning("unknown NEPSE sector %r for %s: stored as %s",
                               row.get("sectorName"), row["symbol"], UNCLASSIFIED)
                sector = UNCLASSIFIED
        if sectors is None or sector in sectors:
            securities.append({"id": int(row["id"]), "symbol": str(row["symbol"]).upper(),
                               "sector": sector, "instrument": instrument})
    if not securities:
        raise ReplicationError(f"NEPSE company list has no active securities for sectors {sectors}")
    return securities


def _last_close(source, symbol, day, detail):
    """Close of an untraded security as of ``day``: its last trade before ``day``."""
    trade = detail.get("securityDailyTradeDto") or {}
    traded_on = str(trade.get("businessDate") or "")[:10]
    if traded_on and traded_on < day.isoformat() and _decimal(trade.get("closePrice")):
        return _decimal(trade.get("closePrice"))
    # It traded after ``day``: walk back through NEPSE's daily prices.
    for back in range(1, LOOKBACK_DAYS + 1):
        row = source.day_prices(day - timedelta(days=back)).get(symbol)
        if row and _decimal(row.get("closePrice")):
            return _decimal(row.get("closePrice"))
    return None


def _listed_shares(symbol, day, detail, price_row, close):
    """Listed shares for ``day`` and where they came from (see CompanyDaily)."""
    listed = int(Decimal(str(detail["stockListedShares"])))
    mcap_million = _decimal((price_row or {}).get("marketCapitalization"))
    if mcap_million and close:
        mcap = mcap_million * 1_000_000
        if abs(listed * close - mcap) > MCAP_TOLERANCE:
            implied = int((mcap / close).to_integral_value(ROUND_HALF_UP))
            logger.warning("%s %s: NEPSE's current listed shares %s disagree with its same-day market cap "
                           "(implies %s); using the same-day value", symbol, day, f"{listed:,}", f"{implied:,}")
            return implied, CompanyDaily.SHARES_SAME_DAY_MCAP
    return listed, CompanyDaily.SHARES_DETAIL


def snapshot_company_daily(day, sectors=None, source=None):
    """
    Store a CompanyDaily row for every active equity / mutual fund (or only ``sectors``) on ``day``.

    All rows are built first and saved in one transaction: any NEPSE failure raises
    ReplicationError and nothing is written for the day.
    """
    source = source or NepseSource()
    prices = source.day_prices(day)
    if not prices:
        raise ReplicationError(f"NEPSE has no end-of-day prices for {day} (not a trading day, or the API failed)")
    securities = listed_securities(source, sectors)

    rows, problems, carried, implied = [], [], [], []
    for security in securities:
        symbol = security["symbol"]
        detail = source.security_detail(security["id"], symbol)
        price = prices.get(symbol)
        close = _decimal(price.get("closePrice")) if price else None
        if close:
            prev_close, traded = _decimal(price.get("previousDayClosePrice")), True
        else:
            close = _last_close(source, symbol, day, detail)
            prev_close, traded = close, False
            carried.append(symbol)
        if not close:
            problems.append(f"{symbol}: no close on or within {LOOKBACK_DAYS} days before {day}")
            continue
        listed, shares_source = _listed_shares(symbol, day, detail, price, close)
        if shares_source == CompanyDaily.SHARES_SAME_DAY_MCAP:
            implied.append(symbol)
        group = detail["security"].get("shareGroupId") or {}
        public = detail.get("publicShares")
        rows.append({
            "symbol": symbol, "security_id": security["id"], "sector": security["sector"],
            "instrument_type": security["instrument"], "share_class": str(group.get("name") or ""),
            "close": close, "prev_close": prev_close, "traded": traded,
            "listed_shares": listed, "listed_shares_source": shares_source,
            "public_shares": None if public is None else int(Decimal(str(public))),
        })
    if problems:
        raise ReplicationError(f"snapshot {day} not saved: " + "; ".join(problems))

    with transaction.atomic():
        for row in rows:
            CompanyDaily.objects.update_or_create(date=day, symbol=row.pop("symbol"), defaults=row)
    result = {"date": day.isoformat(), "saved": len(rows), "carried_forward": carried,
              "shares_from_same_day_mcap": implied}
    logger.info("company snapshot %s: %d securities (%d untraded, last close kept; %d shares from same-day mcap)",
                day, len(rows), len(carried), len(implied))
    return result
