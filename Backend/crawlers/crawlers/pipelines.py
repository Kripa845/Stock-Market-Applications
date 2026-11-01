import json
import os
import sys
import re
import threading
import nepali_datetime
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
from twisted.internet.threads import deferToThread

from pathlib import Path
import requests
from asgiref.sync import sync_to_async

BASE_DIR = Path(__file__).resolve().parents[2]

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings",
)
NEPAL_TZ = ZoneInfo("Asia/Kathmandu")
import django

django.setup()

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from itemadapter import ItemAdapter



from apps.crawler_runs.models import CrawlRun
from apps.news.services.article_images import extract_image_url
from apps.news.services.ingest import IngestRejected, ingest_article, resolve_source
from apps.news.tasks import categorize_article_task
from apps.companies.models import Company
from apps.floorsheet.models import Broker, FloorsheetTransaction
from apps.market_data.models import DailyPrice



def parse_integer(value):
    if value is None or value == "":
        return None

    return int(float(str(value).replace(",", "").strip()))


def parse_decimal(value):
    if value is None or value == "":
        return None

    return Decimal(str(value).replace(",", "").strip())
def clean_text(value):
    if value is None:
        return ""

    return " ".join(str(value).split()).strip()


def clean_body(value):
    if value is None:
        return ""

    if isinstance(value, (list, tuple)):
        parts = []

        for part in value:
            text = clean_text(part)
            if text:
                parts.append(text)

        return "\n\n".join(parts).strip()

    return str(value).strip()
def normalize_datetime(value):

    if value is None or value == "":
        return None

    # ---------------------------------------------------------
    # Already a Python datetime
    # ---------------------------------------------------------
    if isinstance(value, datetime):

        dt = value

        if timezone.is_naive(dt):
            dt = timezone.make_aware(
                dt,
                NEPAL_TZ,
            )

        return dt

    if not isinstance(value, str):
        return None

    value = clean_text(value)

    # ---------------------------------------------------------
    # Convert Nepali numerals to English numerals
    #
    # १२ श्रावण २०८३
    # ->
    # 12 श्रावण 2083
    # ---------------------------------------------------------
    value = value.translate(
        str.maketrans(
            "०१२३४५६७८९",
            "0123456789",
        )
    )

    # ---------------------------------------------------------
    # Bikram Sambat month mapping
    # ---------------------------------------------------------
    bs_months = {
        "बैशाख": 1,
        "बैसाख": 1,
        "जेठ": 2,
        "असार": 3,
        "श्रावण": 4,
        "साउन": 4,
        "भाद्र": 5,
        "भाद्रपद": 5,
        "आश्विन": 6,
        "कार्तिक": 7,
        "मंसिर": 8,
        "पौष": 9,
        "माघ": 10,
        "फाल्गुण": 11,
        "फाल्गुन": 11,
        "चैत्र": 12,
    }

    # ---------------------------------------------------------
    # Detect Bikram Sambat date
    #
    # Example:
    # 12 श्रावण 2083, मंगलवार 15:50
    #
    # Also supports:
    # 12 श्रावण 2083
    # ---------------------------------------------------------
    bs_pattern = re.compile(
        r"(?P<day>\d{1,2})\s+"
        r"(?P<month>"
        r"बैशाख|बैसाख|"
        r"जेठ|"
        r"असार|"
        r"श्रावण|साउन|"
        r"भाद्र|भाद्रपद|"
        r"आश्विन|"
        r"कार्तिक|"
        r"मंसिर|"
        r"पौष|"
        r"माघ|"
        r"फाल्गुण|फाल्गुन|"
        r"चैत्र"
        r")\s+"
        r"(?P<year>\d{4})"
        r"(?:.*?"
        r"(?P<hour>\d{1,2}):"
        r"(?P<minute>\d{2}))?"
    )

    match = bs_pattern.search(value)

    if match:

        day = int(match.group("day"))
        year = int(match.group("year"))
        month_name = match.group("month")

        month = bs_months.get(month_name)

        if month is None:
            return None

        hour = (
            int(match.group("hour"))
            if match.group("hour")
            else 0
        )

        minute = (
            int(match.group("minute"))
            if match.group("minute")
            else 0
        )

        try:

            # -------------------------------------------------
            # Create Bikram Sambat datetime
            # -------------------------------------------------
            bs_dt = nepali_datetime.datetime(
                year,
                month,
                day,
                hour,
                minute,
            )

            # -------------------------------------------------
            # Convert BS date -> AD date
            # -------------------------------------------------
            ad_date = bs_dt.to_datetime_date()

            # -------------------------------------------------
            # Create normal Python datetime
            # -------------------------------------------------
            dt = datetime(
                ad_date.year,
                ad_date.month,
                ad_date.day,
                hour,
                minute,
            )

            # -------------------------------------------------
            # Nepal timezone
            # -------------------------------------------------
            dt = timezone.make_aware(
                dt,
                NEPAL_TZ,
            )

            return dt

        except (
            ValueError,
            TypeError,
        ):

            return None

    # ---------------------------------------------------------
    # Gregorian formats
    # ---------------------------------------------------------
    formats = [
        "%a, %b %d, %Y %I:%M %p",
        "%a, %b %d, %Y %I:%M:%S %p",
        "%B %d, %Y, %I:%M:%S %p",
        "%B %d, %Y, %I:%M %p",
        "%B %d, %Y %I:%M:%S %p",
        "%B %d, %Y %I:%M %p",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    ]

    dt = None

    for fmt in formats:

        try:

            dt = datetime.strptime(
                value,
                fmt,
            )

            break

        except ValueError:

            continue

    # ---------------------------------------------------------
    # dateutil fallback
    # ---------------------------------------------------------
    if dt is None:

        try:

            from dateutil import parser as date_parser

            dt = date_parser.parse(
                value,
                fuzzy=True,
            )

        except (
            ValueError,
            TypeError,
            OverflowError,
        ):

            return None

    # ---------------------------------------------------------
    # Make timezone aware
    # ---------------------------------------------------------
    if timezone.is_naive(dt):

        dt = timezone.make_aware(
            dt,
            NEPAL_TZ,
        )

    return dt

