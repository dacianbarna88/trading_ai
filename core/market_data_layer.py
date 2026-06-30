"""Unified market data layer — yfinance fetch, cache, retry, health."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import yfinance as yf

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
    if data.empty:
        return data
    if len(data.columns.names) > 1:
        data = data.copy()
        data.columns = data.columns.droplevel(1)
    return data


def _fetch_yf_download(ticker: str) -> tuple[float | None, str | None]:
    last_error: str | None = None
    for attempt, backoff in enumerate(_RETRY_BACKOFF_SECONDS, start=1):
        try:
            data = yf.download(
                ticker,
                period="5d",
                auto_adjust=False,
                progress=False,
            )
            data = _normalize_download(data)
            if not data.empty:
                return float(data["Close"].iloc[-1]), None
            last_error = "yf.download returned empty"
        except Exception as exc:
            last_error = str(exc)
        if attempt < len(_RETRY_BACKOFF_SECONDS):
            time.sleep(backoff)
    return None, last_error


def _fetch_fast_info(ticker: str) -> tuple[float | None, str | None]:
    try:
        info = yf.Ticker(ticker).fast_info
        price = info.get("lastPrice") or info.get("regularMarketPrice")
        if price is not None and float(price) > 0:
            return float(price), None
        return None, "fast_info missing lastPrice"
    except Exception as exc:
        return None, str(exc)


def _fetch_history_1d(ticker: str) -> tuple[float | None, str | None]:
    try:
        hist = yf.Ticker(ticker).history(period="1d")
        if hist is None or hist.empty:
            return None, "history(1d) empty"
        return float(hist["Close"].iloc[-1]), None
    except Exception as exc:
        return None, str(exc)


def _fetch_live_price(ticker: str) -> tuple[float | None, str | None, str | None]:
    price, err = _fetch_yf_download(ticker)
    if price is not None:
        return price, "yfinance_download_5d", None

    price, err2 = _fetch_fast_info(ticker)
    if price is not None:
        return price, "yfinance_fast_info", None

    price, err3 = _fetch_history_1d(ticker)
    if price is not None:
        return price, "yfinance_history_1d", None

    return None, None, err or err2 or err3 or "all fetch paths failed"


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
        cached_price = prior.get("price")
        cached_at = _parse_ts(prior.get("fetched_at"))
        age = _age_seconds(cached_at)
        effective_price = float(cached_price) if cached_price is not None else None
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
        "price": effective_price if fetch_succeeded else prior.get("price", effective_price),
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


def reset_market_data_state(
    cache_path: Path | None = None,
    health_path: Path | None = None,
) -> None:
    """Test helper — clear cache and health files."""
    for path in (cache_path or CACHE_PATH, health_path or HEALTH_PATH):
        if path.is_file():
            path.unlink()
