import hashlib
import json
import os
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from twisted.internet.threads import deferToThread

# ----------------------------------------------------------------------
# DJANGO SETUP
# ----------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[2]

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings",
)

import django

django.setup()

from django.db import IntegrityError, transaction
from django.utils import timezone

from itemadapter import ItemAdapter

# ----------------------------------------------------------------------
# MODELS
# ----------------------------------------------------------------------

from apps.crawler_runs.models import CrawlRun
from apps.news.models import NewsArticle, RawArticle
from apps.companies.models import Company
from apps.market_data.models import DailyPrice, FloorsheetTransaction


# ======================================================================
# HELPERS
# ======================================================================

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
    """
    Convert the datetime supplied by the spider into a Django
    timezone-aware datetime.
    """

    if isinstance(value, datetime):
        dt = value

    elif isinstance(value, str):
        value = clean_text(value)

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
                dt = datetime.strptime(value, fmt)
                break
            except ValueError:
                continue

        if dt is None:
            try:
                from dateutil import parser as date_parser

                dt = date_parser.parse(
                    value,
                    fuzzy=True,
                )
            except (ValueError, TypeError, OverflowError):
                return None

    else:
        return None

    if timezone.is_naive(dt):
        dt = timezone.make_aware(
            dt,
            timezone.get_current_timezone(),
        )

    return dt


# ======================================================================
# CRAWL RUN PIPELINE
# ======================================================================

class CrawlRunPipeline:
    """
    Creates one CrawlRun per crawler execution.

    IMPORTANT:
    Scrapy is running with an asyncio reactor. Direct synchronous Django
    ORM calls from pipeline callbacks can raise:

        SynchronousOnlyOperation:
        You cannot call this from an async context

    Therefore every ORM operation is executed in deferToThread().
    """

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
            crawl_run = CrawlRun.objects.create(
                status="running",
                started_at=timezone.now(),
                sources=[source],
            )

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
            crawl_run = CrawlRun.objects.get(
                pk=crawl_run_id,
            )

            crawl_run.status = "completed"
            crawl_run.completed_at = timezone.now()

            # These fields exist in the project's CrawlRun model.
            crawl_run.articles_found = getattr(
                spider,
                "articles_seen",
                0,
            )

            crawl_run.articles_created = getattr(
                spider,
                "news_created",
                0,
            )

            crawl_run.articles_updated = getattr(
                spider,
                "news_duplicate_url",
                0,
            )

            crawl_run.save(
                update_fields=[
                    "status",
                    "completed_at",
                    "articles_found",
                    "articles_created",
                    "articles_updated",
                ],
            )

            spider.logger.info(
                "CrawlRun %s completed | found=%s | created=%s | "
                "duplicate_url=%s | duplicate_content=%s | failed=%s",
                crawl_run.id,
                crawl_run.articles_found,
                crawl_run.articles_created,
                getattr(spider, "news_duplicate_url", 0),
                getattr(spider, "news_duplicate_content", 0),
                getattr(spider, "news_failed", 0),
            )

        except Exception as exc:
            spider.logger.exception(
                "Failed to finalize CrawlRun %s: %s",
                crawl_run_id,
                exc,
            )


# ======================================================================
# NEWS PIPELINE
# ======================================================================

