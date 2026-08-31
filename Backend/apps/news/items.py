import scrapy

class NewsArticleItem(scrapy.Item):
    headline = scrapy.Field()
    body_text = scrapy.Field()
    publish_date = scrapy.Field()
    source_portal = scrapy.Field()
    url = scrapy.Field()
