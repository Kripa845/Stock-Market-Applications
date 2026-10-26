"""
Watchlist heatmap (GET /api/market/heatmap/): the tracked companies grouped by sector,
for a treemap sized by market cap and coloured by the day's change.

Prices are the live values services.live_prices stores on ``Company`` every 2 minutes
in market hours, so after the close they are that session's closing snapshot and they
stay on screen until the next session starts trading.

    change_pct         (ltp - previous_close) / previous_close * 100, against NEPSE's
                       previous close (already adjusted for bonus / right shares)
    market_cap         ltp * listed_shares
    sector change_pct  (sum(ltp * shares) - sum(prev * shares)) / sum(prev * shares) * 100

A company with no trade in the session (absent from the feed, or no volume) has a null
change_pct and counts as unchanged in its sector, the way a cap-weighted index treats
it.  A company without ``listed_shares`` has a null market_cap and is left out of its
sector's change; ``missing_shares`` lists them.
"""

from collections import defaultdict
from decimal import Decimal

from apps.market_data.services.live_prices import NPT, SOURCE, is_stale, last_successful_fetch
from apps.market_data.services.market_stats import tracked_companies
from apps.market_data.services.trading_days import is_market_open

TWO_PLACES = Decimal("0.01")
FIELDS = ("id", "symbol", "name", "sector", "ltp", "previous_close", "prices_updated_at",
          "session_volume", "session_turnover", "listed_shares")


def _two(value):
    return None if value is None else value.quantize(TWO_PLACES)


def _pct(current, previous):
    return None if not previous else _two((current - previous) * 100 / previous)


def _company_row(company, session_date):
    traded = (
        company.prices_updated_at is not None
        and company.prices_updated_at.astimezone(NPT).date() == session_date
        and company.session_volume != 0          # None: saved before volume was stored
    )
    ltp, previous = company.ltp, company.previous_close
    shares = company.listed_shares
    return {
        "symbol": company.symbol,
        "name": company.name,
        "ltp": ltp,
        "prev_close": previous if traded else None,
        "change_pct": _pct(ltp, previous) if traded and ltp is not None else None,
        "market_cap": _two(ltp * shares) if ltp is not None and shares else None,
        # Volume and turnover belong to the session; an untraded company's are from an older one.
        "volume": company.session_volume if traded else None,
        "turnover": company.session_turnover if traded else None,
        "traded": traded,
    }


def _sector_row(name, members):
    """Cap-weighted change over members with a market cap; untraded members count as flat."""
    current = previous = Decimal("0")
    for company, row in members:
        if row["market_cap"] is None:
            continue
        shares = Decimal(company.listed_shares)
        if row["change_pct"] is None:
            current += row["market_cap"]
            previous += row["market_cap"]
        else:
            current += company.ltp * shares
            previous += company.previous_close * shares
    traded_with_cap = any(row["change_pct"] is not None and row["market_cap"] is not None for _, row in members)
    caps = [row["market_cap"] for _, row in members if row["market_cap"] is not None]
    rows = sorted((row for _, row in members), key=lambda r: (-(r["market_cap"] or 0), r["symbol"]))
    return {
        "name": name,
        "change_pct": _pct(current, previous) if traded_with_cap else None,
        "market_cap": sum(caps, Decimal("0")) if caps else None,
        "companies": rows,
    }


def heatmap(company_ids=None):
    companies = list(tracked_companies(company_ids).only(*FIELDS))
    stamps = [c.prices_updated_at for c in companies if c.prices_updated_at]
    as_of = max(stamps) if stamps else None
    session_date = as_of.astimezone(NPT).date() if as_of else None

    by_sector = defaultdict(list)
    for company in companies:
        by_sector[company.sector or "Others"].append((company, _company_row(company, session_date)))
    sectors = sorted(
        (_sector_row(name, members) for name, members in by_sector.items()),
        key=lambda s: (-(s["market_cap"] or 0), s["name"]),
    )

    last_fetch = last_successful_fetch()
    result = {
        "last_updated": as_of.astimezone(NPT).isoformat() if as_of else None,
        "session_date": session_date,
        "market_open": is_market_open(),
        "stale": is_stale(last_fetch),
        "last_successful_fetch": last_fetch,
        "source": SOURCE,
        "tracked_count": len(companies),
        "missing_shares": sorted(c.symbol for c in companies if not c.listed_shares),
        "sectors": sectors,
    }
    if as_of is None:
        result["reason"] = "No live prices stored yet. They are fetched every 2 minutes during market hours."
        result["action"] = "Run `python manage.py update_live_prices` (works while the NEPSE live feed has data)."
    return result
