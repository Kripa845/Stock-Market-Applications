from datetime import timedelta

import scrapy

from django.utils import timezone

from crawlers.items import NewsItem
from crawlers.utils.text import clean_text
from crawlers.utils.dates import parse_datetime
from crawlers.utils.urls import canonicalize_url


class BaseNewsSpider(scrapy.Spider):

    LOOKBACK_DAYS = 31

    custom_settings = {
        "ROBOTSTXT_OBEY": True,

        "CONCURRENT_REQUESTS": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,

        "DOWNLOAD_DELAY": 2,
        "RANDOMIZE_DOWNLOAD_DELAY": True,

        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 2,
        "AUTOTHROTTLE_MAX_DELAY": 10,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 0.5,

        "RETRY_ENABLED": True,
        "RETRY_TIMES": 3,

        "RETRY_HTTP_CODES": [
            408,
            429,
            500,
            502,
            503,
            504,
            522,
            524,
        ],

        "DOWNLOAD_TIMEOUT": 30,

        "USER_AGENT": (
            "NepalStockMarketResearchCrawler/1.0 "
            "(educational research project)"
        ),
    }

    def normalize_headline(self, value):
        return clean_text(value)

    def normalize_body(self, value):
        return clean_text(value)

    def normalize_date(self, value):
        return parse_datetime(value)

    def is_recent(self, published_at):

        if not published_at:
            return True

        cutoff = (
            timezone.now()
            - timedelta(days=self.LOOKBACK_DAYS)
        )

        return published_at >= cutoff

    def build_item(
        self,
        response,
        headline,
        body,
        published_at,
        source,
    ):

        headline = self.normalize_headline(headline)

        body = self.normalize_body(body)

        published_at = self.normalize_date(
            published_at
        )

        url = canonicalize_url(
            response.url
        )

        if not headline:
            self.logger.warning(
                "Skipping article without headline: %s",
                response.url,
            )
            return None

        if not body:
            self.logger.warning(
                "Skipping article without body: %s",
                response.url,
            )
            return None

        if len(body) < 100:
            self.logger.warning(
                "Skipping very short article: %s",
                response.url,
            )
            return None

        if published_at and not self.is_recent(
            published_at
        ):
            self.logger.info(
                "Skipping old article: %s",
                response.url,
            )
            return None

        return NewsItem(
            item_type="news",

            headline=headline,
            body=body,
            published_at=published_at,

            source=source,
            url=url,

            raw_html=response.text,
            http_status=response.status,
        )