class NewsPipeline:
    """
    Saves:

        RawArticle
             |
             v
        NewsArticle

    Deduplication:
        1. URL
        2. content_hash

    RawArticle.crawl_run is mandatory in the actual project model, so
    the current CrawlRun ID is always attached to RawArticle.
    """

    def open_spider(self, spider):
        self.created_count = 0
        self.duplicate_url_count = 0
        self.duplicate_content_count = 0
        self.failed_count = 0

        spider.news_created = 0
        spider.news_duplicate_url = 0
        spider.news_duplicate_content = 0
        spider.news_failed = 0

        spider.logger.info(
            "News pipeline started for %s",
            getattr(
                spider,
                "source",
                getattr(spider, "SOURCE", spider.name),
            ),
        )

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        if adapter.get("item_type", "news") != "news":
            return item

        headline = clean_text(
            adapter.get("headline")
        )
        body = clean_body(
            adapter.get("body")
        )
        source = clean_text(
            adapter.get("source")
        )
        url = clean_text(
            adapter.get("url")
        )
        published_at = normalize_datetime(
            adapter.get("published_at")
        )
        http_status = adapter.get(
            "http_status",
            200,
        )
        raw_html = adapter.get(
            "raw_html",
            "",
        )

        if not headline:
            spider.logger.warning(
                "Skipping article because headline is empty: %s",
                url,
            )
            return item

        if not body:
            spider.logger.warning(
                "Skipping article because body is empty: %s",
                url,
            )
            return item

        if not source:
            spider.logger.warning(
                "Skipping article because source is empty: %s",
                url,
            )
            return item

        if not url:
            spider.logger.warning(
                "Skipping article because URL is empty",
            )
            return item

        if not published_at:
            spider.logger.warning(
                "Skipping article because published_at is invalid: %s",
                url,
            )
            return item

        crawl_run_id = getattr(
            spider,
            "crawl_run_id",
            None,
        )

        if not crawl_run_id:
            spider.news_failed += 1

            spider.logger.error(
                "Cannot save article because CrawlRun was not created: %s",
                url,
            )

            return item

        content_hash = hashlib.sha256(
            f"{headline}|{body}".encode("utf-8")
        ).hexdigest()

        # Run all Django ORM operations in a normal worker thread.
        return deferToThread(
            self._save_article_sync,
            item,
            spider,
            crawl_run_id,
            headline,
            body,
            published_at,
            source,
            url,
            content_hash,
            raw_html,
            http_status,
        )

    def _save_article_sync(
        self,
        item,
        spider,
        crawl_run_id,
        headline,
        body,
        published_at,
        source,
        url,
        content_hash,
        raw_html,
        http_status,
    ):
        try:
            with transaction.atomic():

                # ------------------------------------------------------
                # URL duplicate
                # ------------------------------------------------------

                existing_article = (
                    NewsArticle.objects
                    .filter(url=url)
                    .first()
                )

                if existing_article:
                    self.duplicate_url_count += 1
                    spider.news_duplicate_url += 1

                    spider.logger.info(
                        "Duplicate article skipped by URL: %s",
                        url,
                    )

                    return item

                # ------------------------------------------------------
                # Content duplicate
                # ------------------------------------------------------

                existing_content = (
                    NewsArticle.objects
                    .filter(content_hash=content_hash)
                    .first()
                )

                if existing_content:
                    self.duplicate_content_count += 1
                    spider.news_duplicate_content += 1

                    spider.logger.info(
                        "Duplicate article skipped by content: %s",
                        url,
                    )

                    return item

                # ------------------------------------------------------
                # RAW ARTICLE
                # ------------------------------------------------------
                #
                # The original pipeline did:
                #
                #   RawArticle.objects.create(
                #       source=...,
                #       url=...,
                #   )
                #
                # But RawArticle.crawl_run is mandatory. This is a
                # second independent bug that would appear after fixing
                # SynchronousOnlyOperation.
                # ------------------------------------------------------

                raw_article = (
                    RawArticle.objects
                    .filter(
                        source=source,
                        url=url,
                    )
                    .first()
                )

                if raw_article is None:

                    raw_article = RawArticle.objects.create(
                        crawl_run_id=crawl_run_id,
                        source=source,
                        url=url,
                        http_status=http_status,
                        raw_html=raw_html or "",
                    )

                else:
                    # Recover a RawArticle left behind by a partially
                    # completed previous crawl.
                    raw_article.crawl_run_id = crawl_run_id
                    raw_article.http_status = http_status
                    raw_article.raw_html = raw_html or ""

                    raw_article.save(
                        update_fields=[
                            "crawl_run",
                            "http_status",
                            "raw_html",
                        ],
                    )

                # ------------------------------------------------------
                # NEWS ARTICLE
                # ------------------------------------------------------

                article = NewsArticle.objects.create(
                    raw_article=raw_article,
                    source=source,
                    url=url,
                    headline=headline,
                    body=body,
                    published_at=published_at,
                    content_hash=content_hash,
                )

                self.created_count += 1
                spider.news_created += 1

                spider.logger.info(
                    "News article saved successfully | id=%s | %s",
                    article.id,
                    headline,
                )

                return item

        except IntegrityError as exc:
            self.failed_count += 1
            spider.news_failed += 1

            spider.logger.exception(
                "Integrity error saving article %s: %s",
                url,
                exc,
            )

            return item

        except Exception as exc:
            self.failed_count += 1
            spider.news_failed += 1

            spider.logger.exception(
                "Failed to save article %s: %s",
                url,
                exc,
            )

            return item

    def close_spider(self, spider):
        spider.logger.info(
            "News pipeline finished | created=%s | duplicate_url=%s | "
            "duplicate_content=%s | failed=%s",
            self.created_count,
            self.duplicate_url_count,
            self.duplicate_content_count,
            self.failed_count,
        )


# ======================================================================
# TRADING DATA PIPELINE
# ======================================================================