def update_crawl_metrics(spider, status=None):
    crawl_run_id = getattr(spider, "crawl_run_id", None)

    if not crawl_run_id:
        return

    try:
        crawl_run = CrawlRun.objects.get(pk=crawl_run_id)
        source = getattr(spider, "name", "")
        update_fields = []

        if source in {"sharesansar", "merolagani", "bizmandu", "nepsealpha", "arthakhabar", "fiscalnepal"}:
            crawl_run.articles_found = getattr(spider, "articles_seen", 0)
            crawl_run.articles_created = getattr(spider, "news_created", 0)
            crawl_run.articles_updated = getattr(spider, "news_updated", 0)
            crawl_run.articles_duplicate = getattr(spider, "news_duplicate", 0)
            update_fields += ["articles_found", "articles_created", "articles_updated", "articles_duplicate"]
        elif source == "trading_data":
            crawl_run.prices_found = getattr(spider, "prices_found", 0)
            crawl_run.prices_created = getattr(spider, "prices_created", 0)
            crawl_run.prices_updated = getattr(spider, "prices_updated", 0)
            update_fields += ["prices_found", "prices_created", "prices_updated"]
        elif source == "floorsheet":
            crawl_run.floorsheet_found = getattr(spider, "floorsheet_found", 0)
            crawl_run.floorsheet_created = getattr(spider, "floorsheet_created", 0)
            crawl_run.floorsheet_updated = getattr(spider, "floorsheet_updated", 0)
            update_fields += ["floorsheet_found", "floorsheet_created", "floorsheet_updated"]

        if status:
            crawl_run.status = status
            update_fields.append("status")

        if status in {CrawlRun.Status.SUCCESS, CrawlRun.Status.FAILED}:
            crawl_run.completed_at = timezone.now()
            update_fields.append("completed_at")

        if update_fields:
            crawl_run.save(update_fields=update_fields)
    except Exception as exc:
        spider.logger.exception("Failed to update CrawlRun %s: %s", crawl_run_id, exc)




