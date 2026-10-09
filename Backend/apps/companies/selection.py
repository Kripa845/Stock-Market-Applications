"""
Which companies the crawlers and the analysis rebuild work on.

One rule everywhere: ``is_active`` AND ``tracking.is_tracked``.  A company
added in the database (e.g. by ``seed_companies``) is picked up with no code
change; no symbol is ever hardcoded here.
"""

from apps.companies.models import Company


def tracked_active_companies():
    return Company.objects.filter(is_active=True, tracking__is_tracked=True).order_by("symbol")


def parse_symbols(value):
    """``"mnbbl, GUFL"`` -> ``["MNBBL", "GUFL"]``; ``None`` / blank -> ``[]``."""
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        parts = value
    else:
        parts = str(value).split(",")
    return sorted({str(part).strip().upper() for part in parts if str(part).strip()})


def select_crawl_companies(symbols=None):
    """
    Active, tracked companies, optionally narrowed to ``symbols``.

    Returns ``(queryset, unknown)``: ``unknown`` lists requested symbols that
    are not active-and-tracked in the database.  They are never crawled; the
    caller logs them.
    """
    companies = tracked_active_companies()
    requested = parse_symbols(symbols)
    if not requested:
        return companies, []
    companies = companies.filter(symbol__in=requested)
    found = set(companies.values_list("symbol", flat=True))
    return companies, [symbol for symbol in requested if symbol not in found]
