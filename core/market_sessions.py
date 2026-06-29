from markets.market_hours import get_ticker_market, is_market_open


def get_ticker_region(ticker):
    return get_ticker_market(ticker)


def is_region_market_open(region, now=None):
    del now  # timezone-aware checks use market local time in markets.market_hours
    return is_market_open(region)


def is_ticker_market_open(ticker, now=None):
    del now
    region = get_ticker_market(ticker)
    return is_market_open(region), region