class CrawlRunPipeline:
  

    def open_spider(self, spider):
        return deferToThread(
            self._create_crawl_run,
            spider,
        )

    @staticmethod
    def _create_crawl_run(spider):
        source = getattr(
            spider,
            "source",
            getattr(
                spider,
                "SOURCE",
                spider.name,
            ),
        )

        try:
            crawl_run_id = getattr(spider, "crawl_run_id", None)
            if crawl_run_id:
                crawl_run = CrawlRun.objects.get(pk=crawl_run_id)
                if source not in crawl_run.sources:
                    crawl_run.sources = [*crawl_run.sources, source]
                crawl_run.status = CrawlRun.Status.RUNNING
                crawl_run.started_at = crawl_run.started_at or timezone.now()
                crawl_run.save(update_fields=["sources", "status", "started_at"])
            else:
                crawl_run = CrawlRun.objects.create(
                    status=CrawlRun.Status.RUNNING,
                    started_at=timezone.now(),
                    sources=[source],
                )
                spider.owns_crawl_run = True

            spider.crawl_run = crawl_run
            spider.crawl_run_id = crawl_run.id

            spider.logger.info(
                "CrawlRun %s started for %s",
                crawl_run.id,
                source,
            )

        except Exception as exc:
            spider.crawl_run = None
            spider.crawl_run_id = None

            spider.logger.exception(
                "Could not create CrawlRun for %s: %s",
                source,
                exc,
            )

    def process_item(self, item, spider):
        return item

    def close_spider(self, spider):
        return deferToThread(
            self._complete_crawl_run,
            spider,
        )

    @staticmethod
    def _complete_crawl_run(spider):
        crawl_run_id = getattr(
            spider,
            "crawl_run_id",
            None,
        )

        if not crawl_run_id:
            return

        try:
            # One CrawlRun spans several spider processes (crawler_runs.tasks.run_crawl),
            # so add this spider's article counts instead of overwriting the others'.
            found = getattr(spider, "articles_seen", None)
            if found is None:
                found = sum(
                    getattr(spider, name, 0)
                    for name in ("news_created", "news_updated", "news_duplicate", "news_failed", "news_rejected")
                )
            CrawlRun.objects.filter(pk=crawl_run_id).update(
                articles_found=F("articles_found") + found,
                articles_created=F("articles_created") + getattr(spider, "news_created", 0),
                articles_updated=F("articles_updated") + getattr(spider, "news_updated", 0),
                articles_duplicate=F("articles_duplicate") + getattr(spider, "news_duplicate", 0),
            )
            crawl_run = CrawlRun.objects.get(pk=crawl_run_id)
            update_fields = []

            # A run handed in by the Celery task is finalised by that task once every
            # spider is done; marking it SUCCESS here would end it between spiders.
            if getattr(spider, "owns_crawl_run", False):
                crawl_run.status = CrawlRun.Status.SUCCESS
                crawl_run.completed_at = timezone.now()
                update_fields += ["status", "completed_at"]

            if spider.name == "trading_data":
                crawl_run.prices_found = getattr(spider, "prices_found", 0)
                crawl_run.prices_created = getattr(spider, "prices_created", 0)
                crawl_run.prices_updated = getattr(spider, "prices_updated", 0)
                update_fields += ["prices_found", "prices_created", "prices_updated"]
            elif spider.name == "floorsheet":
                crawl_run.floorsheet_found = getattr(spider, "floorsheet_found", 0)
                crawl_run.floorsheet_created = getattr(spider, "floorsheet_saved", 0)
                crawl_run.floorsheet_updated = 0
                update_fields += ["floorsheet_found", "floorsheet_created", "floorsheet_updated"]

            if update_fields:
                crawl_run.save(update_fields=update_fields)

            spider.logger.info(
                "CrawlRun %s completed | found=%s | created=%s | "
                "updated=%s | duplicate=%s | failed=%s | rejected=%s",
                crawl_run.id,
                crawl_run.articles_found,
                crawl_run.articles_created,
                crawl_run.articles_updated,
                crawl_run.articles_duplicate,
                getattr(spider, "news_failed", 0),
                getattr(spider, "news_rejected", 0),
            )

        except Exception as exc:
            spider.logger.exception(
                "Failed to finalize CrawlRun %s: %s",
                crawl_run_id,
                exc,
            )




