"""Unified market data layer — yfinance fetch, cache, retry, health."""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import yfinance as yf


def _valid_price(price: Any) -> float | None:
    """Accept only finite, strictly positive prices. NaN/inf/<=0 are failures."""
    try:
        if price is None:
            return None
        value = float(price)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or value <= 0:
        return None
    return value

CACHE_PATH = Path("runtime_outputs/market_data_cache.json")
HEALTH_PATH = Path("runtime_outputs/market_data_health.json")

RISK_CACHE_MAX_AGE = 45
DISPLAY_CACHE_MAX_AGE = 300
SIGNAL_CACHE_MAX_AGE = 120

STATUS_OK = "DATA_OK"
STATUS_STALE = "DATA_STALE"
STATUS_FAILING = "DATA_FAILING"
STATUS_CRITICAL = "DATA_CRITICAL"

_RETRY_BACKOFF_SECONDS = (1, 2)


@dataclass
class PriceResult:
    ticker: str
    price: float | None
    fetched_at: datetime | None
    source: str | None
    age_seconds: float | None
    status: str
    consecutive_failures: int
    error: str | None = None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _age_seconds(fetched_at: datetime | None) -> float | None:
    if fetched_at is None:
        return None
    return max(0.0, (_utc_now() - fetched_at).total_seconds())


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _normalize_download(data: pd.DataFrame) -> pd.DataFrame:
    """Legacy flat-column helper. Prefer extract_close_series for price reads."""
    if data is None or data.empty:
        return data if data is not None else pd.DataFrame()
    if isinstance(data.columns, pd.MultiIndex) and data.columns.nlevels > 1:
        data = data.copy()
        # Prefer dropping ticker level when level-0 holds OHLCV names.
        level0 = {str(x) for x in data.columns.get_level_values(0)}
        if "Close" in level0 or "close" in {x.lower() for x in level0}:
            data.columns = data.columns.droplevel(1)
        else:
            data.columns = data.columns.droplevel(0)
    return data


def extract_close_series(data: pd.DataFrame, ticker: str | None = None) -> pd.Series:
    """
    Extract a 1-D Close series from flat or MultiIndex OHLCV frames.

    Supports yfinance layouts:
      - flat: columns include Close
      - (Price, Ticker): level0=OHLCV, level1=symbol
      - (Ticker, Price): level0=symbol, level1=OHLCV
    """
    if data is None or getattr(data, "empty", True):
        return pd.Series(dtype=float)

    ticker_u = str(ticker).upper().strip() if ticker else None
    cols = data.columns

    def _as_series(frame_or_series: pd.DataFrame | pd.Series) -> pd.Series:
        if isinstance(frame_or_series, pd.Series):
            return pd.to_numeric(frame_or_series, errors="coerce")
        if frame_or_series.shape[1] == 1:
            return pd.to_numeric(frame_or_series.iloc[:, 0], errors="coerce")
        if ticker_u:
            for col in frame_or_series.columns:
                if str(col).upper() == ticker_u:
                    return pd.to_numeric(frame_or_series[col], errors="coerce")
            # suffix-preserving match
            for col in frame_or_series.columns:
                if str(col).upper().startswith(ticker_u):
                    return pd.to_numeric(frame_or_series[col], errors="coerce")
        return pd.to_numeric(frame_or_series.iloc[:, 0], errors="coerce")

    if isinstance(cols, pd.MultiIndex) and cols.nlevels > 1:
        level0 = [str(x) for x in cols.get_level_values(0)]
        level1 = [str(x) for x in cols.get_level_values(1)]
        level0_l = {x.lower() for x in level0}
        level1_l = {x.lower() for x in level1}
        try:
            if "close" in level0_l:
                close = data.xs("Close", axis=1, level=0, drop_level=True)
                if isinstance(close, pd.DataFrame) and "Close" not in close.columns:
                    # xs may keep ticker columns only
                    return _as_series(close)
                if isinstance(close, pd.DataFrame) and "Close" in close.columns:
                    return _as_series(close["Close"])
                return _as_series(close)
            if "close" in level1_l:
                close = data.xs("Close", axis=1, level=1, drop_level=True)
                return _as_series(close)
        except (KeyError, TypeError, ValueError):
            pass
        # Fall through to flattened attempt
        flat = _normalize_download(data.copy())
        if "Close" in flat.columns:
            return _as_series(flat["Close"])
        return pd.Series(dtype=float)

    if "Close" in data.columns:
        return _as_series(data["Close"])
    for col in data.columns:
        if str(col).lower() == "close":
            return _as_series(data[col])
    return pd.Series(dtype=float)


