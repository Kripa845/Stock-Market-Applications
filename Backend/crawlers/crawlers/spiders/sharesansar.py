
import re
from datetime import timedelta

import scrapy
from dateutil import parser as date_parser
from django.utils import timezone

from crawlers.items import NewsItem
from crawlers.utils.urls import canonicalize_url


class SharesansarSpider(scrapy.Spider):
    """
    ShareSansar news crawler.

    ShareSansar structure:
      - listing: /category/latest
      - article: /newsdetail/<slug>
      - article title: h1
      - publication metadata: h5
      - article body: #newsdetail-content
    """

    name = "sharesansar"

    allowed_domains = [
        "sharesansar.com",
        "www.sharesansar.com",
    ]

    start_urls = [
        "https://www.sharesansar.com/category/latest",
    ]

    source = "ShareSansar"
    SOURCE = "ShareSansar"

    max_pages = 5
    max_articles = 50
    max_article_age_days = 31

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

        "DOWNLOAD_TIMEOUT": 30,

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

        "DEFAULT_REQUEST_HEADERS": {
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
    }

    def __init__(
        self,
        max_pages=None,
        max_articles=None,
        max_article_age_days=None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.max_pages = self.parse_positive_int(max_pages, 5)
        self.max_articles = self.parse_positive_int(max_articles, 50)
        self.max_article_age_days = self.parse_positive_int(
            max_article_age_days,
            31,
        )

        self.pages_requested = 0
        self.pages_crawled = 0

        self.articles_seen = 0
        self.articles_scheduled = 0
        self.articles_scraped = 0

        self.seen_article_urls = set()
        self.seen_listing_urls = set()

        self.cutoff_datetime = (
            timezone.now()
            - timedelta(days=self.max_article_age_days)
        )

        # Counters consumed by CrawlRunPipeline.
        self.news_created = 0
        self.news_duplicate_url = 0
        self.news_duplicate_content = 0
        self.news_failed = 0

    # ==============================================================
    # HELPERS
    # ==============================================================

    @staticmethod
    def parse_positive_int(value, default):
        if value is None:
            return default

        try:
            value = int(value)
        except (TypeError, ValueError):
            return default

        return value if value > 0 else default

    @staticmethod
    def normalize_whitespace(value):
        return re.sub(
            r"\s+",
            " ",
            str(value or ""),
        ).strip()

    # ==============================================================
    # START
    # ==============================================================

    def start_requests(self):
        for url in self.start_urls:

            if self.pages_requested >= self.max_pages:
                break

            canonical_url = canonicalize_url(url)

            self.pages_requested += 1
            self.seen_listing_urls.add(canonical_url)

            self.logger.info(
                "Starting ShareSansar listing: %s",
                canonical_url,
            )

            yield scrapy.Request(
                url=canonical_url,
                callback=self.parse,
                errback=self.errback_page,
                dont_filter=True,
            )

    # ==============================================================
    # LISTING
    # ==============================================================

    def parse(self, response):
        yield from self.parse_news_page(response)

    def parse_news_page(self, response):

        self.pages_crawled += 1

        self.logger.info(
            "ShareSansar listing page %s/%s: %s",
            self.pages_crawled,
            self.max_pages,
            response.url,
        )

        if response.status != 200:
            self.logger.error(
                "Unexpected ShareSansar listing status=%s url=%s",
                response.status,
                response.url,
            )
            return

        article_urls = self.extract_article_urls(response)

        self.logger.info(
            "Found %s article URLs",
            len(article_urls),
        )

        for article_url in article_urls:

            if self.articles_scheduled >= self.max_articles:
                break

            if article_url in self.seen_article_urls:
                continue

            self.seen_article_urls.add(article_url)

            self.articles_seen += 1
            self.articles_scheduled += 1

            self.logger.info(
                "Scheduling article %s/%s: %s",
                self.articles_scheduled,
                self.max_articles,
                article_url,
            )

            yield scrapy.Request(
                url=article_url,
                callback=self.parse_article,
                errback=self.errback_article,
                dont_filter=True,
            )

        # Only paginate if we still need articles.
        if (
            self.pages_requested < self.max_pages
            and self.articles_scheduled < self.max_articles
        ):
            next_page = self.extract_next_page(response)

            if (
                next_page
                and next_page not in self.seen_listing_urls
            ):
                self.seen_listing_urls.add(next_page)
                self.pages_requested += 1

                self.logger.info(
                    "Scheduling next ShareSansar page %s/%s: %s",
                    self.pages_requested,
                    self.max_pages,
                    next_page,
                )

                yield scrapy.Request(
                    url=next_page,
                    callback=self.parse,
                    errback=self.errback_page,
                )

    # ==============================================================
    # ARTICLE URL EXTRACTION
    # ==============================================================

    def extract_article_urls(self, response):
        """
        Extract ONLY /newsdetail/ links.

        IMPORTANT:
        Do not use guessed .news-list/.news-item selectors here.

        The selector you supplied from ShareSansar points to the
        actual article-card link, so we use it first.

        We also keep a controlled fallback that only accepts
        /newsdetail/ URLs.
        """

        urls = []
        seen = set()

        # ----------------------------------------------------------
        # PRIMARY SELECTOR
        # ----------------------------------------------------------
        #
        # This is the selector you supplied:
        #
        # body > div:nth-child(5) > div > section.main-content >
        # div:nth-child(3) > div > div:nth-child(3) > div > div >
        # div > div > div:nth-child(1) > div > div:nth-child(6) >
        # div > a
        #
        # It identifies an actual article link in the Latest page.
        #
        primary_selector = (
            "body > div:nth-child(5) > div > "
            "section.main-content > div:nth-child(3) > "
            "div > div:nth-child(3) > div > div > div > "
            "div > div:nth-child(1) > div > div:nth-child(6) > "
            "div > a::attr(href)"
        )

        hrefs = response.css(primary_selector).getall()

        self.logger.info(
            "Primary article selector found %s links",
            len(hrefs),
        )

        for href in hrefs:
            self._add_article_url(
                response,
                href,
                urls,
                seen,
            )

        # ----------------------------------------------------------
        # CONTROLLED FALLBACK
        # ----------------------------------------------------------
        #
        # If the exact nth-child selector changes, don't completely
        # break the crawler. Find newsdetail links, but only inside
        # the main content area.
        #

        if not urls:

            self.logger.warning(
                "Primary article selector returned 0 links. "
                "Trying controlled main-content fallback."
            )

            fallback_selectors = [
                "section.main-content a[href*='/newsdetail/']::attr(href)",
                "main a[href*='/newsdetail/']::attr(href)",
            ]

            for selector in fallback_selectors:

                for href in response.css(selector).getall():

                    self._add_article_url(
                        response,
                        href,
                        urls,
                        seen,
                    )

                if urls:
                    break

        self.logger.info(
            "ShareSansar extracted %s article URLs",
            len(urls),
        )

        for index, url in enumerate(
            urls[:20],
            start=1,
        ):
            self.logger.info(
                "Candidate %s: %s",
                index,
                url,
            )

        return urls

    def _add_article_url(
        self,
        response,
        href,
        urls,
        seen,
    ):
        if not href:
            return

        absolute = canonicalize_url(
            response.urljoin(href.strip())
        )

        # Must be an actual news article.
        if "/newsdetail/" not in absolute:
            return

        # Reject known non-news/static pages.
        blocked_slugs = (
            "/beginners-guide",
        )

        if any(
            slug in absolute
            for slug in blocked_slugs
        ):
            return

        if absolute in seen:
            return

        seen.add(absolute)
        urls.append(absolute)

    # ==============================================================
    # PAGINATION
    # ==============================================================

    def extract_next_page(self, response):

        selectors = [
            "a[rel='next']::attr(href)",
            ".pagination a[rel='next']::attr(href)",
            ".pagination .next a::attr(href)",
            "li.next a::attr(href)",
            "a.next::attr(href)",
        ]

        for selector in selectors:

            href = response.css(selector).get()

            if href:
                return canonicalize_url(
                    response.urljoin(
                        href.strip()
                    )
                )

        return None

    # ==============================================================
    # ARTICLE
    # ==============================================================

    def parse_article(self, response):

        headline = self.extract_headline(response)
        published_at = self.extract_published_at(response)
        body = self.extract_body(response)

        self.logger.debug(
            "ARTICLE DEBUG | url=%s | headline=%r | date=%r | body_length=%s",
            response.url,
            headline,
            published_at,
            len(body or ""),
        )

        # ----------------------------------------------------------
        # HEADLINE
        # ----------------------------------------------------------

        if not headline:
            self.logger.warning(
                "Skipping article: headline not found: %s",
                response.url,
            )
            return

        # ----------------------------------------------------------
        # DATE
        # ----------------------------------------------------------

        if not published_at:
            self.logger.warning(
                "Skipping article: publication date not found: %s",
                response.url,
            )
            return

        # ----------------------------------------------------------
        # BODY
        # ----------------------------------------------------------

        if not body or len(body) < 100:
            self.logger.warning(
                "Skipping article: body too short (%s chars): %s",
                len(body or ""),
                response.url,
            )
            return

        # ----------------------------------------------------------
        # AGE FILTER
        # ----------------------------------------------------------

        if published_at < self.cutoff_datetime:

            self.logger.info(
                "Skipping old article | published=%s | cutoff=%s | %s",
                published_at.isoformat(),
                self.cutoff_datetime.isoformat(),
                response.url,
            )

            return

        if self.articles_scraped >= self.max_articles:
            return

        self.articles_scraped += 1

        self.logger.info(
            "SCRAPED %s/%s | %s | %s",
            self.articles_scraped,
            self.max_articles,
            published_at.isoformat(),
            headline,
        )

        yield NewsItem(
            item_type="news",
            headline=headline,
            body=body,
            published_at=published_at,
            source=self.source,
            url=canonicalize_url(response.url),
            http_status=response.status,
            raw_html=response.text,
        )

    # ==============================================================
    # HEADLINE
    # ==============================================================

    def extract_headline(self, response):
        """
        Use the exact h1 structure you supplied.

        We intentionally do NOT combine every h1/meta/title value.
        """

        selector = (
            "section.main-content h1"
        )

        value = response.css(
            selector
        ).xpath(
            "string(.)"
        ).get()

        headline = self.normalize_whitespace(value)

        if headline:
            return headline

        # Exact structural fallback based on your selector.
        fallback_selector = (
            "div.col-lg-9.col-md-9.col-sm-8.col-xs-12 "
            "div.col-md-12 > h1"
        )

        value = response.css(
            fallback_selector
        ).xpath(
            "string(.)"
        ).get()

        return self.normalize_whitespace(value)

    # ==============================================================
    # PUBLICATION DATE
    # ==============================================================

    def extract_published_at(self, response):
        """
        Use the h5 publication metadata from the article header.

        Your selector shows:

        div.margin-bottom-10 > div.col-lg-8 > h5
        """

        selectors = [
            (
                "section.main-content "
                "div.col-md-12 "
                "div.margin-bottom-10 "
                "div.col-lg-8 > h5"
            ),
            (
                "div.col-md-12 "
                "div.margin-bottom-10 "
                "div.col-lg-8 > h5"
            ),
            "h5",
        ]

        for selector in selectors:

            values = response.css(
                selector
            ).xpath(
                "string(.)"
            ).getall()

            for value in values:

                parsed = self.parse_date(value)

                if parsed:
                    self.logger.debug(
                        "Publication date found using %s: %r",
                        selector,
                        value,
                    )
                    return parsed

        return None

    @staticmethod
    def parse_date(value):

        if not value:
            return None

        value = " ".join(
            str(value).split()
        ).strip()

        if not value:
            return None

        try:

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

        if timezone.is_naive(dt):

            dt = timezone.make_aware(
                dt,
                timezone.get_current_timezone(),
            )

        return dt

    # ==============================================================
    # BODY
    # ==============================================================

  
    # ==============================================================
    # BODY
    # ==============================================================

    def extract_body(self, response):
        """
        Extract article body from ShareSansar.

        The actual article paragraph is inside:

        #newsdetail-content
        > div.qMYqUG_convSearchResultHighlightRoot
        > div
        > section
        > ...
        > p

        We use the stable #newsdetail-content container first rather
        than relying on the full nth-child selector, because nth-child
        paths can change when ShareSansar adds/removes HTML elements.
        """

        # ----------------------------------------------------------
        # PRIMARY: actual article content container
        # ----------------------------------------------------------

        node = response.css(
            "#newsdetail-content"
        )

        if node:
            parts = node.xpath(
                ".//p//text()[normalize-space()]"
            ).getall()

            body = self.clean_body(parts)

            if len(body) >= 100:
                self.logger.debug(
                    "Body extracted from #newsdetail-content | chars=%s",
                    len(body),
                )
                return body

        # ----------------------------------------------------------
        # SECONDARY: exact structure you provided
        # ----------------------------------------------------------

        exact_selector = (
            "#newsdetail-content > "
            "div.qMYqUG_convSearchResultHighlightRoot > "
            "div > section > div > div > div > div > div > div > "
            "p"
        )

        parts = response.css(
            exact_selector
        ).xpath(
            ".//text()[normalize-space()]"
        ).getall()

        body = self.clean_body(parts)

        if len(body) >= 100:
            self.logger.debug(
                "Body extracted using ShareSansar article selector | chars=%s",
                len(body),
            )
            return body

        # ----------------------------------------------------------
        # FALLBACK
        # ----------------------------------------------------------

        for selector in [
            "article p",
            "section.main-content p",
        ]:
            parts = response.css(
                selector
            ).xpath(
                ".//text()[normalize-space()]"
            ).getall()

            body = self.clean_body(parts)

            if len(body) >= 100:
                self.logger.debug(
                    "Body extracted using fallback %s | chars=%s",
                    selector,
                    len(body),
                )
                return body

        self.logger.warning(
            "Could not extract article body: %s",
            response.url,
        )

        return ""


    def clean_body(self, values):

        parts = []
        seen = set()

        for value in values:

            text = self.normalize_whitespace(value)

            if not text:
                continue

            # Ignore tiny UI/navigation fragments.
            if len(text) < 20:
                continue

            key = text.casefold()

            if key in seen:
                continue

            seen.add(key)
            parts.append(text)

        return "\n\n".join(parts).strip()

    # ==============================================================
    # ERRBACKS
    # ==============================================================

    def errback_page(self, failure):

        request = failure.request

        self.logger.error(
            "ShareSansar listing request failed: %s | %s",
            request.url,
            failure.value,
        )

    def errback_article(self, failure):

        request = failure.request

        self.logger.error(
            "ShareSansar article request failed: %s | %s",
            request.url,
            failure.value,
        )

    # ==============================================================
    # CLOSE
    # ==============================================================

    def closed(self, reason):

        self.logger.info(
            "ShareSansar crawl completed | reason=%s | "
            "pages=%s/%s | articles_seen=%s | "
            "articles_scheduled=%s | articles_scraped=%s | "
            "created=%s | duplicate_url=%s | "
            "duplicate_content=%s | failed=%s",
            reason,
            self.pages_crawled,
            self.max_pages,
            self.articles_seen,
            self.articles_scheduled,
            self.articles_scraped,
            self.news_created,
            self.news_duplicate_url,
            self.news_duplicate_content,
            self.news_failed,
        )

