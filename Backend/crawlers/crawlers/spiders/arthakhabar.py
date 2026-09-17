
import scrapy
import re
from crawlers.spiders.base_news import BaseNewsSpider
import json


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

   

        headline = response.css(
            "#content > div > header > h1::text"
        ).get()

        if not headline:

            headline = response.css(
                'meta[property="og:title"]::attr(content)'
            ).get()

        if headline:
            headline = headline.strip()

      

        body_parts = response.css(
            "div.entry- p::text"
        ).getall()

        if not body_parts:

            body_parts = response.css(
                "div.entry- ::text"
            ).getall()

        body = " ".join(
            part.strip()
            for part in body_parts
            if part.strip()
        )

      
        published_at = self.extract_published_at(
            response
        )
        print("ARTHAKHABAR RAW PUBLISHED DATE:", repr(published_at))
        self.logger.info(
            "Arthakhabar article | headline=%r | "
            "published_at=%r | body_length=%s | url=%s",
            headline,
            published_at,
            len(body),
            response.url,
        )

        self.logger.info(
           "Arthakhabar body: %s",
         body,
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

   
    def extract_published_at(self, response):
    

        nepali_months = (
            "बैशाख|बैसाख|जेठ|असार|श्रावण|साउन|"
            "भाद्र|भाद्रपद|आश्विन|कार्तिक|मंसिर|पौष|"
            "माघ|फाल्गुण|फाल्गुन|चैत्र"
        )

        # 1. Look for the visible date in the article header
        selectors = [
            "#content > div > header p::text",
            "#content > div > header div p::text",
            "article header p::text",
            "article header div p::text",
        ]

        for selector in selectors:
            texts = response.css(selector).getall()

            for text in texts:
                text = " ".join(text.split())

                if re.search(
                    rf"\d+\s*(?:{nepali_months})\s*\d{{4}}",
                    text,
                ):
                    self.logger.info(
                        "Arthakhabar visible date: %s",
                        text,
                    )
                    return text

        # 2. Search the whole article header
        header_text = " ".join(
            response.css("#content > div > header *::text").getall()
        )

        header_text = " ".join(header_text.split())

        match = re.search(
            rf"\d+\s*(?:{nepali_months})\s*\d{{4}}"
            rf"(?:,\s*[^0-9]+)?"
            rf"(?:\s*\d{{1,2}}:\d{{2}})?",
            header_text,
        )

        if match:
            value = match.group(0).strip()

            self.logger.info(
                "Arthakhabar header date: %s",
                value,
            )

            return value

        # 3. JSON-LD fallback
        for script in response.css(
            'script[type="application/ld+json"]::text'
        ).getall():

            try:
                data = json.loads(script)

                objects = data if isinstance(data, list) else [data]

                for obj in objects:
                    if not isinstance(obj, dict):
                        continue

                    value = (
                        obj.get("datePublished")
                        or obj.get("dateCreated")
                    )

                    if value:
                        return value

            except (json.JSONDecodeError, TypeError):
                continue

        # 4. Meta tag fallback
        value = response.css(
            'meta[property="article:published_time"]::attr(content)'
        ).get()

        if value:
            return value.strip()

        # 5. <time datetime="">
        value = response.css(
            "time::attr(datetime)"
        ).get()

        if value:
            return value.strip()

        # 6. <time> visible text
        value = response.css(
            "time::text"
        ).get()

        if value:
            return " ".join(value.split())

        return None