def last_valid_close(data: pd.DataFrame, ticker: str | None = None) -> float | None:
    """Last finite, strictly positive Close — skips trailing NaN rows."""
    series = extract_close_series(data, ticker=ticker).dropna()
    if series.empty:
        return None
    positive = series[series > 0]
    if positive.empty:
        return None
    return _valid_price(positive.iloc[-1])


def _fetch_yf_download(ticker: str) -> tuple[float | None, str | None]:
    last_error: str | None = None
    ticker_key = str(ticker).strip()
    for attempt, backoff in enumerate(_RETRY_BACKOFF_SECONDS, start=1):
        try:
            data = yf.download(
                ticker_key,
                period="5d",
                auto_adjust=False,
                progress=False,
            )
            if data is None or data.empty:
                last_error = "yf.download returned empty"
            else:
                price = last_valid_close(data, ticker=ticker_key)
                if price is not None:
                    return price, None
                last_error = "yf.download returned non-finite Close"
        except Exception as exc:
            last_error = str(exc)
        if attempt < len(_RETRY_BACKOFF_SECONDS):
            time.sleep(backoff)
    return None, last_error


def _fetch_fast_info(ticker: str) -> tuple[float | None, str | None]:
    try:
        info = yf.Ticker(str(ticker).strip()).fast_info
        raw = None
        if hasattr(info, "get"):
            raw = info.get("lastPrice") or info.get("regularMarketPrice") or info.get("last_price")
        if raw is None:
            raw = getattr(info, "last_price", None) or getattr(info, "regular_market_price", None)
        price = _valid_price(raw)
        if price is not None:
            return price, None
        return None, "fast_info missing lastPrice"
    except Exception as exc:
        return None, str(exc)


def _fetch_history_close(ticker: str, *, period: str) -> tuple[float | None, str | None]:
    try:
        hist = yf.Ticker(str(ticker).strip()).history(period=period)
        if hist is None or hist.empty:
            return None, f"history({period}) empty"
        price = last_valid_close(hist, ticker=ticker)
        if price is not None:
            return price, None
        return None, f"history({period}) non-finite Close"
    except Exception as exc:
        return None, str(exc)


def _fetch_history_1d(ticker: str) -> tuple[float | None, str | None]:
    """Backward-compatible name — tries 1d then 5d for closed-session previous close."""
    price, err = _fetch_history_close(ticker, period="1d")
    if price is not None:
        return price, None
    price2, err2 = _fetch_history_close(ticker, period="5d")
    if price2 is not None:
        return price2, None
    return None, err or err2


def _fetch_live_price(ticker: str) -> tuple[float | None, str | None, str | None]:
    # Preserve canonical suffix (.L / .DE / .PA) — never strip for provider requests.
    ticker_key = str(ticker).strip()
    price, err = _fetch_yf_download(ticker_key)
    price = _valid_price(price)
    if price is not None:
        return price, "yfinance_download_5d", None

    price, err2 = _fetch_fast_info(ticker_key)
    price = _valid_price(price)
    if price is not None:
        return price, "yfinance_fast_info", None

    price, err3 = _fetch_history_close(ticker_key, period="1d")
    price = _valid_price(price)
    if price is not None:
        return price, "yfinance_history_1d", None

    price, err4 = _fetch_history_close(ticker_key, period="5d")
    price = _valid_price(price)
    if price is not None:
        return price, "yfinance_history_5d_previous_close", None

    return None, None, err or err2 or err3 or err4 or "all fetch paths failed"


def _compute_status(
    *,
    age_seconds: float | None,
    consecutive_failures: int,
    fetch_succeeded: bool,
) -> str:
    age = age_seconds if age_seconds is not None else float("inf")

    if consecutive_failures > 5 or (not fetch_succeeded and age > 120):
        return STATUS_CRITICAL
    if consecutive_failures >= 3 or age > 90:
        return STATUS_FAILING
    if fetch_succeeded and age <= 15:
        return STATUS_OK
    if age <= 90 or consecutive_failures in (1, 2):
        return STATUS_STALE
    return STATUS_FAILING


def _cache_entry(
    ticker: str,
    cache: dict[str, Any],
) -> dict[str, Any]:
    entry = cache.get(ticker.upper(), {})
    return entry if isinstance(entry, dict) else {}


