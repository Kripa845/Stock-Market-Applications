"""
Floor Sheet Summary grid: one session's timestamped trades for the tracked
companies, grouped into N-minute buckets from the 11:00 open, plus the checks
that prove the grid matches the raw trades and the exchange's daily figures.

The grid is built from the SQL per-minute rows that also feed the intraday
candles (``intraday_candles.minute_rows``); the checks recompute everything
from the raw trades in Python, so the two paths verify each other.
"""

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.utils import timezone

from apps.floorsheet.models import FloorsheetTransaction
from apps.floorsheet.services.intraday_candles import NPT, SESSION_CLOSE, SESSION_OPEN, minute_rows, session_bounds
from apps.market_data.models import DailyPrice
from apps.market_data.services.market_stats import PRICE_SOURCE, tracked_companies
from apps.market_data.services.movers import annotated_companies, resolve_sessions
from apps.market_data.services.trading_days import is_market_open

BUCKET_MINUTES = (1, 5, 10, 15, 30, 45)
DEFAULT_BUCKET_MINUTES = 1
RECENT_DATES = 60

# NEPSE's official close ignores odd-lot trades (fewer than 10 shares): on
# 2026-10-28 NICA closed at 320.00 although its last trade was 2 shares at 320.60.
ROUND_LOT = 10
CLOSING_VWAP_FROM = time(14, 45)

HUNDRED = Decimal(100)
MONEY_TOLERANCE = Decimal("0.01")
# The crawled daily turnover is rounded by the source (seen up to 0.40 off the trade sum).
DAILY_TURNOVER_TOLERANCE = Decimal("0.5")
# ShareSansar publishes % change to 2 decimals, and in the closing-VWAP era it was
# computed from the unrounded VWAP: gaps up to 0.0098 seen on 2025 sessions.
PCT_TOLERANCE = Decimal("0.01")
MAX_MISMATCHES = 25

SESSION_MINUTES = (SESSION_CLOSE.hour * 60 + SESSION_CLOSE.minute) - (SESSION_OPEN.hour * 60 + SESSION_OPEN.minute)


