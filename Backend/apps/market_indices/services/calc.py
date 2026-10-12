"""
Pure calculation helpers (no Django imports) so they can be unit-tested anywhere.

Rule used everywhere: if a value cannot be computed honestly it is ``None``
(shown as "—" in the UI), never 0.
"""

from decimal import Decimal


def pct_change(current, previous):
    """(current - previous) / previous * 100, or None when there is no valid base."""
    if current is None or previous is None:
        return None
    previous = Decimal(previous)
    if previous == 0:
        return None
    return (Decimal(current) - previous) * 100 / previous


def pct_of(part, whole):
    """part / whole * 100, or None when part is unknown or whole is 0."""
    if part is None or not whole:
        return None
    return Decimal(part) * 100 / Decimal(whole)


def diff(current, previous):
    if current is None or previous is None:
        return None
    return Decimal(current) - Decimal(previous)


def build_sector_rows(today, previous):
    """
    Build the Sub Index / Market % rows from two aggregated sector dicts.

    ``today`` / ``previous``: {sector: {"turnover", "volume", "transactions",
    "companies", "transactions_reported"}}  (values may be None).
    Returns (rows, totals).  Shares are relative to the sum over ALL rows in
    ``today``, so each share column adds up to 100.
    """

    def total(key):
        return sum((Decimal(r[key]) for r in today.values() if r.get(key) is not None), Decimal(0))

    totals = {
        "turnover": total("turnover"),
        "volume": total("volume"),
        "transactions": total("transactions"),
    }

    rows = []
    for sector in sorted(today):
        t = today[sector]
        p = previous.get(sector) or {}
        rows.append({
            "sector": sector,
            "companies": t.get("companies", 0),
            "turnover": t.get("turnover"),
            "tu_ch": diff(t.get("turnover"), p.get("turnover")),
            "tu_ch_pct": pct_change(t.get("turnover"), p.get("turnover")),
            "volume": t.get("volume"),
            "vol_ch": diff(t.get("volume"), p.get("volume")),
            "vol_ch_pct": pct_change(t.get("volume"), p.get("volume")),
            "transactions": t.get("transactions"),
            "trans_ch": diff(t.get("transactions"), p.get("transactions")),
            "trans_ch_pct": pct_change(t.get("transactions"), p.get("transactions")),
            # False when some stocks in the sector have no transaction count yet.
            "transactions_complete": t.get("transactions_reported") == t.get("companies"),
            "turnover_share_pct": pct_of(t.get("turnover"), totals["turnover"]),
            "volume_share_pct": pct_of(t.get("volume"), totals["volume"]),
            "transactions_share_pct": pct_of(t.get("transactions"), totals["transactions"]),
        })
    return rows, totals