class NewsPipeline:
    """Validates scraped items and hands them to apps/news/services/ingest.py,
    which owns de-duplication and provenance."""

    def open_spider(self, spider):
        self.counts = {"inserted": 0, "updated": 0, "duplicate": 0, "failed": 0, "rejected": 0}
        # Items are ingested on deferToThread's pool; `+=` from several threads loses counts.
        self.count_lock = threading.Lock()

        spider.news_created = 0
        spider.news_updated = 0
        spider.news_duplicate = 0
        spider.news_failed = 0
        spider.news_rejected = 0

        self.spider_label = getattr(spider, "source", getattr(spider, "SOURCE", spider.name))
        # label -> NewsSource id; filled on the worker thread (no ORM in the asyncio loop).
        self.source_ids = {}
        spider.logger.info("News pipeline started for %s", self.spider_label)

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        if adapter.get("item_type", "news") != "news":
            return item

        url = clean_text(adapter.get("url"))
        raw_html = adapter.get("raw_html", "")
        crawl_run_id = getattr(spider, "crawl_run_id", None)

        if not crawl_run_id:
            self._count(spider, "failed")
            spider.logger.error("Cannot save article because CrawlRun was not created: %s", url)
            return item

        # A spider may emit items for another portal than its own label.
        label = clean_text(adapter.get("source")) or self.spider_label
        raw_item = {
            "url": url,
            "headline": clean_text(adapter.get("headline")),
            "body": clean_body(adapter.get("body")),
            "published_at": normalize_datetime(adapter.get("published_at")),
            "external_id": adapter.get("external_id"),
            # A spider may set image_url itself; otherwise take the lead image from the page.
            "image_url": adapter.get("image_url") or extract_image_url(raw_html, url),
            "raw_html": raw_html,
            "http_status": adapter.get("http_status", 200),
        }
        return deferToThread(self._ingest_sync, item, spider, label, crawl_run_id, raw_item)

    _SPIDER_COUNTERS = {
        "inserted": "news_created",
        "updated": "news_updated",
        "duplicate": "news_duplicate",
        "failed": "news_failed",
        "rejected": "news_rejected",
    }

    def _count(self, spider, status):
        attr = self._SPIDER_COUNTERS[status]
        with self.count_lock:
            self.counts[status] += 1
            setattr(spider, attr, getattr(spider, attr, 0) + 1)

    def _source_id(self, label):
        if label not in self.source_ids:
            source = resolve_source(label)
            self.source_ids[label] = source.pk if source else None
        return self.source_ids[label]

    def _ingest_sync(self, item, spider, label, crawl_run_id, raw_item):
        url = raw_item["url"]
        source_id = self._source_id(label)
        if source_id is None:
            self._count(spider, "failed")
            spider.logger.error(
                "No NewsSource matches %r: add one (see apps/news/README.md); skipping %s", label, url,
            )
            return item
        try:
            result = ingest_article(source_id, raw_item, ingest_run_id=crawl_run_id)
        except IngestRejected as exc:
            self._count(spider, "rejected")
            spider.logger.warning("Skipping article: %s", exc)
            return item
        except Exception as exc:
            self._count(spider, "failed")
            spider.logger.exception("Failed to save article %s: %s", url, exc)
            return item

        self._count(spider, result.status)

        if result.status in {"inserted", "updated"}:
            # Re-categorise edited articles too; manual tags are never overwritten.
            try:
                categorize_article_task.delay(result.article_id)
            except Exception as exc:
                # The article is saved; `categorize_news` can tag it later.
                spider.logger.warning("Could not queue categorisation for %s: %s", result.article_id, exc)

        spider.logger.info(
            "News article %s | id=%s | duplicate_of=%s | %s",
            result.status, result.article_id, result.duplicate_of_id, url,
        )
        return item

    def close_spider(self, spider):
        spider.logger.info(
            "News pipeline finished | inserted=%s | updated=%s | duplicate=%s | failed=%s | rejected=%s",
            self.counts["inserted"],
            self.counts["updated"],
            self.counts["duplicate"],
            self.counts["failed"],
            self.counts["rejected"],
        )




