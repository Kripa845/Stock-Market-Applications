

import scrapy

from crawlers.spiders.base_news import BaseNewsSpider
from crawlers.utils.urls import canonicalize_url


class BizmanduSpider(BaseNewsSpider):

    name = "bizmandu"

    allowed_domains = [
        "bizmandu.com",
        "www.bizmandu.com",
    ]

    start_urls = [
        "https://bizmandu.com/content/category/market.html",
    ]

    SOURCE = "Bizmandu"
    source = "Bizmandu"

    max_pages = 5
    max_articles = 40

    def __init__(
        self,
        max_pages=None,
        max_articles=None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.max_pages = int(max_pages) if max_pages else 5
        self.max_articles = int(max_articles) if max_articles else 40

        self.pages_crawled = 0
        self.articles_seen = 0
        self.articles_scheduled = 0
        self.seen_article_urls = set()

        self.news_created = 0
        self.news_duplicate_url = 0
        self.news_duplicate_content = 0
        self.news_failed = 0

    def parse(self, response):

        self.pages_crawled += 1

        article_urls = self.extract_article_urls(response)

        self.logger.info(
            "Bizmandu page %s/%s: found %s article links",
            self.pages_crawled,
            self.max_pages,
            len(article_urls),
        )

        for url in article_urls:

            if self.articles_scheduled >= self.max_articles:
                break

            if url in self.seen_article_urls:
                continue

            self.seen_article_urls.add(url)

            self.articles_seen += 1
            self.articles_scheduled += 1

            self.logger.info(
                "Scheduling Bizmandu article: %s",
                url,
            )

            yield scrapy.Request(
                url,
                callback=self.parse_article,
                errback=self.errback_article,
                dont_filter=True,
            )

        if (
            self.pages_crawled < self.max_pages
            and self.articles_scheduled < self.max_articles
        ):

            next_page = self.extract_next_page(response)

            if next_page:

                self.logger.info(
                    "Next Bizmandu page: %s",
                    next_page,
                )

                yield scrapy.Request(
                    next_page,
                    callback=self.parse,
                    errback=self.errback_page,
                )
    # rest of your existing code...
    def extract_article_urls(self, response):

        urls = []
        seen = set()

        selectors = [
            "a[href*='/content/details/']::attr(href)",
            ".news-list a::attr(href)",
            "article a::attr(href)",
            "h2 a::attr(href), h3 a::attr(href)",
        ]

        for selector in selectors:

            for href in response.css(selector).getall():

                if not href:
                    continue

                absolute = canonicalize_url(
                    response.urljoin(href.strip())
                )

                if "bizmandu.com" not in absolute:
                    continue

                if "/category/" in absolute:
                    continue

                if absolute in seen:
                    continue

                seen.add(absolute)
                urls.append(absolute)

            if urls:
                break

        return urls
   

        all_links = response.css("a::attr(href)").getall()

        self.logger.info(
            "Bizmandu total links found: %s",
            len(all_links),
        )

        for href in all_links[:50]:
            self.logger.info("LINK: %s", href)

        urls = []
        seen = set()

        for href in all_links:

            if not href:
                continue

            absolute = canonicalize_url(
                response.urljoin(href.strip())
            )

            if "bizmandu.com" not in absolute:
                continue

            if "/category/" in absolute:
                continue

            if absolute in seen:
                continue

            seen.add(absolute)
            urls.append(absolute)

        return urls
    def extract_next_page(self, response):

        selectors = [
            "a.next::attr(href)",
            "a[rel='next']::attr(href)",
            ".pagination a:contains('Next')::attr(href)",
        ]

        for selector in selectors:
            href = response.css(selector).get()
            if href:
                return canonicalize_url(response.urljoin(href.strip()))

        return None

  
    def parse_article(self, response):

        headline = (
            response.css("#title::text").get()
            or response.css("h1::text").get()
            or response.css(
                'meta[property="og:title"]::attr(content)'
            ).get()
        )

        body_parts = response.css(
            "div.biz-article-content div.news-text.mb-0 *::text"
        ).getall()

        if not body_parts:
            body_parts = response.css(
                "div.biz-article-content div.news-text.mb-0::text"
            ).getall()

        body = " ".join(
            part.strip()
            for part in body_parts
            if part.strip()
        )

        published_at = (
            response.css(
                'meta[property="article:published_time"]::attr(content)'
            ).get()
            or response.css("time::attr(datetime)").get()
            or response.css("time::text").get()
            or response.css(".date::text").get()
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

    def errback_page(self, failure):
        self.logger.error(
            "Bizmandu listing request failed: %s | %s",
            failure.request.url,
            failure.value,
        )

    def errback_article(self, failure):
        self.logger.error(
            "Bizmandu article request failed: %s | %s",
            failure.request.url,
            failure.value,
        )

    def closed(self, reason):
        self.logger.info(
            "Bizmandu crawl completed | reason=%s | pages=%s/%s | "
            "seen=%s | scheduled=%s | created=%s | failed=%s",
            reason,
            self.pages_crawled,
            self.max_pages,
            self.articles_seen,
            self.articles_scheduled,
            self.news_created,
            self.news_failed,
        )