class TradingDataPipeline:
    """
    Persists DailyPrice and writes trading_data.json.

    The original pipeline also performed synchronous Django ORM calls.
    That would produce the same async-context exception when this item
    pipeline is used by trading_data.
    """

    def open_spider(self, spider):
        self.file = open(
            "trading_data.json",
            "w",
            encoding="utf-8",
        )

        self.file.write("[\n")
        self.first_item = True

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

        try:
            _, created = (
                DailyPrice.objects.update_or_create(
                    company=company,
                    date=trading_date,
                    defaults={
                        "open": open_price,
                        "high": high_price,
                        "low": low_price,
                        "close": close_price,
                        "volume": volume,
                        "turnover": turnover,
                    },
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
    Persists FloorsheetTransaction rows (feeds the buyer/seller
    behavior analysis in Section 3) AND keeps writing floorsheet.json
    for quick manual inspection.

    Same async-context caveat as the other DB-touching pipelines: all
    ORM calls run inside deferToThread().
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

        spider.floorsheet_saved = 0
        spider.floorsheet_failed = 0

    def process_item(self, item, spider):
        required_keys = {
            "buyer_broker",
            "seller_broker",
            "quantity",
            "rate",
        }

        if not any(key in item for key in required_keys):
            return item

        # Keep the raw JSON dump regardless of DB outcome.
        if self.first_item:
            self.first_item = False
        else:
            self.file.write(",\n")

        self.file.write(
            json.dumps(dict(item), ensure_ascii=False, default=str)
        )

        return deferToThread(
            self._save_transaction_sync,
            item,
            spider,
        )

    def _save_transaction_sync(self, item, spider):
        symbol = clean_text(item.get("company")).upper()

        if not symbol:
            self.skipped_count += 1
            spider.logger.error(
                "Floorsheet row missing company symbol.",
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

        raw_date = item.get("date")

        if not raw_date:
            self.skipped_count += 1
            spider.logger.error(
                "Floorsheet row missing date for %s.",
                symbol,
            )
            return item

        trading_date = normalize_datetime(raw_date)

        if trading_date is None:
            self.skipped_count += 1
            spider.logger.error(
                "Floorsheet row has unparseable date '%s' for %s.",
                raw_date,
                symbol,
            )
            return item

        trading_date = trading_date.date()

        buyer_broker = clean_text(item.get("buyer_broker"))
        seller_broker = clean_text(item.get("seller_broker"))
        transaction_id = clean_text(item.get("transaction_id"))

        try:
            quantity = int(
                str(item.get("quantity") or "0").replace(",", "")
            )

            rate = Decimal(
                str(item.get("rate") or "0").replace(",", "")
            )

            amount_raw = item.get("amount")

            amount = (
                Decimal(str(amount_raw).replace(",", ""))
                if amount_raw not in (None, "")
                else (rate * quantity)
            )

        except (InvalidOperation, ValueError):
            self.failed_count += 1
            spider.floorsheet_failed += 1

            spider.logger.error(
                "Floorsheet row has invalid numeric data for %s on %s.",
                symbol,
                trading_date,
            )
            return item

        if quantity < 0 or rate < 0 or amount < 0:
            self.failed_count += 1
            spider.floorsheet_failed += 1

            spider.logger.error(
                "Floorsheet row has negative values for %s on %s.",
                symbol,
                trading_date,
            )
            return item

        try:
            _, created = FloorsheetTransaction.objects.update_or_create(
                company=company,
                date=trading_date,
                transaction_id=transaction_id or f"{buyer_broker}-{seller_broker}-{quantity}-{rate}",
                defaults={
                    "buyer_broker": buyer_broker,
                    "seller_broker": seller_broker,
                    "quantity": quantity,
                    "rate": rate,
                    "amount": amount,
                },
            )

        except IntegrityError as exc:
            self.failed_count += 1
            spider.floorsheet_failed += 1

            spider.logger.error(
                "Database error saving floorsheet row for %s on %s: %s",
                symbol,
                trading_date,
                exc,
            )
            return item

        self.saved_count += 1
        spider.floorsheet_saved += 1

        spider.logger.debug(
            "%s | floorsheet | %s | %s -> %s | qty=%s rate=%s",
            "CREATED" if created else "UPDATED",
            symbol,
            trading_date,
            buyer_broker,
            quantity,
            rate,
        )

        return item

    def close_spider(self, spider):
        if getattr(self, "file", None):
            self.file.write("\n]\n")
            self.file.close()

        spider.logger.info(
            "Floorsheet pipeline finished | saved=%s | skipped=%s | "
            "failed=%s",
            self.saved_count,
            self.skipped_count,
            self.failed_count,
        )