def _write_health(cache: dict[str, Any], path: Path = HEALTH_PATH) -> None:
    health: dict[str, Any] = {"generated_at": _utc_now().isoformat(), "tickers": {}}
    for ticker, entry in cache.items():
        if not isinstance(entry, dict):
            continue
        fetched_at = _parse_ts(entry.get("fetched_at"))
        age = _age_seconds(fetched_at)
        health["tickers"][ticker] = {
            "price": entry.get("price"),
            "fetched_at": entry.get("fetched_at"),
            "source": entry.get("source"),
            "age_seconds": round(age, 2) if age is not None else None,
            "status": entry.get("status"),
            "consecutive_failures": entry.get("consecutive_failures", 0),
            "last_error": entry.get("last_error"),
        }
    _save_json(path, health)


def get_market_price(
    ticker: str,
    purpose: str = "risk",
    *,
    cache_path: Path | None = None,
    health_path: Path | None = None,
    fetch_fn: Callable[[str], tuple[float | None, str | None, str | None]] | None = None,
    now_fn: Callable[[], datetime] | None = None,
) -> PriceResult:
    """Return a price quote with cache, retry, fallback, and health metadata."""
    ticker_key = str(ticker).upper()
    purpose = (purpose or "risk").lower()
    cache_file = cache_path or CACHE_PATH
    health_file = health_path or HEALTH_PATH
    fetch = fetch_fn or _fetch_live_price

    cache = _load_json(cache_file)
    prior = _cache_entry(ticker_key, cache)
    prior_failures = int(prior.get("consecutive_failures") or 0)

    live_price, source, error = fetch(ticker_key)
    live_price = _valid_price(live_price)
    if live_price is None and error is None:
        error = "non_finite_or_missing_price"
    fetched_at = _utc_now()
    fetch_succeeded = live_price is not None

    if fetch_succeeded:
        consecutive_failures = 0
        effective_price = live_price
        effective_source = source
        effective_fetched_at = fetched_at
        age = 0.0
        status = STATUS_OK
    else:
        consecutive_failures = prior_failures + 1
        cached_price = _valid_price(prior.get("price"))
        cached_at = _parse_ts(prior.get("fetched_at"))
        age = _age_seconds(cached_at)
        effective_price = cached_price
        effective_source = prior.get("source")
        effective_fetched_at = cached_at
        status = _compute_status(
            age_seconds=age,
            consecutive_failures=consecutive_failures,
            fetch_succeeded=False,
        )

    result_price = effective_price
    result_status = status if fetch_succeeded else _compute_status(
        age_seconds=age,
        consecutive_failures=consecutive_failures,
        fetch_succeeded=False,
    )

    if purpose == "risk":
        if fetch_succeeded:
            result_price = live_price
            result_status = STATUS_OK
        elif effective_price is not None and age is not None and age <= RISK_CACHE_MAX_AGE:
            result_price = effective_price
            result_status = _compute_status(
                age_seconds=age,
                consecutive_failures=consecutive_failures,
                fetch_succeeded=False,
            )
        else:
            result_price = None
            if consecutive_failures > 5 or (age is not None and age > 120):
                result_status = STATUS_CRITICAL
            elif consecutive_failures >= 3 or (age is not None and age > 90):
                result_status = STATUS_FAILING
            else:
                result_status = STATUS_STALE

    elif purpose == "display":
        if effective_price is None:
            result_price = None
        elif fetch_succeeded or (age is not None and age <= DISPLAY_CACHE_MAX_AGE):
            result_price = effective_price
            result_status = STATUS_OK if fetch_succeeded and (age or 0) <= 15 else result_status
        else:
            result_price = None
            result_status = STATUS_FAILING if consecutive_failures >= 3 else STATUS_STALE

    elif purpose == "signal":
        if fetch_succeeded:
            result_price = live_price
            result_status = STATUS_OK
        elif effective_price is not None and age is not None and age <= SIGNAL_CACHE_MAX_AGE:
            result_price = effective_price
            result_status = STATUS_STALE
        else:
            result_price = None

    cache[ticker_key] = {
        "price": effective_price if fetch_succeeded else _valid_price(prior.get("price")),
        "fetched_at": (
            effective_fetched_at.isoformat()
            if fetch_succeeded and effective_fetched_at
            else prior.get("fetched_at")
        ),
        "source": effective_source if fetch_succeeded else prior.get("source"),
        "consecutive_failures": consecutive_failures,
        "status": result_status,
        "last_error": error,
        "last_purpose": purpose,
        "updated_at": _utc_now().isoformat(),
    }
    if fetch_succeeded:
        cache[ticker_key]["price"] = live_price
        cache[ticker_key]["fetched_at"] = fetched_at.isoformat()
        cache[ticker_key]["source"] = source
        cache[ticker_key]["status"] = STATUS_OK
    # Never persist non-finite / non-positive cache prices.
    if _valid_price(cache[ticker_key].get("price")) is None:
        cache[ticker_key]["price"] = None

    _save_json(cache_file, cache)
    _write_health(cache, health_file)

    return PriceResult(
        ticker=ticker_key,
        price=result_price,
        fetched_at=effective_fetched_at if fetch_succeeded else _parse_ts(prior.get("fetched_at")),
        source=effective_source if fetch_succeeded else prior.get("source"),
        age_seconds=0.0 if fetch_succeeded else age,
        status=result_status,
        consecutive_failures=consecutive_failures,
        error=error,
    )


