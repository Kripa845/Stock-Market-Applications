

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
   
    companies = tracked_active_companies()
    requested = parse_symbols(symbols)
    if not requested:
        return companies, []
    companies = companies.filter(symbol__in=requested)
    found = set(companies.values_list("symbol", flat=True))
    return companies, [symbol for symbol in requested if symbol not in found]
