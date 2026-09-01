

import scrapy


class NepalipaisaSpider(scrapy.Spider):

    name = "nepalipaisa"

    allowed_domains = ["nepalipaisa.com"]

    start_urls = ["https://nepalipaisa.com/news"]

    def parse(self, response):
        self.logger.warning(
            "nepalipaisa spider is a documented stub: this portal "
            "renders news via client-side JS and requires a headless "
            "browser or its internal JSON API to scrape. Skipping."
        )
        return
        yield  # pragma: no cover - keeps this a generator, unreachable