class TradingDataPipeline:
   

    def open_spider(self, spider):
        self.file = open(
            "trading_data.json",
            "w",
            encoding="utf-8",
        )

        self.file.write("[\n")
        self.first_item = True
        spider.prices_found = 0
        spider.prices_created = 0
        spider.prices_updated = 0

    def process_item(self, item, spider):
        if "open" not in item:
            return item

        return deferToThread(
            self._process_sync,
            item,
            spider,
        )

    def _process_sync(self, item, spider):
        symbol = clean_text(
            item.get("company")
        ).upper()

        if not symbol:
            spider.logger.error(
                "Trading data does not contain company symbol.",
            )
            return item

        try:
            company = Company.objects.get(
                symbol=symbol,
                is_active=True,
            )

        except Company.DoesNotExist:
            spider.logger.error(
                "Company '%s' does not exist in database.",
                symbol,
            )
            return item

        date_value = item.get("date")

        if not date_value:
            spider.logger.error(
                "Missing trading date for %s.",
                symbol,
            )
            return item

        try:
            if isinstance(
                date_value,
                datetime,
            ):
                trading_date = date_value.date()

            else:
                trading_date = datetime.strptime(
                    str(date_value),
                    "%Y-%m-%d",
                ).date()

        except ValueError:
            spider.logger.error(
                "Invalid date '%s' for %s.",
                date_value,
                symbol,
            )
            return item

        try:
            open_price = Decimal(
                str(
                    item.get("open")
                    or "0"
                ).replace(",", "")
            )

            high_price = Decimal(
                str(
                    item.get("high")
                    or "0"
                ).replace(",", "")
            )

            low_price = Decimal(
                str(
                    item.get("low")
                    or "0"
                ).replace(",", "")
            )

            close_price = Decimal(
                str(
                    item.get("close")
                    or "0"
                ).replace(",", "")
            )

            turnover = Decimal(
                str(
                    item.get("turnover")
                    or "0"
                ).replace(",", "")
            )

            volume = int(
                Decimal(
                    str(
                    item.get("volume")
                    or "0"
                ).replace(",", "")
            )
            )

        except (
            InvalidOperation,
            ValueError,
        ):
            spider.logger.error(
                "Invalid numeric data for %s on %s.",
                symbol,
                trading_date,
            )
            return item

        # Optional source "% change": an unparseable value is logged and
        # skipped, it never rejects the row.
        source_change_pct = None
        raw_change = item.get("source_change_pct")
        if raw_change not in (None, ""):
            try:
                source_change_pct = Decimal(str(raw_change).replace(",", "").strip())
            except (InvalidOperation, ValueError):
                spider.logger.warning(
                    "Invalid source_change_pct %r for %s on %s; stored as NULL.",
                    raw_change,
                    symbol,
                    trading_date,
                )

        if any(
            value < 0
            for value in (
                open_price,
                high_price,
                low_price,
                close_price,
            )
        ):
            spider.logger.error(
                "Negative price detected for %s on %s.",
                symbol,
                trading_date,
            )
            return item

        if volume < 0:
            spider.logger.error(
                "Negative volume detected for %s on %s.",
                symbol,
                trading_date,
            )
            return item

        if turnover < 0:
            spider.logger.error(
                "Negative turnover detected for %s on %s.",
                symbol,
                trading_date,
            )
            return item

        if high_price < low_price:
            spider.logger.error(
                "High price is lower than low price for %s on %s.",
                symbol,
                trading_date,
            )
            return item

        defaults = {
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "volume": volume,
            "turnover": turnover,
            "source": "crawled",
        }
        # Only ever set, never cleared: a later crawl without the column
        # keeps the value already stored.
        if source_change_pct is not None:
            defaults["source_change_pct"] = source_change_pct

        try:
            _, created = (
                DailyPrice.objects.update_or_create(
                    company=company,
                    date=trading_date,
                    defaults=defaults,
                )
            )

        except IntegrityError as exc:
            spider.logger.error(
                "Database error saving %s on %s: %s",
                symbol,
                trading_date,
                exc,
            )
            return item

        spider.logger.info(
            "%s | %s | %s | close=%s",
            "CREATED" if created else "UPDATED",
            symbol,
            trading_date,
            close_price,
        )

        spider.prices_found += 1
        if created:
            spider.prices_created += 1
        else:
            spider.prices_updated += 1

        if self.first_item:
            self.first_item = False
        else:
            self.file.write(",\n")

        self.file.write(
            json.dumps(
                dict(item),
                ensure_ascii=False,
                default=str,
            )
        )

        return item

    def close_spider(self, spider):
        if getattr(
            self,
            "file",
            None,
        ):
            self.file.write("\n]\n")
            self.file.close()


