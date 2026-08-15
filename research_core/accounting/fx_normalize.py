#!/usr/bin/env python3
"""
Historical FX normalization for economic integrity (READ_ONLY consumers).

Uses yfinance FX pairs EURUSD=X / GBPUSD=X. No static FX for historical lots.
GBp (pence) → GBP (/100) before USD conversion.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable

import pandas as pd

FX_PAIR = {
    "EUR": "EURUSD=X",
    "GBP": "GBPUSD=X",
    "USD": None,
}

_FX_CACHE: dict[str, pd.Series] = {}


def instrument_currency(ticker: str) -> str:
    t = str(ticker).upper()
    if t.endswith(".L"):
        return "GBp"
    if t.endswith((".PA", ".DE", ".AS", ".MI", ".MC", ".BR")):
        return "EUR"
    return "USD"


def to_major_currency_amount(amount_local: float, currency: str) -> tuple[float, str]:
    """Convert GBp pence → GBP pounds; EUR/USD unchanged."""
    ccy = str(currency)
    if ccy == "GBp":
        return float(amount_local) / 100.0, "GBP"
    return float(amount_local), ccy


def _flatten_close(raw: pd.DataFrame) -> pd.Series:
    if raw is None or raw.empty:
        return pd.Series(dtype=float)
    close = raw["Close"] if "Close" in raw.columns else raw.iloc[:, 0]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    s = close.astype(float).copy()
    s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s


def _default_fx_fetcher(pair: str) -> pd.DataFrame:
    import yfinance as yf

    return yf.download(pair, period="10y", interval="1d", auto_adjust=True, progress=False)


def load_fx_series(
    quote: str,
    *,
    fetcher: Callable[[str], pd.DataFrame] | None = None,
) -> pd.Series:
    """Return USD per 1 unit of quote currency (EUR or GBP)."""
    quote = str(quote).upper()
    if quote == "USD":
        return pd.Series(dtype=float)
    pair = FX_PAIR.get(quote)
    if not pair:
        return pd.Series(dtype=float)
    if pair in _FX_CACHE:
        return _FX_CACHE[pair]
    fn = fetcher or _default_fx_fetcher
    series = _flatten_close(fn(pair))
    _FX_CACHE[pair] = series
    return series


def fx_rate_on(
    quote: str,
    when: Any,
    *,
    fetcher: Callable[[str], pd.DataFrame] | None = None,
) -> dict[str, Any]:
    """
    Historical FX: USD per 1 major unit of quote (EUR/GBP).
    Uses last available rate on or before `when` (no future peek).
    """
    quote = str(quote).upper()
    if quote == "USD":
        return {
            "rate": 1.0,
            "quote": "USD",
            "fx_date": str(pd.Timestamp(when).normalize().date()) if when is not None else None,
            "fx_source": "IDENTITY_USD",
            "fx_fallback_status": "NONE",
            "ok": True,
        }
    if quote == "GBP":
        pair_quote = "GBP"
    elif quote == "EUR":
        pair_quote = "EUR"
    else:
        return {
            "rate": None,
            "quote": quote,
            "fx_date": None,
            "fx_source": None,
            "fx_fallback_status": "UNSUPPORTED_CURRENCY",
            "ok": False,
        }

    series = load_fx_series(pair_quote, fetcher=fetcher)
    if series.empty or when is None:
        return {
            "rate": None,
            "quote": pair_quote,
            "fx_date": None,
            "fx_source": FX_PAIR[pair_quote],
            "fx_fallback_status": "FX_SERIES_MISSING",
            "ok": False,
        }
    ts = pd.Timestamp(when).tz_localize(None).normalize()
    eligible = series[series.index <= ts]
    if eligible.empty:
        return {
            "rate": None,
            "quote": pair_quote,
            "fx_date": None,
            "fx_source": FX_PAIR[pair_quote],
            "fx_fallback_status": "NO_RATE_ON_OR_BEFORE_DATE",
            "ok": False,
        }
    fx_date = eligible.index[-1]
    rate = float(eligible.iloc[-1])
    if rate != rate or rate <= 0:
        return {
            "rate": None,
            "quote": pair_quote,
            "fx_date": str(fx_date.date()),
            "fx_source": FX_PAIR[pair_quote],
            "fx_fallback_status": "NON_FINITE_RATE",
            "ok": False,
        }
    return {
        "rate": rate,
        "quote": pair_quote,
        "fx_date": str(pd.Timestamp(fx_date).date()),
        "fx_source": FX_PAIR[pair_quote],
        "fx_fallback_status": "NONE",
        "ok": True,
    }


@dataclass
class LotUsdLedger:
    lot_id: str
    ticker: str
    instrument_currency: str
    entry_price_local: float
    exit_price_local: float | None
    quantity: float
    entry_price_major: float
    exit_price_major: float | None
    major_currency: str
    entry_fx_to_usd: float | None
    exit_fx_to_usd: float | None
    fees_local: float
    fees_usd: float | None
    cost_basis_usd: float | None
    proceeds_usd: float | None
    realized_pnl_local: float | None
    realized_pnl_usd: float | None
    dividend_usd: float | None
    entry_fx_source: str | None
    exit_fx_source: str | None
    entry_fx_date: str | None
    exit_fx_date: str | None
    entry_fx_fallback_status: str
    exit_fx_fallback_status: str
    validation_status: str
    validation_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_lot_usd_ledger(
    *,
    lot_id: str,
    ticker: str,
    entry_timestamp: Any,
    exit_timestamp: Any | None,
    entry_price_local: float,
    exit_price_local: float | None,
    quantity: float,
    fees_local: float = 0.0,
    dividend_local: float = 0.0,
    fetcher: Callable[[str], pd.DataFrame] | None = None,
) -> LotUsdLedger:
    ccy = instrument_currency(ticker)
    entry_major, major = to_major_currency_amount(entry_price_local, ccy)
    exit_major = None
    if exit_price_local is not None:
        exit_major, _ = to_major_currency_amount(exit_price_local, ccy)
    fees_major, _ = to_major_currency_amount(fees_local, ccy)
    div_major, _ = to_major_currency_amount(dividend_local, ccy)

    entry_fx = fx_rate_on(major, entry_timestamp, fetcher=fetcher)
    exit_fx = (
        fx_rate_on(major, exit_timestamp, fetcher=fetcher)
        if exit_timestamp is not None and exit_major is not None
        else {"rate": None, "fx_source": None, "fx_date": None, "fx_fallback_status": "NO_EXIT", "ok": major == "USD"}
    )

    realized_local = None
    if exit_price_local is not None:
        realized_local = (float(exit_price_local) - float(entry_price_local)) * float(quantity) - float(fees_local)

    cost_usd = proceeds_usd = pnl_usd = fees_usd = div_usd = None
    status = "OK"
    reason = None

    if not entry_fx.get("ok"):
        status = "DATA_INVALID"
        reason = f"entry_fx:{entry_fx.get('fx_fallback_status')}"
    elif exit_price_local is not None and not exit_fx.get("ok") and major != "USD":
        status = "DATA_INVALID"
        reason = f"exit_fx:{exit_fx.get('fx_fallback_status')}"
    else:
        er = float(entry_fx["rate"] or 1.0)
        cost_usd = entry_major * float(quantity) * er
        fees_usd = fees_major * er
        if exit_major is not None:
            xr = float(exit_fx["rate"] or er)
            proceeds_usd = exit_major * float(quantity) * xr
            pnl_usd = proceeds_usd - cost_usd - (fees_major * xr)
            div_usd = div_major * xr
        # Reject non-finite
        for label, val in (("cost", cost_usd), ("proceeds", proceeds_usd), ("pnl", pnl_usd)):
            if val is not None and (val != val or val in (float("inf"), float("-inf"))):
                status = "DATA_INVALID"
                reason = f"non_finite_{label}"
                cost_usd = proceeds_usd = pnl_usd = None
                break

    return LotUsdLedger(
        lot_id=lot_id,
        ticker=ticker,
        instrument_currency=ccy,
        entry_price_local=float(entry_price_local),
        exit_price_local=None if exit_price_local is None else float(exit_price_local),
        quantity=float(quantity),
        entry_price_major=entry_major,
        exit_price_major=exit_major,
        major_currency=major,
        entry_fx_to_usd=entry_fx.get("rate"),
        exit_fx_to_usd=exit_fx.get("rate"),
        fees_local=float(fees_local),
        fees_usd=fees_usd,
        cost_basis_usd=cost_usd,
        proceeds_usd=proceeds_usd,
        realized_pnl_local=realized_local,
        realized_pnl_usd=pnl_usd,
        dividend_usd=div_usd,
        entry_fx_source=entry_fx.get("fx_source"),
        exit_fx_source=exit_fx.get("fx_source"),
        entry_fx_date=entry_fx.get("fx_date"),
        exit_fx_date=exit_fx.get("fx_date"),
        entry_fx_fallback_status=str(entry_fx.get("fx_fallback_status")),
        exit_fx_fallback_status=str(exit_fx.get("fx_fallback_status")),
        validation_status=status,
        validation_reason=reason,
    )


def clear_fx_cache() -> None:
    _FX_CACHE.clear()