def diagnose_mark(ticker: str, *, purpose: str = "risk") -> dict[str, Any]:
    """Deterministic regional mark diagnostic for one ticker (read-only + cache write via layer)."""
    from markets.market_hours import get_ticker_market, ticker_session_context
    from markets.market_config import MARKETS

    ticker_key = str(ticker).strip()
    ticker_u = ticker_key.upper()
    market = get_ticker_market(ticker_u)
    cfg = MARKETS.get(market) or {}
    session = ticker_session_context(ticker_u)
    now_utc = _utc_now()
    local_tz = cfg.get("timezone") or "UTC"
    try:
        from zoneinfo import ZoneInfo

        now_local = now_utc.astimezone(ZoneInfo(local_tz))
    except Exception:
        now_local = now_utc

    attempts: list[dict[str, Any]] = []
    for name, fn in (
        ("yf.download_5d", lambda: _fetch_yf_download(ticker_key)),
        ("fast_info", lambda: _fetch_fast_info(ticker_key)),
        ("history_1d", lambda: _fetch_history_close(ticker_key, period="1d")),
        ("history_5d", lambda: _fetch_history_close(ticker_key, period="5d")),
    ):
        price, err = fn()
        valid = _valid_price(price)
        attempts.append(
            {
                "source": name,
                "value": valid,
                "raw": price,
                "validity": valid is not None,
                "rejection_reason": None if valid is not None else (err or "invalid"),
            }
        )

    result = get_market_price(ticker_key, purpose=purpose)
    cache = _load_json(CACHE_PATH)
    entry = _cache_entry(ticker_u, cache)
    is_open = bool(session.get("is_open"))
    if result.price is not None and result.source and "previous_close" in str(result.source):
        freshness = "PREVIOUS_CLOSE"
        session_label = "MARKET_CLOSED_VALID_PREVIOUS_CLOSE" if not is_open else "DELAYED_BUT_ACCEPTABLE_MARK"
    elif result.price is not None and result.status == STATUS_OK:
        freshness = "LIVE/FRESH MARK" if is_open else "DELAYED_BUT_ACCEPTABLE_MARK"
        session_label = "MARKET_OPEN_VALID_LIVE_MARK" if is_open else "MARKET_CLOSED_VALID_PREVIOUS_CLOSE"
    elif result.price is not None:
        freshness = "STALE CACHE"
        session_label = "MARKET_OPEN_NO_LIVE_MARK" if is_open else "MARKET_CLOSED_VALID_PREVIOUS_CLOSE"
    else:
        freshness = "NO VALID MARK"
        session_label = "MARKET_OPEN_NO_LIVE_MARK" if is_open else "MARKET_CLOSED_NO_VALID_MARK"

    currency = "GBp" if ticker_u.endswith(".L") else ("EUR" if market == "EU" else "USD")
    exchange = {
        "UK": "London Stock Exchange",
        "EU": "Xetra/Euronext (suffix-mapped)",
        "US": "US",
        "ASIA": "ASIA",
    }.get(market, market)

    return {
        "ticker": ticker_u,
        "provider_symbol": ticker_key,
        "market": market,
        "exchange": exchange,
        "currency": currency,
        "exchange_timezone": local_tz,
        "market_open": is_open,
        "market_session_status": session_label,
        "request_timestamp_utc": now_utc.isoformat(),
        "request_timestamp_local_exchange": now_local.isoformat(),
        "attempts": attempts,
        "cache_value": _valid_price(entry.get("price")),
        "cache_age_seconds": _age_seconds(_parse_ts(entry.get("fetched_at"))),
        "cache_key": ticker_u,
        "selected_source": result.source,
        "selected_mark": result.price,
        "mark_timestamp": result.fetched_at.isoformat() if result.fetched_at else None,
        "mark_age_seconds": result.age_seconds,
        "mark_freshness_status": freshness,
        "validity": result.price is not None and _valid_price(result.price) is not None,
        "failure_reason": result.error,
        "layer_status": result.status,
        "session_context": {
            "regular_session_open": str(session.get("regular_session_open")),
            "regular_session_close": str(session.get("regular_session_close")),
            "minutes_since_open": session.get("minutes_since_open"),
        },
    }


