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


if __name__ == "__main__":
    for name, is_open in get_market_statuses().items():
        print(name, "OPEN" if is_open else "CLOSED")
