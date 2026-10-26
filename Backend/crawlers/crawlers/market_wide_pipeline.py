
import logging
import os
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

logger = logging.getLogger(__name__)


def _ensure_django():
    """Same bootstrap idea as crawlers.pipelines: make `apps.*` importable."""
    backend_dir = Path(__file__).resolve().parents[2]   # .../Backend
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    from django.apps import apps

    if not apps.ready:
        django.setup()


def parse_decimal(value):
    """'1,23,456.70' -> Decimal; '', '-', None, garbage -> None (never 0)."""
    if value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    text = str(value).strip().replace(",", "")
    if text in ("", "-", "--", "N/A", "n/a"):
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def parse_int(value):
    number = parse_decimal(value)
    return int(number) if number is not None else None


class MarketWidePipeline:
    # Scrapy runs on the asyncio reactor, where Django refuses synchronous ORM
    # calls (SynchronousOnlyOperation aborts the crawl); like crawlers.pipelines,
    # every database call runs in a thread via deferToThread.

    def open_spider(self, spider):
        from twisted.internet.threads import deferToThread

        return deferToThread(self._load_lookups, spider)

    def _load_lookups(self, spider):
        _ensure_django()
        from apps.market_indices.models import StockSector
        from apps.market_indices.sectors import normalise_sector

        self.counters = {"stock_rows": 0, "unclassified": 0, "skipped": 0}
        self._unclassified_logged = set()

        self.sectors = dict(StockSector.objects.values_list("symbol", "sector"))
        self._normalise_sector = normalise_sector

        # Tracked companies already have a sector; use it as a fallback only.
        from apps.companies.models import Company

        self.company_sectors = {}
        for symbol, sector in Company.objects.values_list("symbol", "sector"):
            normalised = normalise_sector(sector)
            if normalised:
                self.company_sectors[symbol.upper()] = normalised

    def close_spider(self, spider):
        spider.logger.info("MarketWidePipeline: %s", self.counters)

    def process_item(self, item, spider):
        from twisted.internet.threads import deferToThread

        return deferToThread(self._process_sync, item, spider)

    def _process_sync(self, item, spider):
        kind = item.get("item_type")
        if kind == "market_stock_daily":
            self._save_stock(item, spider)
        return item

    # ------------------------------------------------------------------

    def _save_stock(self, item, spider):
        from apps.market_indices.models import MarketStockDaily

        symbol = (item.get("symbol") or "").strip().upper()
        if not symbol or item.get("date") is None:
            self.counters["skipped"] += 1
            return

        sector = (
            self.sectors.get(symbol)
            or self._normalise_sector(item.get("sector_raw"))
            or self.company_sectors.get(symbol)
        )
        if not sector:
            sector = MarketStockDaily.UNCLASSIFIED
            self.counters["unclassified"] += 1
            if symbol not in self._unclassified_logged:
                self._unclassified_logged.add(symbol)
                spider.logger.warning("No sector for %s: add it to the stock_sectors CSV", symbol)

        MarketStockDaily.objects.update_or_create(
            symbol=symbol,
            date=item["date"],
            defaults={
                "sector": sector,
                "close": parse_decimal(item.get("close")),
                "prev_close": parse_decimal(item.get("prev_close")),
                "volume": parse_int(item.get("volume")) or 0,
                "turnover": parse_decimal(item.get("turnover")) or Decimal("0"),
                "transactions": parse_int(item.get("transactions")),
                "source": "crawled",
            },
        )
        self.counters["stock_rows"] += 1