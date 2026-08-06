from datetime import datetime
from zoneinfo import ZoneInfo

from markets.market_config import MARKETS


def is_market_open(market_name, at: datetime | None = None):
    cfg = MARKETS.get(market_name)

    if not cfg or not cfg.get("enabled", False):
        return False

    now = at
    if now is None:
        now = datetime.now(ZoneInfo(cfg["timezone"]))
    else:
        if now.tzinfo is None:
            now = now.replace(tzinfo=ZoneInfo(cfg["timezone"]))
        else:
            now = now.astimezone(ZoneInfo(cfg["timezone"]))

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


def regular_session_open_close(market_name: str, at: datetime | None = None):
    """
    Return (regular_open, regular_close) as timezone-aware datetimes for the
    exchange-local calendar day of `at` (default: now in exchange TZ).

    Holiday / shortened-session calendars are not in SSOT — open/close come from
    markets/market_config.py only. Shortened sessions still start at configured open.
    """
    cfg = MARKETS.get(market_name)
    if not cfg or not cfg.get("enabled", False):
        return None
    tz = ZoneInfo(cfg["timezone"])
    if at is None:
        local = datetime.now(tz)
    else:
        local = at.replace(tzinfo=tz) if at.tzinfo is None else at.astimezone(tz)
    if local.weekday() >= 5:
        return None
    open_time = local.replace(
        hour=cfg["open_hour"],
        minute=cfg["open_minute"],
        second=0,
        microsecond=0,
    )
    close_time = local.replace(
        hour=cfg["close_hour"],
        minute=cfg["close_minute"],
        second=0,
        microsecond=0,
    )
    return open_time, close_time


def get_ticker_market(ticker):
    ticker = str(ticker).upper().strip()

    if ticker.endswith(".L"):
        return "UK"

    if ticker.endswith((".DE", ".PA", ".AS", ".MI", ".SW", ".MC", ".BR")):
        return "EU"

    if ticker.endswith((".HK", ".T", ".KS", ".SI")):
        return "ASIA"

    return "US"


def ticker_session_context(ticker: str, at: datetime | None = None) -> dict:
    """
    Canonical session context for a ticker at time `at`.

    Keys: market, timezone, enabled, is_open, regular_session_open,
    regular_session_close, minutes_since_open, minutes_to_close.
    """
    market = get_ticker_market(ticker)
    cfg = MARKETS.get(market) or {}
    tz_name = cfg.get("timezone") or "UTC"
    tz = ZoneInfo(tz_name)
    if at is None:
        local = datetime.now(tz)
    else:
        local = at.replace(tzinfo=tz) if at.tzinfo is None else at.astimezone(tz)
    bounds = regular_session_open_close(market, local)
    enabled = bool(cfg.get("enabled", False))
    is_open = bool(enabled and bounds and bounds[0] <= local <= bounds[1])
    minutes_since_open = None
    minutes_to_close = None
    open_iso = None
    close_iso = None
    if bounds:
        open_t, close_t = bounds
        open_iso = open_t.isoformat()
        close_iso = close_t.isoformat()
        minutes_since_open = (local - open_t).total_seconds() / 60.0
        minutes_to_close = (close_t - local).total_seconds() / 60.0
    return {
        "ticker": str(ticker).upper().strip(),
        "market": market,
        "timezone": tz_name,
        "enabled": enabled,
        "is_open": is_open,
        "regular_session_open": open_iso,
        "regular_session_close": close_iso,
        "minutes_since_open": minutes_since_open,
        "minutes_to_close": minutes_to_close,
        "local_time": local.isoformat(),
        # Project has no holiday calendar SSOT.
        "holiday_calendar": None,
        "shortened_session": False,
    }


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


def is_ticker_market_open(ticker, at: datetime | None = None):
    market = get_ticker_market(ticker)
    cfg = MARKETS.get(market)

    if not cfg or not cfg.get("enabled", False):
        return False

    return is_market_open(market, at=at)


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
