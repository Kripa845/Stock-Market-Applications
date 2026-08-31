# from scrapy.spiders import SitemapSpider

# from crawlers.spiders.base_news import BaseNewsSpider


# class ArthakhabarSpider(
#     BaseNewsSpider,
#     SitemapSpider,
# ):

#     name = "arthakhabar"

#     allowed_domains = [
#         "arthakhabar.com",
#         "www.arthakhabar.com",
#     ]

#     sitemap_urls = [
#         "https://arthakhabar.com/wp-sitemap.xml"
#     ]

#     SOURCE = "Arthakhabar"

#     def sitemap_filter(self, entries):

#         ignored_parts = [
#             "/wp-admin/",
#             "/wp-login",
#             "/category/",
#             "/tag/",
#             "/author/",
#             "/page/",
#             "/feed/",
#             "/wp-json/",
#         ]

#         for entry in entries:

#             url = entry["loc"]

#             if any(
#                 part in url.lower()
#                 for part in ignored_parts
#             ):
#                 continue

#             yield entry

#     def parse(self, response):

#         headline = (
#             response.css("h1::text").get()
#             or
#             response.css(
#                 'meta[property="og:title"]::attr(content)'
#             ).get()
#         )

#         body_parts = []

#         selectors = [
#             "article .entry-content p::text",
#             "article .post-content p::text",
#             "article .article-content p::text",
#             ".entry-content p::text",
#             ".post-content p::text",
#             ".article-content p::text",
#             ".news-content p::text",
#             "article p::text",
#         ]

#         for selector in selectors:

#             parts = response.css(
#                 selector
#             ).getall()

#             if parts:
#                 body_parts = parts
#                 break

#         if not body_parts:

#             body_parts = response.xpath(
#                 "//article//p//text()"
#             ).getall()

#         body = " ".join(
#             part.strip()
#             for part in body_parts
#             if part.strip()
#         )

#         published_at = (
#             response.css(
#                 'meta[property="article:published_time"]'
#                 '::attr(content)'
#             ).get()
#             or
#             response.css(
#                 "time::attr(datetime)"
#             ).get()
#             or
#             response.css(
#                 "time::text"
#             ).get()
#             or
#             response.css(
#                 ".entry-date::text"
#             ).get()
#             or
#             response.css(
#                 ".published::text"
#             ).get()
#         )

#         item = self.build_item(
#             response=response,
#             headline=headline,
#             body=body,
#             published_at=published_at,
#             source=self.SOURCE,
#         )

#         if item:
#             yield item


import scrapy

from crawlers.spiders.base_news import BaseNewsSpider


