from datetime import datetime, time as dtime


def is_market_open():
    now = datetime.now()

    if now.weekday() >= 5:
        return False

    market_open = dtime(16, 30)
    market_close = dtime(23, 0)

    return market_open <= now.time() <= market_close
