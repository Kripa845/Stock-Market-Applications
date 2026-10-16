import scrapy


class NewsItem(scrapy.Item):
    item_type = scrapy.Field()

    headline = scrapy.Field()
    body = scrapy.Field()
    published_at = scrapy.Field()
    source = scrapy.Field()
    url = scrapy.Field()
    image_url = scrapy.Field()

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

    # ShareSansar "% change" (per_change), optional.
    source_change_pct = scrapy.Field()

    source = scrapy.Field()


class FloorsheetItem(scrapy.Item):
    item_type = scrapy.Field()

    company = scrapy.Field()
    date = scrapy.Field()
    trade_time = scrapy.Field()

    transaction_id = scrapy.Field()
    buyer_broker = scrapy.Field()
    seller_broker = scrapy.Field()

    quantity = scrapy.Field()
    rate = scrapy.Field()
    amount = scrapy.Field()

    source = scrapy.Field()


class IndexDailyItem(scrapy.Item):
    # MarketWidePipeline dispatches on item_type ("index_daily") and matches index_name.
    item_type = scrapy.Field()
    item_code = scrapy.Field()
    index_name = scrapy.Field()

    
    date = scrapy.Field()

    open = scrapy.Field()
    high = scrapy.Field()
    low = scrapy.Field()
    close = scrapy.Field()

    source = scrapy.Field()
    
    
class MarketStockDailyItem(scrapy.Item):
    # MarketWidePipeline dispatches on item_type ("market_stock_daily").
    item_type = scrapy.Field()
    symbol = scrapy.Field()

    date = scrapy.Field()
    sector_raw = scrapy.Field()
    close=scrapy.Field()
    prev_close=scrapy.Field()
    turnover = scrapy.Field()
    volume = scrapy.Field()
    transactions = scrapy.Field()

    source = scrapy.Field()
    
    


class DividendItem(scrapy.Item):
    # DividendPipeline dispatches on item_type ("dividend"); upserted on (symbol, fiscal_year).
    item_type = scrapy.Field()
    source_id = scrapy.Field()
    symbol = scrapy.Field()
    company_name = scrapy.Field()
    fiscal_year = scrapy.Field()

    bonus_pct = scrapy.Field()
    cash_pct = scrapy.Field()

    announcement_date = scrapy.Field()
    book_closure_date = scrapy.Field()
    distribution_date = scrapy.Field()
    bonus_listing_date = scrapy.Field()

    source = scrapy.Field()


class CompanyFaceValueItem(scrapy.Item):
    # item_type "company_face_value": paid-up value per share.
    item_type = scrapy.Field()
    symbol = scrapy.Field()
    face_value = scrapy.Field()

    source = scrapy.Field()


class CompanyEpsItem(scrapy.Item):
    # item_type "company_eps": EPS for one fiscal year and quarter.
    item_type = scrapy.Field()
    symbol = scrapy.Field()
    fiscal_year = scrapy.Field()
    quarter = scrapy.Field()
    eps = scrapy.Field()

    source = scrapy.Field()
