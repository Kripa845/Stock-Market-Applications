import scrapy


class BrokersSpider(scrapy.Spider):
    name = "brokers"
    limit = 100
    api_url = "https://nepseportfoliotracker.app/api/brokers"

    custom_settings = {
        # This pipeline runs for this spider only; it does not replace the
        # project's global pipeline configuration for other spiders.
        "ITEM_PIPELINES": {"crawlers.pipelines.BrokerPipeline": 500},
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 2,
    }

    def start_requests(self):
        yield self._page_request(1)

    def _page_request(self, page):
        return scrapy.Request(
            f"{self.api_url}?page={page}&limit={self.limit}&search=&sortBy=rank&sortOrder=ASC",
            callback=self.parse,
            meta={"page": page},
        )

    def parse(self, response):
        payload = response.json()
        data = payload.get("data") or {}
        brokers = data.get("brokers") or []
        total = int(data.get("total") or 0)
        page = int(data.get("page") or response.meta.get("page", 1))
        if not hasattr(self, "_seen_broker_numbers"):
            self._seen_broker_numbers = set()

        for broker in brokers:
            try:
                broker_no = int(broker.get("member_code"))
            except (TypeError, ValueError):
                continue
            name = str(broker.get("member_name") or "").strip()
            if not name:
                continue
            self._seen_broker_numbers.add(broker_no)
            yield {
                "broker_no": broker_no,
                "name": name,
                "tms_link": str(broker.get("tms_link") or "").strip(),
            }

        if brokers and len(self._seen_broker_numbers) < total:
            yield self._page_request(page + 1)
