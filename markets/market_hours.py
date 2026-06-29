from datetime import datetime
from zoneinfo import ZoneInfo

from markets.market_config import MARKETS


def is_market_open(market_name):
    cfg = MARKETS.get(market_name)

    if not cfg or not cfg.get("enabled", False):
        return False

    now = datetime.now(ZoneInfo(cfg["timezone"]))

    if now.weekday() >= 5:
        return False

    open_time = now.replace(
        hour=cfg["open_hour"],
        minute=cfg["open_minute"],
        second=0,
        microsecond=0,
    )

    close_time = now.replace(
        hour=cfg["close_hour"],
        minute=cfg["close_minute"],
        second=0,
        microsecond=0,
    )

    return open_time <= now <= close_time


def get_market_statuses():
    return {
        name: is_market_open(name)
        for name in MARKETS.keys()
    }


def any_market_open():
    return any(
        is_market_open(name)
        for name in MARKETS
        if MARKETS[name].get("enabled", False)
    )


def get_open_markets():
    return [name for name in MARKETS if is_market_open(name)]


def get_ticker_market(ticker):
    ticker = str(ticker).upper().strip()

    if ticker.endswith(".L"):
        return "UK"

    if ticker.endswith((".DE", ".PA", ".AS", ".MI", ".SW", ".MC", ".BR")):
        return "EU"

    if ticker.endswith((".HK", ".T", ".KS", ".SI")):
        return "ASIA"

    return "US"


def is_ticker_market_open(ticker):
    market = get_ticker_market(ticker)
    cfg = MARKETS.get(market)

    if not cfg or not cfg.get("enabled", False):
        return False

    return is_market_open(market)


def log_market_session_summary(logger=None):
    statuses = get_market_statuses()
    open_markets = get_open_markets()
    closed_markets = [name for name, is_open in statuses.items() if not is_open]

    line = (
        f"Market sessions OPEN=[{','.join(open_markets) if open_markets else 'NONE'}] "
        f"CLOSED=[{','.join(closed_markets) if closed_markets else 'NONE'}]"
    )

    if logger:
        logger(line)
    else:
        print(line)

    return statuses


if __name__ == "__main__":
    log_market_session_summary()
    for name, is_open in get_market_statuses().items():
        print(name, "OPEN" if is_open else "CLOSED")
