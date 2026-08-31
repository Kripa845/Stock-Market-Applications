"""
NepseAlpha news spider.

Listing:  https://nepsealpha.com/all-news?page=home  (also ?cid=<n> per
          category)
Article:  https://nepsealpha.com/<slug>
"""

import scrapy

from crawlers.spiders.base_news import BaseNewsSpider
from crawlers.utils.urls import canonicalize_url


class NepsealphaSpider(BaseNewsSpider):

    name = "nepsealpha"

    allowed_domains = [
        "nepsealpha.com",
        "www.nepsealpha.com",
    ]

    start_urls = [
        "https://nepsealpha.com/all-news?page=home",
    ]

    SOURCE = "NepseAlpha"
    source = "NepseAlpha"

    max_articles = 40

    def __init__(self, max_articles=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.max_articles = int(max_articles) if max_articles else 40

        self.articles_seen = 0
        self.articles_scheduled = 0

        self.news_created = 0
        self.news_duplicate_url = 0
        self.news_duplicate_content = 0
        self.news_failed = 0

    def parse(self, response):

        urls = []
        seen = set()

        for href in response.css("a::attr(href)").getall():

            if not href:
                continue

            absolute = canonicalize_url(
                response.urljoin(href.strip())
            )

            if "nepsealpha.com" not in absolute:
                continue

            # Skip known non-article sections.
            if any(
                part in absolute
                for part in (
                    "all-news",
                    "/announcement",
                    "/login",
                    "/register",
                    "/live-trading",
                    "/floorsheet",
                    "/all-stock",
                    "javascript:",
                )
            ):
                continue

            # Article slugs are single path segments, e.g.
            # nepsealpha.com/unitry-shares-surge-629-percent
            path = absolute.split("nepsealpha.com/", 1)[-1]

            if not path or "/" in path.strip("/"):
                continue

            if absolute in seen:
                continue

            seen.add(absolute)
            urls.append(absolute)

        self.logger.info(
            "NepseAlpha: found %s candidate article links",
            len(urls),
        )

        for url in urls:

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
            response.css("h1::text").get()
            or response.css(
                'meta[property="og:title"]::attr(content)'
            ).get()
        )

        body_selectors = [
            "div.news-details p::text",
            "div.blog-details p::text",
            "article p::text",
            ".post-content p::text",
        ]

        body_parts = []

        for selector in body_selectors:
            parts = response.css(selector).getall()
            if parts:
                body_parts = parts
                break

        if not body_parts:
            body_parts = response.xpath(
                "//article//p//text() | //main//p//text()"
            ).getall()

        body = " ".join(
            part.strip() for part in body_parts if part.strip()
        )

        published_at = (
            response.css(
                'meta[property="article:published_time"]'
                "::attr(content)"
            ).get()
            or response.css("time::attr(datetime)").get()
            or response.css("time::text").get()
        )

        item = self.build_item(
            response=response,
            headline=headline,
            body=body,
            published_at=published_at,
            source=self.SOURCE,
        )

        if item:
            yield item

    def errback_article(self, failure):
        self.logger.error(
            "NepseAlpha article request failed: %s | %s",
            failure.request.url,
            failure.value,
        )

    def closed(self, reason):
        self.logger.info(
            "NepseAlpha crawl completed | reason=%s | seen=%s | "
            "scheduled=%s | created=%s | failed=%s",
            reason,
            self.articles_seen,
            self.articles_scheduled,
            self.news_created,
            self.news_failed,
        )