def regional_mark_health_summary(
    tickers: list[str] | None = None,
) -> dict[str, Any]:
    """Compact morning-audit summary for regional mark availability (cache/signals first)."""
    import csv

    targets = [t.upper() for t in (tickers or ["AZN.L", "BP.L", "SAP.DE"])]
    cache = _load_json(CACHE_PATH)
    signal_prices: dict[str, float | None] = {}
    signals_path = Path("live_signals.csv")
    if signals_path.is_file():
        try:
            with signals_path.open(encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    t = str(row.get("Ticker") or row.get("ticker") or "").upper()
                    if t in targets:
                        signal_prices[t] = _valid_price(row.get("Price") or row.get("price"))
        except OSError:
            pass

    details: dict[str, Any] = {}
    valid = 0
    missing = 0
    stale = 0
    for t in targets:
        entry = _cache_entry(t, cache)
        cache_px = _valid_price(entry.get("price"))
        sig_px = signal_prices.get(t)
        status = str(entry.get("status") or "")
        mark = sig_px if sig_px is not None else cache_px
        if mark is not None:
            valid += 1
            label = "VALID"
            if status in {STATUS_STALE, STATUS_FAILING} and sig_px is None:
                stale += 1
                label = "STALE"
        else:
            missing += 1
            label = "MISSING"
        details[t] = {
            "status": label,
            "signal_price": sig_px,
            "cache_price": cache_px,
            "cache_status": entry.get("status"),
            "source": entry.get("source"),
        }
    return {
        "AZN.L": details.get("AZN.L"),
        "BP.L": details.get("BP.L"),
        "SAP.DE": details.get("SAP.DE"),
        "valid_regional_marks": valid,
        "missing_regional_marks": missing,
        "stale_regional_marks": stale,
        "details": details,
    }


def reset_market_data_state(
    cache_path: Path | None = None,
    health_path: Path | None = None,
) -> None:
    """Test helper — clear cache and health files."""
    for path in (cache_path or CACHE_PATH, health_path or HEALTH_PATH):
        if path.is_file():
            path.unlink()


def _print_diagnosis(payload: dict[str, Any]) -> None:
    print(f"ticker: {payload.get('ticker')}")
    print(f"provider symbol: {payload.get('provider_symbol')}")
    print(f"market: {payload.get('market')}")
    print(f"exchange: {payload.get('exchange')}")
    print(f"currency: {payload.get('currency')}")
    print(f"exchange timezone: {payload.get('exchange_timezone')}")
    print(f"market open/closed: {'OPEN' if payload.get('market_open') else 'CLOSED'}")
    print(f"session status: {payload.get('market_session_status')}")
    print(f"request timestamp UTC: {payload.get('request_timestamp_utc')}")
    print(f"request timestamp local exchange: {payload.get('request_timestamp_local_exchange')}")
    for row in payload.get("attempts") or []:
        print(
            f"  attempt {row.get('source')}: value={row.get('value')} "
            f"valid={row.get('validity')} reject={row.get('rejection_reason')}"
        )
    print(f"cache value: {payload.get('cache_value')}")
    print(f"cache age: {payload.get('cache_age_seconds')}")
    print(f"cache key: {payload.get('cache_key')}")
    print(f"selected source: {payload.get('selected_source')}")
    print(f"selected mark: {payload.get('selected_mark')}")
    print(f"mark timestamp: {payload.get('mark_timestamp')}")
    print(f"mark age seconds: {payload.get('mark_age_seconds')}")
    print(f"freshness: {payload.get('mark_freshness_status')}")
    print(f"validity: {payload.get('validity')}")
    print(f"failure reason: {payload.get('failure_reason')}")


if __name__ == "__main__":
    import sys

    args = [a for a in sys.argv[1:] if a.strip()]
    if not args:
        print("usage: python3 -m core.market_data_layer TICKER [TICKER...]", file=sys.stderr)
        raise SystemExit(2)
    for sym in args:
        _print_diagnosis(diagnose_mark(sym))
        print("---")
