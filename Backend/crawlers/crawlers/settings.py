BOT_NAME = "crawlers"

SPIDER_MODULES = ["crawlers.spiders"]
NEWSPIDER_MODULE = "crawlers.spiders"

ROBOTSTXT_OBEY = True

CONCURRENT_REQUESTS_PER_DOMAIN = 1

DOWNLOAD_DELAY = 2

RANDOMIZE_DOWNLOAD_DELAY = True
AUTOTHROTTLE_ENABLED = True

AUTOTHROTTLE_START_DELAY = 2

AUTOTHROTTLE_MAX_DELAY = 15

AUTOTHROTTLE_TARGET_CONCURRENCY = 0.5
USER_AGENT = (
    "NepalStockMarketResearchCrawler/1.0 "
    "(research project)"
)

ITEM_PIPELINES = {
    "crawlers.pipelines.CrawlRunPipeline": 100,
    "crawlers.pipelines.NewsPipeline": 300,
    "crawlers.pipelines.TradingDataPipeline": 400,
    "crawlers.pipelines.FloorsheetPipeline":500,
}

FEED_EXPORT_ENCODING = "utf-8"
RETRY_ENABLED = True

RETRY_TIMES = 3

RETRY_HTTP_CODES = [
    408,
    429,
    500,
    502,
    503,
    504,
    522,
    524,
]


DOWNLOAD_TIMEOUT = 30
LOG_LEVEL = "INFO"
COOKIES_ENABLED = True
# settings.py