from datetime import datetime, time as dtime


def get_ticker_region(ticker):
    ticker = str(ticker).upper()

    if ticker.endswith(".L"):
        return "UK"

    if ticker.endswith((".DE", ".PA", ".AS", ".MI", ".SW", ".MC", ".BR")):
        return "EU"

    return "US"


def is_region_market_open(region, now=None):
    if now is None:
        now = datetime.now()

    if now.weekday() >= 5:
        return False

    current = now.time()

    if region == "EU":
        return dtime(10, 0) <= current <= dtime(18, 30)

    if region == "UK":
        return dtime(10, 0) <= current <= dtime(18, 30)

    if region == "US":
        return dtime(16, 30) <= current <= dtime(23, 0)

    return False


def is_ticker_market_open(ticker, now=None):
    region = get_ticker_region(ticker)
    return is_region_market_open(region, now), region
