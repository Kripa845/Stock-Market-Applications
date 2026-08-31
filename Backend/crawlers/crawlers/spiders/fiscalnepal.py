import scrapy

from crawlers.spiders.base_news import BaseNewsSpider


class FiscalnepalSpider(BaseNewsSpider):

    name = "fiscalnepal"

    allowed_domains = [
        "fiscalnepal.com",
        "www.fiscalnepal.com",
    ]

    start_urls = [
        "https://www.fiscalnepal.com/category/stock/"
    ]

    SOURCE = "Fiscal Nepal"

    def parse(self, response):

        article_urls = response.css(
            "article a::attr(href)"
        ).getall()

        # Fallback for themes where article is not
        # wrapped exactly in <article>.
        if not article_urls:

            article_urls = response.css(
                'a[href*="/20"]::attr(href)'
            ).getall()

        seen = set()

        for url in article_urls:

            absolute_url = response.urljoin(url)

            if absolute_url in seen:
                continue

            seen.add(absolute_url)

            yield scrapy.Request(
                absolute_url,
                callback=self.parse_article,
            )

        # Pagination
        next_page = (
            response.css(
                "a.next.page-numbers::attr(href)"
            ).get()
            or
            response.css(
                "a.next::attr(href)"
            ).get()
        )

        if next_page:

            yield response.follow(
                next_page,
                callback=self.parse,
            )

    def parse_article(self, response):

        headline = (
            response.css("h1::text").get()
            or
            response.css(
                'meta[property="og:title"]::attr(content)'
            ).get()
        )

        body_parts = []

        selectors = [
            "div.content-area p::text",
            "article p::text",
            ".entry-content p::text",
            ".post-content p::text",
        ]

        for selector in selectors:

            parts = response.css(
                selector
            ).getall()

            if parts:
                body_parts = parts
                break

        if not body_parts:

            body_parts = response.xpath(
                "//article//p//text()"
            ).getall()

        body = " ".join(
            part.strip()
            for part in body_parts
            if part.strip()
        )

        published_at = (
            response.css(
                'meta[property="article:published_time"]'
                '::attr(content)'
            ).get()
            or
            response.css(
                "time::attr(datetime)"
            ).get()
            or
            response.css(
                "time::text"
            ).get()
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