def bucket_index(moment, minutes, day):
    """Bucket of ``moment``: 0 starts at the open; pre-open fills fold into bucket 0, like the candles."""
    session_open, _ = session_bounds(day)
    return max(0, (moment.astimezone(NPT) - session_open) // timedelta(minutes=minutes))


def bucket_count(minutes, last_index=None):
    """Buckets covering the session (the last may be partial, e.g. 14:45-15:00 at 45M), plus any late trades."""
    count = -(-SESSION_MINUTES // minutes)
    return max(count, last_index + 1) if last_index is not None else count


def pct_change(value, base):
    if value is None or base is None or base <= 0:
        return None
    return (value - base) * HUNDRED / base


def roll_up(rows, minutes, day):
    """{company_id: {bucket index: cell}} from ordered per-minute rows."""
    grid = defaultdict(dict)
    for row in rows:
        cells = grid[row["company_id"]]
        index = bucket_index(row["minute"], minutes, day)
        cell = cells.get(index)
        if cell is None:
            cells[index] = {key: row[key] for key in ("open", "high", "low", "close", "volume", "turnover", "trade_count")}
            continue
        cell["high"] = max(cell["high"], row["high"])
        cell["low"] = min(cell["low"], row["low"])
        cell["close"] = row["close"]
        cell["volume"] += row["volume"]
        cell["turnover"] += row["turnover"]
        cell["trade_count"] += row["trade_count"]
    return grid


def add_derived(cells, prev_close):
    """VWAP, and % change against the previous bucket that traded (the first against the previous close)."""
    reference = prev_close
    for index in sorted(cells):
        cell = cells[index]
        cell["vwap"] = cell["turnover"] / cell["volume"] if cell["volume"] else None
        cell["change_pct"] = pct_change(cell["close"], reference)
        reference = cell["close"]


def available_dates(company_ids=None):
    """Newest-first dates that have timestamped trades for the companies."""
    trades = FloorsheetTransaction.objects.filter(trade_time__isnull=False, company__in=tracked_companies(company_ids))
    return list(trades.order_by("-date").values_list("date", flat=True).distinct()[:RECENT_DATES])


def daily_reference(day, company_ids):
    """
    {company_id: {prev_close, official_close, published_change_pct, volume, transactions, turnover}}.

    Previous close comes from movers (adjusted for bonus / right shares when the
    exchange's % says so).  Before the day's prices are crawled, the previous
    close is the latest crawled close and the official figures are missing.
    """
    as_of, base_date, _ = resolve_sessions(day)
    if as_of is None:
        return {}
    if as_of == day:
        rows = annotated_companies(day, base_date, [day], company_ids).values(
            "id", "prev_close", "close", "source_pct_today", "volume", "transactions", "turnover",
        )
        return {
            row["id"]: {
                "prev_close": row["prev_close"],
                "official_close": row["close"],
                "published_change_pct": row["source_pct_today"],
                "volume": row["volume"],
                "transactions": row["transactions"],
                "turnover": row["turnover"],
            }
            for row in rows
        }
    closes = DailyPrice.objects.filter(source=PRICE_SOURCE, date=as_of, company_id__in=company_ids)
    return {
        company_id: {"prev_close": close, "official_close": None, "published_change_pct": None,
                     "volume": None, "transactions": None, "turnover": None}
        for company_id, close in closes.values_list("company_id", "close")
    }


def raw_trades(day, company_ids):
    """{company_id: [(trade_time, transaction_id, quantity, rate, amount)]} in trade order."""
    trades = defaultdict(list)
    rows = (
        FloorsheetTransaction.objects
        .filter(date=day, trade_time__isnull=False, company_id__in=company_ids)
        .order_by("company_id", "trade_time", "transaction_id", "pk")
        .values_list("company_id", "trade_time", "transaction_id", "quantity", "rate", "amount")
    )
    for company_id, *trade in rows:
        trades[company_id].append(tuple(trade))
    return trades


def closing_rule(day):
    rule = None
    for start, name in settings.NEPSE_CLOSING_PRICE_RULES:
        if date.fromisoformat(start) <= day:
            rule = name
    return rule


def session_close(trades, day):
    """The exchange's closing price under the rule in force on ``day`` (see settings.NEPSE_CLOSING_PRICE_RULES)."""
    if not trades:
        return None
    lots = [t for t in trades if t[2] >= ROUND_LOT] or trades
    if closing_rule(day) == "closing_vwap":
        window_start = datetime.combine(day, CLOSING_VWAP_FROM, tzinfo=NPT)
        window = [t for t in lots if t[0] >= window_start]
        if window:
            vwap = sum(t[2] * t[3] for t in window) / sum(t[2] for t in window)
            return vwap.quantize(Decimal("0.01"), ROUND_HALF_UP)
    return lots[-1][3]


def build_grid(day, minutes=DEFAULT_BUCKET_MINUTES, company_ids=None, with_checks=True):
    companies = list(tracked_companies(company_ids).order_by("symbol").values("id", "symbol", "name", "sector"))
    ids = [company["id"] for company in companies]
    rows = minute_rows(day, ids)
    grid = roll_up(rows, minutes, day)
    reference = daily_reference(day, ids)
    trades = raw_trades(day, ids)

    last_index = max((max(cells) for cells in grid.values() if cells), default=None)
    count = bucket_count(minutes, last_index)
    session_open, _ = session_bounds(day)
    buckets = [session_open + timedelta(minutes=minutes * i) for i in range(count)]

    result = []
    for company in companies:
        cid = company.pop("id")
        cells = grid.get(cid, {})
        ref = reference.get(cid, {})
        add_derived(cells, ref.get("prev_close"))
        close = session_close(trades.get(cid, []), day)
        last_cell = cells[max(cells)] if cells else None
        result.append({
            **company,
            "company_id": cid,
            "prev_close": ref.get("prev_close"),
            "official_close": ref.get("official_close"),
            "published_change_pct": ref.get("published_change_pct"),
            "session_close": close,
            "last_trade_close": last_cell["close"] if last_cell else None,
            "day_change_pct": pct_change(close, ref.get("prev_close")),
            "quantity": sum(c["volume"] for c in cells.values()),
            "trades": sum(c["trade_count"] for c in cells.values()),
            "turnover": sum((c["turnover"] for c in cells.values()), Decimal(0)),
            "cells": cells,
            "_ref": ref,
        })

    pre_open = sum(1 for company_trades in trades.values() for t in company_trades
                   if t[0].astimezone(NPT) < session_open)
    payload = {
        "date": day,
        "minutes": minutes,
        "status": "live" if day == timezone.localdate() and is_market_open() else "stored",
        "buckets": buckets,
        "pre_open_trades": pre_open,
        "companies": result,
    }
    if with_checks:
        payload["checks"] = run_checks(day, minutes, result, rows, trades)
    for company in result:
        company.pop("_ref")
    return payload


def _check(key, label, mismatches, compared, note=""):
    return {
        "key": key,
        "label": label,
        "status": "n/a" if not compared else ("fail" if mismatches else "pass"),
        "compared": compared,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches[:MAX_MISMATCHES],
        "note": note,
    }


def _bucket_label(buckets, index):
    return f"{buckets[index]:%H:%M}" if index is not None and index < len(buckets) else None


def run_checks(day, minutes, companies, rows, trades):
    """Validation checks 1-9 of the Floor Sheet Summary spec (10, responsiveness, is a frontend concern)."""
    session_open, _ = session_bounds(day)
    count = bucket_count(minutes, max((max(c["cells"]) for c in companies if c["cells"]), default=None))
    buckets = [session_open + timedelta(minutes=minutes * i) for i in range(count)]
    open_seconds = SESSION_OPEN.hour * 3600 + SESSION_OPEN.minute * 60
    checks = []

    def miss(company, bucket, field, expected, actual, source=""):
        return {"symbol": company["symbol"], "bucket": bucket, "field": field,
                "expected": expected, "actual": actual, "source": source}

    # 1-3: cell totals against the raw trades and the crawled daily row.
    totals = {}
    for company in companies:
        company_trades = trades.get(company["company_id"], [])
        totals[company["company_id"]] = {
            "quantity": sum(t[2] for t in company_trades),
            "trades": len(company_trades),
            "turnover": sum((t[2] * t[3] for t in company_trades), Decimal(0)),
        }
    for key, label, daily_field in (
        ("quantity", "Cell quantities add up to the day's traded quantity", "volume"),
        ("trades", "Cell trade counts add up to the day's trades", "transactions"),
        ("turnover", "Cell turnover adds up to the day's turnover", "turnover"),
    ):
        mismatches, compared = [], 0
        for company in companies:
            actual = company[key]
            expected = totals[company["company_id"]][key]
            if expected or actual:
                compared += 1
                if _differs(expected, actual, key == "turnover"):
                    mismatches.append(miss(company, None, key, expected, actual, "raw trades"))
            official = company["_ref"].get(daily_field)
            if official is not None and (expected or actual):
                if _differs(official, actual, key == "turnover", DAILY_TURNOVER_TOLERANCE):
                    mismatches.append(miss(company, None, key, official, actual, "crawled daily price"))
        checks.append(_check(key, label, mismatches, compared))

    # 4: VWAP inside the bucket's range.
    mismatches, compared = [], 0
    for company in companies:
        for index, cell in company["cells"].items():
            compared += 1
            if cell["vwap"] is None or not cell["low"] <= cell["vwap"] <= cell["high"]:
                mismatches.append(miss(company, _bucket_label(buckets, index), "vwap",
                                       f"{cell['low']}-{cell['high']}", cell["vwap"]))
    checks.append(_check("vwap", "Each VWAP lies within its bucket's low-high", mismatches, compared))

    # 5: change % recomputed from the closes.
    mismatches, compared = [], 0
    for company in companies:
        reference = company["prev_close"]
        for index in sorted(company["cells"]):
            cell = company["cells"][index]
            expected = (cell["close"] - reference) / reference * 100 if reference else None
            compared += 1
            if (expected is None) != (cell["change_pct"] is None) or (
                expected is not None and abs(expected - cell["change_pct"]) > Decimal("0.0001")
            ):
                mismatches.append(miss(company, _bucket_label(buckets, index), "change_pct", expected, cell["change_pct"]))
            reference = cell["close"]
    no_base = [c["symbol"] for c in companies if c["cells"] and c["prev_close"] is None]
    checks.append(_check("change", "Change % recomputes from the bucket closes", mismatches, compared,
                         f"No previous close for {', '.join(no_base)}: first bucket shows no change." if no_base else ""))

    # 6: regrouping to 5M (or 1M when viewing 5M) keeps every total.
    other = 5 if minutes == 1 else 1
    other_grid = roll_up(rows, other, day)
    mismatches, compared = [], 0
    for company in companies:
        cells = other_grid.get(company["company_id"], {})
        for field, key in (("volume", "quantity"), ("trade_count", "trades"), ("turnover", "turnover")):
            regrouped = sum((c[field] for c in cells.values()), Decimal(0) if field == "turnover" else 0)
            compared += 1
            if regrouped != company[key]:
                mismatches.append(miss(company, None, key, company[key], regrouped, f"{other}M regroup"))
    checks.append(_check("regroup", f"{minutes}M and {other}M grids have the same totals", mismatches, compared))

    # 7: every raw trade lands in exactly one cell, by an independent seconds-based rule.
    mismatches, compared = [], 0
    for company in companies:
        expected_cells = defaultdict(lambda: [0, 0])
        seen = set()
        for trade_time, transaction_id, quantity, *_ in trades.get(company["company_id"], []):
            compared += 1
            if transaction_id in seen:
                mismatches.append(miss(company, None, "duplicate transaction", transaction_id, "twice"))
            seen.add(transaction_id)
            local = trade_time.astimezone(NPT)
            seconds = local.hour * 3600 + local.minute * 60 + local.second
            index = max(0, (seconds - open_seconds) // (60 * minutes)) if local.date() == day else -1
            expected_cells[index][0] += quantity
            expected_cells[index][1] += 1
        for index in set(expected_cells) | set(company["cells"]):
            want = expected_cells.get(index, [0, 0])
            cell = company["cells"].get(index)
            got = [cell["volume"], cell["trade_count"]] if cell else [0, 0]
            if want != got:
                mismatches.append(miss(company, _bucket_label(buckets, index) or str(index),
                                       "quantity/trades", want, got))
    checks.append(_check("placement", "Every trade is in exactly one, correct bucket", mismatches, compared,
                         "Pre-open fills (before 11:00) are counted in the first bucket."))

    # 8: session close against the official close.
    mismatches, compared, odd_lot = [], 0, []
    for company in companies:
        official = company["official_close"]
        if official is None or company["session_close"] is None:
            continue
        compared += 1
        if _differs(official, company["session_close"], money=True):
            mismatches.append(miss(company, None, "close", official, company["session_close"], "crawled daily price"))
        if company["last_trade_close"] != company["session_close"]:
            odd_lot.append(f"{company['symbol']} (last trade {company['last_trade_close']})")
    rule = ("VWAP of round-lot trades from 14:45" if closing_rule(day) == "closing_vwap"
            else "last round-lot (10+ share) trade")
    note = f"Session close = {rule}."
    if odd_lot and closing_rule(day) == "last_trade":
        note += f" Last bucket's close differs for: {', '.join(odd_lot)}."
    checks.append(_check("close", "Session close equals the official close", mismatches, compared, note))

    # 9: DAY % against the exchange's published % change.
    mismatches, compared = [], 0
    for company in companies:
        published, ours = company["published_change_pct"], company["day_change_pct"]
        if published is None or ours is None:
            continue
        compared += 1
        if abs(published - ours) > PCT_TOLERANCE:
            mismatches.append(miss(company, None, "day_change_pct", published, ours.quantize(Decimal("0.0001")),
                                   "ShareSansar % change"))
    checks.append(_check("day_change", "DAY % matches the exchange's published % change", mismatches, compared))
    return checks


def _differs(expected, actual, money=False, tolerance=MONEY_TOLERANCE):
    if expected is None or actual is None:
        return expected is not actual
    if money:
        return abs(Decimal(expected) - Decimal(actual)) > tolerance
    return expected != actual


def _num(value, places=4):
    return None if value is None else round(float(value), places)


def serialize_grid(payload):
    """JSON-ready grid: numbers as floats (one session can be 279 x 240 cells), cells as sorted lists."""
    companies = []
    for company in payload["companies"]:
        companies.append({
            **{key: company[key] for key in ("company_id", "symbol", "name", "sector", "quantity", "trades")},
            **{key: _num(company[key]) for key in (
                "prev_close", "official_close", "published_change_pct", "session_close",
                "last_trade_close", "day_change_pct",
            )},
            "turnover": _num(company["turnover"], 2),
            "cells": [
                {
                    "i": index,
                    **{key: _num(cell[key]) for key in ("open", "high", "low", "close", "vwap", "change_pct")},
                    "quantity": cell["volume"],
                    "trades": cell["trade_count"],
                    "turnover": _num(cell["turnover"], 2),
                }
                for index, cell in sorted(company["cells"].items())
            ],
        })
    checks = [
        {**check, "mismatches": [
            {**m, "expected": None if m["expected"] is None else str(m["expected"]),
             "actual": None if m["actual"] is None else str(m["actual"])}
            for m in check["mismatches"]
        ]}
        for check in payload.get("checks", [])
    ]
    return {
        "date": payload["date"].isoformat(),
        "minutes": payload["minutes"],
        "status": payload["status"],
        "buckets": [f"{bucket.astimezone(NPT):%H:%M}" for bucket in payload["buckets"]],
        "pre_open_trades": payload["pre_open_trades"],
        "companies": companies,
        "checks": checks,
    }
