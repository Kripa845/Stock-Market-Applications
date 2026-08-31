import scrapy


class NewsItem(scrapy.Item):
    item_type = scrapy.Field()

    headline = scrapy.Field()
    body = scrapy.Field()
    published_at = scrapy.Field()
    source = scrapy.Field()
    url = scrapy.Field()

    raw_html = scrapy.Field()
    http_status = scrapy.Field()


class DailyTradingDataItem(scrapy.Item):
    item_type = scrapy.Field()

    company = scrapy.Field()
    date = scrapy.Field()

    open = scrapy.Field()
    high = scrapy.Field()
    low = scrapy.Field()
    close = scrapy.Field()

    volume = scrapy.Field()
    turnover = scrapy.Field()

    source = scrapy.Field()


class FloorsheetItem(scrapy.Item):
    item_type = scrapy.Field()

    company = scrapy.Field()
    date = scrapy.Field()

    transaction_id = scrapy.Field()
    buyer_broker = scrapy.Field()
    seller_broker = scrapy.Field()

    quantity = scrapy.Field()
    rate = scrapy.Field()
    amount = scrapy.Field()

    source = scrapy.Field()