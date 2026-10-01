# crawlers/spiders/moneymitra_brokers.py
import re
import scrapy

import requests
class MoneymitraBrokersSpider(scrapy.Spider):
    name = "moneymitra_brokers"
    base = "https://moneymitra.com/chirfaar/brokers/"

    custom_settings = {
        "ITEM_PIPELINES": {"crawlers.pipelines.MoneymitraBrokerPipeline": 500},
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 2,
        "ROBOTSTXT_OBEY": True,
    }
    async def start(self):
     yield scrapy.Request(f"{self.base}?page=1", self.parse, meta={"page": 1})
    def start_requests(self):
        yield scrapy.Request(f"{self.base}?page=1", self.parse, meta={"page": 1})

    def parse(self, response):
        page = response.meta["page"]
        found = 0

        for h in response.xpath("//h3[re:test(normalize-space(.), '^\\d+\\s*-\\s*.+')]"):
            text = " ".join(h.xpath(".//text()").getall()).strip()
            m = re.match(r"^(\d+)\s*-\s*(.+)$", text)
            if not m:
                continue
            logo = h.xpath(
                "preceding::img[contains(@src, '/media/broker/logo/')][1]/@src"
            ).get()
            found += 1
            yield {
                "broker_no": int(m.group(1)),
                "name": m.group(2).strip(),
                "logo_url": response.urljoin(logo) if logo else "",
            }

        # keep going until a page returns no brokers
        if found:
            nxt = page + 1
            yield scrapy.Request(
                f"{self.base}?page={nxt}", self.parse, meta={"page": nxt}
            )