class ArthakhabarSpider(BaseNewsSpider, scrapy.Spider):

    name = "arthakhabar"

    allowed_domains = [
        "arthakhabar.com",
        "www.arthakhabar.com",
    ]

    start_urls = [
        "https://arthakhabar.com/category/stock-market/"
    ]

    SOURCE = "Arthakhabar"

    def parse(self, response):

        self.logger.info(
            "Arthakhabar listing page: %s",
            response.url,
        )

        article_urls = response.css(
            '[id^="post-"] > a::attr(href)'
        ).getall()

        self.logger.info(
            "Arthakhabar found %s article URLs",
            len(article_urls),
        )

        # Fallback
        if not article_urls:

            article_urls = response.css(
                "article a::attr(href)"
            ).getall()

        seen = set()

        for url in article_urls:

            url = response.urljoin(url)

            if url in seen:
                continue

            seen.add(url)

            # Skip category/non-article pages
            if "/category/" in url:
                continue

            if "/tag/" in url:
                continue

            if "/author/" in url:
                continue

            if "/feed/" in url:
                continue

            if url.rstrip("/") == "https://arthakhabar.com":
                continue

            yield scrapy.Request(
                url=url,
                callback=self.parse_article,
            )

    def parse_article(self, response):

        # --------------------------------------------------
        # HEADLINE
        # --------------------------------------------------

        headline = response.css(
            "#content > div > header > h1::text"
        ).get()

        if not headline:

            headline = response.css(
                'meta[property="og:title"]::attr(content)'
            ).get()

        if headline:
            headline = headline.strip()

        # --------------------------------------------------
        # BODY
        # --------------------------------------------------

        body_parts = response.css(
            "div.entry-content p::text"
        ).getall()

        if not body_parts:

            body_parts = response.css(
                "div.entry-content ::text"
            ).getall()

        body = " ".join(
            part.strip()
            for part in body_parts
            if part.strip()
        )

        # --------------------------------------------------
        # PUBLISHED DATE
        # --------------------------------------------------

        published_at = self.extract_published_at(
            response
        )

        self.logger.info(
            "Arthakhabar article | headline=%r | "
            "published_at=%r | body_length=%s | url=%s",
            headline,
            published_at,
            len(body),
            response.url,
        )

        # --------------------------------------------------
        # BUILD ITEM
        # --------------------------------------------------

        item = self.build_item(
            response=response,
            headline=headline,
            body=body,
            published_at=published_at,
            source=self.SOURCE,
        )

        if item:
            yield item

    # def extract_published_at(self, response):

    #     # --------------------------------------------------
    #     # 1. Actual Arthakhabar header date
    #     # --------------------------------------------------

    #     published_at = response.css(
    #         "#content > div > header > div > div > div "
    #         "> p:nth-child(2)::text"
    #     ).get()

    #     if published_at:
    #         return published_at.strip()

    #     # --------------------------------------------------
    #     # 2. <time datetime="">
    #     # --------------------------------------------------

    #     published_at = response.css(
    #         "time::attr(datetime)"
    #     ).get()

    #     if published_at:
    #         return published_at.strip()

    #     # --------------------------------------------------
    #     # 3. <time> text
    #     # --------------------------------------------------

    #     published_at = response.css(
    #         "time::text"
    #     ).get()

    #     if published_at:
    #         return published_at.strip()

    #     # --------------------------------------------------
    #     # 4. WordPress date classes
    #     # --------------------------------------------------

    #     for selector in [
    #         ".entry-date::text",
    #         ".published::text",
    #         ".post-date::text",
    #         ".article-date::text",
    #         ".date::text",
    #     ]:

    #         published_at = response.css(
    #             selector
    #         ).get()

    #         if published_at:
    #             return published_at.strip()

    #     # --------------------------------------------------
    #     # 5. JSON-LD
    #     # --------------------------------------------------

    #     json_ld_blocks = response.css(
    #         'script[type="application/ld+json"]::text'
    #     ).getall()

    #     for block in json_ld_blocks:

    #         try:
    #             import json

    #             data = json.loads(block)

    #         except (
    #             json.JSONDecodeError,
    #             TypeError,
    #         ):
    #             continue

    #         if isinstance(data, list):
    #             objects = data

    #         elif (
    #             isinstance(data, dict)
    #             and "@graph" in data
    #         ):
    #             objects = data["@graph"]

    #         else:
    #             objects = [data]

    #         for obj in objects:

    #             if not isinstance(obj, dict):
    #                 continue

    #             published_at = (
    #                 obj.get("datePublished")
    #                 or obj.get("dateCreated")
    #             )

    #             if published_at:
    #                 return str(
    #                     published_at
    #                 ).strip()

    #     return None
    def extract_published_at(self, response):

    # --------------------------------------------------
    # 1. JSON-LD
    # --------------------------------------------------

        json_ld_blocks = response.css(
            'script[type="application/ld+json"]::text'
        ).getall()

        for block in json_ld_blocks:

            try:
                data = json.loads(block)

            except (json.JSONDecodeError, TypeError):
                continue

            if isinstance(data, list):
                objects = data

            elif isinstance(data, dict) and "@graph" in data:
                objects = data["@graph"]

            else:
                objects = [data]

            for obj in objects:

                if not isinstance(obj, dict):
                    continue

                published_at = (
                    obj.get("datePublished")
                    or obj.get("dateCreated")
                )

                if published_at:
                    return str(published_at).strip()

        # --------------------------------------------------
        # 2. OpenGraph
        # --------------------------------------------------

        published_at = response.css(
            'meta[property="article:published_time"]::attr(content)'
        ).get()

        if published_at:
            return published_at.strip()

        # --------------------------------------------------
        # 3. <time datetime="">
        # --------------------------------------------------

        published_at = response.css(
            "time::attr(datetime)"
        ).get()

        if published_at:
            return published_at.strip()

        # --------------------------------------------------
        # 4. <time> visible text
        # --------------------------------------------------

        published_at = response.css(
            "time::text"
        ).get()

        if published_at:
            return published_at.strip()

        # --------------------------------------------------
        # 5. Arthakhabar article header
        #
        # Based on:
        # #content > div > header > div > div > div > p:nth-child(2)
        # --------------------------------------------------

        selectors = [

            "#content > div > header > div > div > div > p:nth-child(2)::text",

            "#content > div > header p:nth-child(2)::text",

            "#content > div > header p::text",

            "#content > div > header div p::text",

            "article header p::text",

            "article header div p::text",

        ]

        for selector in selectors:

            values = response.css(selector).getall()

            for value in values:

                value = value.strip()

                if not value:
                    continue

                # Only accept text that looks like a date.
                if any(
                    month in value
                    for month in [
                        "बैशाख",
                        "जेठ",
                        "असार",
                        "श्रावण",
                        "श्रावण",
                        "भाद्र",
                        "आश्विन",
                        "कार्तिक",
                        "मंसिर",
                        "पौष",
                        "माघ",
                        "फाल्गुण",
                        "चैत्र",
                    ]
                ):
                    return value

                # Gregorian date fallback
                if any(
                    char.isdigit()
                    for char in value
                ) and (
                    "-" in value
                    or "/" in value
                    or ":" in value
                ):
                    return value

        # --------------------------------------------------
        # 6. Search all header text
        # --------------------------------------------------

        header_text = response.css(
            "#content > div > header ::text"
        ).getall()

        for text in header_text:

            text = text.strip()

            if not text:
                continue

            if any(
                month in text
                for month in [
                    "बैशाख",
                    "जेठ",
                    "असार",
                    "श्रावण",
                    "भाद्र",
                    "आश्विन",
                    "कार्तिक",
                    "मंसिर",
                    "पौष",
                    "माघ",
                    "फाल्गुण",
                    "चैत्र",
                ]
            ):
                return text

        return None