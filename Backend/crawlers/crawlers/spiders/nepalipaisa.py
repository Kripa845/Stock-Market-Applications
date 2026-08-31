"""
NepaliPaisa spider -- INTENTIONALLY NOT IMPLEMENTED.

nepalipaisa.com is a client-side rendered (JS) application: the news
list is populated by an internal JSON API after the page loads rather
than being present in the initial HTML response, so a plain
Scrapy/requests-based crawl of https://nepalipaisa.com/news returns an
empty shell.

Two honest options exist for a real implementation:
  1. Reverse-engineer the site's internal JSON API (browser devtools ->
     Network tab -> XHR) and hit that endpoint directly with scrapy.
  2. Render the page with a headless browser (scrapy-playwright /
     scrapy-splash) before parsing.

Given the assignment's time budget this portal was left out in favor
of four fully-implemented HTML-rendered sources (ShareSansar,
MeroLagani, Bizmandu, NepseAlpha) plus ArthaKhabar and FiscalNepal --
see the README "Data sources used" section for this trade-off.

This spider is kept as a stub / extension point rather than deleted so
option (1) or (2) above can be dropped in later without touching the
rest of the pipeline (items/pipelines are already source-agnostic).
"""

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