# ======================================================================
# FLOORSHEET PIPELINE
# ======================================================================


class FloorsheetPipeline:
    """
    Persists FloorsheetTransaction rows and writes floorsheet.json.

    All Django ORM operations are executed inside deferToThread()
    because Scrapy is running with an asyncio reactor.
    """

    def open_spider(self, spider):
        self.file = open(
            "floorsheet.json",
            "w",
            encoding="utf-8",
        )

        self.file.write("[\n")
        self.first_item = True

        self.saved_count = 0
        self.skipped_count = 0
        self.failed_count = 0

        spider.floorsheet_found = 0
        spider.floorsheet_saved = 0
        spider.floorsheet_failed = 0
        spider.floorsheet_created = 0
        spider.floorsheet_updated = 0

    def process_item(self, item, spider):
        required_keys = {
            "buyer_broker",
            "seller_broker",
            "quantity",
            "rate",
        }

        if not any(key in item for key in required_keys):
            return item

        spider.floorsheet_found += 1

        # --------------------------------------------------------------
        # Keep raw JSON output regardless of database result.
        # --------------------------------------------------------------

        if self.first_item:
            self.first_item = False
        else:
            self.file.write(",\n")

        self.file.write(
            json.dumps(
                dict(item),
                ensure_ascii=False,
                default=str,
            )
        )

        return deferToThread(
            self._save_transaction_sync,
            item,
            spider,
        )

    def _save_transaction_sync(self, item, spider):
        # --------------------------------------------------------------
        # COMPANY
        # --------------------------------------------------------------

        symbol = clean_text(
            item.get("company")
        ).upper()

        if not symbol:
            self.skipped_count += 1

            spider.logger.error(
                "Floorsheet row missing company symbol."
            )

            return item

        try:
            company = Company.objects.get(
                symbol=symbol,
                is_active=True,
            )

        except Company.DoesNotExist:
            self.skipped_count += 1

            spider.logger.error(
                "Floorsheet row skipped: unknown company '%s'.",
                symbol,
            )

            return item

        # --------------------------------------------------------------
        # DATE
        # --------------------------------------------------------------

        raw_date = item.get("date")

        if not raw_date:
            self.skipped_count += 1

            spider.logger.error(
                "Floorsheet row missing date for %s.",
                symbol,
            )

            return item

        trading_datetime = normalize_datetime(
            raw_date
        )

        if trading_datetime is None:
            self.skipped_count += 1

            spider.logger.error(
                "Floorsheet row has unparseable date '%s' for %s.",
                raw_date,
                symbol,
            )

            return item

        trading_date = trading_datetime.date()
        raw_trade_time = item.get("trade_time")
        trading_time = normalize_datetime(raw_trade_time) if raw_trade_time else None
        if isinstance(raw_trade_time, str) and re.fullmatch(r"\s*\d{1,2}:\d{2}(?::\d{2})?\s*", raw_trade_time):
            trading_time = normalize_datetime(f"{trading_date.isoformat()} {raw_trade_time.strip()}")

        # --------------------------------------------------------------
        # BROKER / TRANSACTION INFORMATION
        # --------------------------------------------------------------

        buyer_broker = clean_text(
            item.get("buyer_broker")
        )

        seller_broker = clean_text(
            item.get("seller_broker")
        )

        transaction_id = clean_text(
            item.get("transaction_id")
        )

        # --------------------------------------------------------------
        # NUMERIC DATA
        # --------------------------------------------------------------

        raw_quantity = item.get("quantity")
        raw_rate = item.get("rate")
        raw_amount = item.get("amount")

        quantity = parse_integer(
            raw_quantity
        )

        rate = parse_decimal(
            raw_rate
        )

        amount = None

        if quantity is not None and rate is not None:
            amount = rate * quantity

        # --------------------------------------------------------------
        # VALIDATE NUMERIC DATA
        # --------------------------------------------------------------

        if quantity is None:
            self.failed_count += 1
            spider.floorsheet_failed += 1

            spider.logger.error(
                "Invalid quantity | company=%s | date=%s | "
                "raw_quantity=%r | raw_rate=%r | raw_amount=%r",
                symbol,
                trading_date,
                raw_quantity,
                raw_rate,
                raw_amount,
            )

            return item

        if rate is None:
            self.failed_count += 1
            spider.floorsheet_failed += 1

            spider.logger.error(
                "Invalid rate | company=%s | date=%s | "
                "raw_quantity=%r | raw_rate=%r | raw_amount=%r",
                symbol,
                trading_date,
                raw_quantity,
                raw_rate,
                raw_amount,
            )

            return item

        if amount is None:
            self.failed_count += 1
            spider.floorsheet_failed += 1

            spider.logger.error(
                "Could not calculate amount | company=%s | date=%s | "
                "quantity=%r | rate=%r",
                symbol,
                trading_date,
                quantity,
                rate,
            )

            return item

        # --------------------------------------------------------------
        # NEGATIVE VALUE VALIDATION
        # --------------------------------------------------------------

        if quantity < 0:
            self.failed_count += 1
            spider.floorsheet_failed += 1

            spider.logger.error(
                "Negative quantity | company=%s | date=%s | quantity=%s",
                symbol,
                trading_date,
                quantity,
            )

            return item

        if rate < 0:
            self.failed_count += 1
            spider.floorsheet_failed += 1

            spider.logger.error(
                "Negative rate | company=%s | date=%s | rate=%s",
                symbol,
                trading_date,
                rate,
            )

            return item

        if amount < 0:
            self.failed_count += 1
            spider.floorsheet_failed += 1

            spider.logger.error(
                "Negative amount | company=%s | date=%s | amount=%s",
                symbol,
                trading_date,
                amount,
            )

            return item

        # --------------------------------------------------------------
        # DATABASE
        # --------------------------------------------------------------

        transaction_key = (
            transaction_id
            or f"{buyer_broker}-{seller_broker}-{quantity}-{rate}"
        )
        defaults = {
            "buyer_broker": buyer_broker,
            "seller_broker": seller_broker,
            "quantity": quantity,
            "rate": rate,
            "amount": amount,
        }
        # Preserve a source trade timestamp when supplied. A date-only
        # floorsheet row must not be assigned an invented intraday time.
        if trading_datetime.time().replace(tzinfo=None) != datetime.min.time():
            defaults["trade_time"] = trading_datetime
        if trading_time and trading_time.time().replace(tzinfo=None) != datetime.min.time():
            defaults["trade_time"] = trading_time

        try:
            _, created = (
                FloorsheetTransaction.objects.update_or_create(
                    company=company,
                    date=trading_date,
                    transaction_id=transaction_key,
                    defaults=defaults,
                )
            )

        except IntegrityError as exc:
            self.failed_count += 1
            spider.floorsheet_failed += 1

            spider.logger.error(
                "Database error saving floorsheet row | "
                "company=%s | date=%s | error=%s",
                symbol,
                trading_date,
                exc,
            )

            return item

        except Exception as exc:
            self.failed_count += 1
            spider.floorsheet_failed += 1

            spider.logger.exception(
                "Unexpected error saving floorsheet row | "
                "company=%s | date=%s | error=%s",
                symbol,
                trading_date,
                exc,
            )

            return item

        # --------------------------------------------------------------
        # SUCCESS
        # --------------------------------------------------------------

        self.saved_count += 1
        spider.floorsheet_saved += 1
        if created:
            spider.floorsheet_created += 1
        else:
            spider.floorsheet_updated += 1

        spider.logger.debug(
            "%s | floorsheet | %s | %s -> %s | "
            "qty=%s | rate=%s | amount=%s",
            "CREATED" if created else "UPDATED",
            symbol,
            trading_date,
            buyer_broker,
            seller_broker,
            quantity,
            rate,
            amount,
        )

        return item

    def close_spider(self, spider):
        if getattr(self, "file", None):
            self.file.write("\n]\n")
            self.file.close()

        spider.logger.info(
            "Floorsheet pipeline finished | "
            "found=%s | saved=%s | skipped=%s | failed=%s",
            getattr(spider, "floorsheet_found", 0),
            self.saved_count,
            self.skipped_count,
            self.failed_count,
        )


