

import re

import scrapy
from dateutil import parser as date_parser
from django.utils import timezone

from crawlers.spiders.base_news import BaseNewsSpider
from crawlers.utils.urls import canonicalize_url


class MerolaganiSpider(BaseNewsSpider):

    name = "merolagani"

    allowed_domains = [
        "merolagani.com",
        "www.merolagani.com",
    ]

    start_urls = [
        "https://merolagani.com/NewsList.aspx",
    ]

    SOURCE = "MeroLagani"
    source = "MeroLagani"

    max_articles = 40

    def __init__(self, max_articles=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.max_articles = (
            int(max_articles) if max_articles else 40
        )

        self.articles_seen = 0
        self.articles_scheduled = 0

        # Counters consumed by CrawlRunPipeline / logging.
        self.news_created = 0
        self.news_duplicate_url = 0
        self.news_duplicate_content = 0
        self.news_failed = 0

    def parse(self, response):

        article_urls = []
        seen = set()

        for href in response.css(
            "a[href*='NewsDetail.aspx']::attr(href)"
        ).getall():

            absolute = canonicalize_url(
                response.urljoin(href.strip())
            )

            if "newsdetail.aspx" not in absolute.lower():
                continue

            if absolute in seen:
                continue

            seen.add(absolute)
            article_urls.append(absolute)

        self.logger.info(
            "MeroLagani: found %s article links on listing page",
            len(article_urls),
        )

        for url in article_urls:

            if self.articles_scheduled >= self.max_articles:
                break

            self.articles_seen += 1
            self.articles_scheduled += 1

            yield scrapy.Request(
                url,
                callback=self.parse_article,
                errback=self.errback_article,
                dont_filter=True,
            )

    def parse_article(self, response):

        headline = (
            response.css("h4::text").get()
            or response.css("h1::text").get()
            or response.css(
                'meta[property="og:title"]::attr(content)'
            ).get()
        )

        body_selectors = [
            "#ctl00_ContentPlaceHolder1_divNewsDetail p::text",
            "#ctl00_ContentPlaceHolder1_divNewsDetail::text",
            "div.p-3 p::text",
            "article p::text",
            ".news-detail p::text",
        ]

        body_parts = []

        for selector in body_selectors:
            parts = response.css(selector).getall()
            if parts:
                body_parts = parts
                break

        if not body_parts:
            body_parts = response.xpath(
                "//div[contains(@class,'news') or "
                "contains(@id,'News')]//p//text()"
            ).getall()

        body = " ".join(
            part.strip() for part in body_parts if part.strip()
        )

     
        published_at = self.extract_published_at(response)

        item = self.build_item(
            response=response,
            headline=headline,
            body=body,
            published_at=published_at,
            source=self.SOURCE,
        )

        if item:
            yield item

    DATE_PATTERN = re.compile(
        r"[A-Z][a-z]{2}\s+\d{1,2},\s*\d{4}\s+\d{1,2}:\d{2}\s*[AP]M"
    )

    def extract_published_at(self, response):

        candidates = response.css(
            "span::text, div::text, p::text"
        ).getall()

        for text in candidates:
            match = self.DATE_PATTERN.search(text or "")

            if match:
                try:
                    dt = date_parser.parse(match.group(0))
                except (ValueError, TypeError, OverflowError):
                    continue

                if timezone.is_naive(dt):
                    dt = timezone.make_aware(
                        dt,
                        timezone.get_current_timezone(),
                    )

                return dt

        return None

    def errback_article(self, failure):
        self.logger.error(
            "MeroLagani article request failed: %s | %s",
            failure.request.url,
            failure.value,
        )

    def closed(self, reason):
        self.logger.info(
            "MeroLagani crawl completed | reason=%s | seen=%s | "
            "scheduled=%s | created=%s | duplicate_url=%s | failed=%s",
            reason,
            self.articles_seen,
            self.articles_scheduled,
            self.news_created,
            self.news_duplicate_url,
            self.news_failed,
        )