class BrokerPipeline:
    """Persist broker-directory items emitted by the brokers spider."""

    def process_item(self, item, spider):
        broker_no = int(item["broker_no"])
        name = clean_text(item.get("name"))
        tms_link = clean_text(item.get("tms_link"))
        legacy_row = Broker.objects.filter(
            broker_no__isnull=True,
            broker_code=str(broker_no),
        ).first()
        if legacy_row:
            legacy_row.broker_no = broker_no
            legacy_row.save(update_fields=["broker_no"])
        Broker.objects.update_or_create(
            broker_no=broker_no,
            defaults={
                "name": name,
                "tms_link": tms_link,
                # Keep the existing directory key populated for rows added by
                # the crawler; other broker endpoints still consume this code.
                "broker_code": str(broker_no),
            },
        )
        return item



class MoneymitraBrokerPipeline:
    def open_spider(self, spider):
        from django.conf import settings
        self.logo_dir = (
            Path(settings.BASE_DIR).parent / "frontend" / "public" / "broker-logos"
        )
        self.logo_dir.mkdir(parents=True, exist_ok=True)

    async def process_item(self, item, spider):
        return await sync_to_async(self._save, thread_sensitive=True)(item, spider)

    def _save(self, item, spider):
        from apps.floorsheet.models import Broker

        logo_name = ""
        if item["logo_url"]:
            ext = Path(item["logo_url"].split("?")[0]).suffix or ".png"
            fname = f"{item['broker_no']}{ext}"
            try:
                r = requests.get(item["logo_url"], timeout=15)
                r.raise_for_status()
                (self.logo_dir / fname).write_bytes(r.content)
                logo_name = fname
            except requests.RequestException as e:
                spider.logger.warning("Logo failed for %s: %s", item["broker_no"], e)

        defaults = {
            "broker_code": str(item["broker_no"]),
            "name": item["name"],
            "is_active": True,
        }
        if logo_name:
            defaults["logo"] = logo_name

        Broker.objects.update_or_create(broker_no=item["broker_no"], defaults=defaults)
        return item