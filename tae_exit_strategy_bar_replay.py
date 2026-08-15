#!/usr/bin/env python3
"""
TAE Exit Strategy Bar Replay — SMALL_ADAPTER (READ_ONLY / SHADOW).

Joins portfolio FIFO BUY lots (OPEN and/or CLOSED) to daily OHLCV and
evaluates BASELINE_FIXED, ATR_ADAPTIVE, TREND_FOLLOWER, HYBRID_ATR_TREND
bar-by-bar without look-ahead. Actual closed exits are benchmarks only.

Does NOT modify live_bot, core/trailing, or portfolio.csv.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from research.momentum.context_intelligence_research_v18 import compute_atr

PORTFOLIO_CSV = Path("portfolio.csv")
FORWARD_OBS_CSV = Path("tae_exit_strategy_forward_observations.csv")

STRATEGY_ARMS = (
    "BASELINE_FIXED",
    "ATR_ADAPTIVE",
    "TREND_FOLLOWER",
    "HYBRID_ATR_TREND",
)

COMMISSION_PER_TRADE_USD = 0.0
SLIPPAGE_BPS = 0.0
PREMATURE_LOOKAHEAD_BARS = 5
PREMATURE_EXCEED_PCT = 1.0
ATR_PERIOD = 14
EMA_FAST = 20
EMA_SLOW = 50
MIN_LOCKED_PROFIT_PCT = 2.0
MAX_REPLAY_CALENDAR_DAYS = None  # None = until last available bar / today
REALISTIC_ENTRY_SLIPPAGE_BPS = 5.0
REALISTIC_EXIT_SLIPPAGE_BPS = 5.0
COHORTS = ("OPEN_ONLY", "CLOSED_ONLY", "ALL")
LOT_ID_SCHEMA = "LOT|{ticker}|{entry_ts:%Y%m%d%H%M%S}|buyrow{buy_row}|qty{qty:.6f}|seq{seq}"

# Replay window context — set by run_bar_replay for horizon/capped methodologies.
# Strategy formulas are unchanged; only the post-entry window and forced label vary.
_REPLAY_CTX: dict[str, Any] = {
    "max_bars": None,
    "end_ts": None,
    "forced_label": "FORCED_END_OF_AVAILABLE_HISTORY",
    "methodology": "UNBOUNDED_AVAILABLE_HISTORY",
}


def set_replay_context(
    *,
    max_bars: int | None = None,
    end_ts: Any = None,
    forced_label: str = "FORCED_END_OF_AVAILABLE_HISTORY",
    methodology: str = "UNBOUNDED_AVAILABLE_HISTORY",
) -> None:
    _REPLAY_CTX["max_bars"] = max_bars
    _REPLAY_CTX["end_ts"] = pd.Timestamp(end_ts).normalize() if end_ts is not None else None
    _REPLAY_CTX["forced_label"] = forced_label
    _REPLAY_CTX["methodology"] = methodology


def reset_replay_context() -> None:
    set_replay_context()


def native_currency_for_ticker(ticker: str) -> str:
    t = str(ticker).upper()
    if t.endswith(".L"):
        return "GBp"  # Yahoo/LSE convention: pence sterling
    if t.endswith((".PA", ".DE", ".AS", ".MI", ".MC", ".BR")):
        return "EUR"
    return "USD"



def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _f(value: Any, default: float = 0.0) -> float:
    try:
        v = float(value)
        if math.isnan(v) or math.isinf(v):
            return default
        return v
    except (TypeError, ValueError):
        return default


def region_for_ticker(ticker: str) -> str:
    t = str(ticker).upper()
    if t.endswith(".L"):
        return "UK"
    if t.endswith((".PA", ".DE", ".AS", ".MI", ".MC", ".BR")):
        return "EU"
    return "US"


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def apply_slippage(price: float, *, side: str = "SELL") -> float:
    bps = SLIPPAGE_BPS / 10_000.0
    return price * (1.0 - bps) if side == "SELL" else price * (1.0 + bps)


def resolve_stop_exit_price(bar_open: float, bar_low: float, stop_price: float) -> float | None:
    """Conservative gap model: open below stop -> open; else low<=stop -> stop."""
    if bar_open <= stop_price:
        return apply_slippage(bar_open)
    if bar_low <= stop_price:
        return apply_slippage(stop_price)
    return None


def enrich_bars_causal(ohlcv: pd.DataFrame) -> pd.DataFrame:
    if ohlcv.empty:
        return ohlcv
    out = ohlcv.copy().sort_index()
    out = out[~out.index.duplicated(keep="last")]
    h = out["High"].astype(float)
    l = out["Low"].astype(float)
    c = out["Close"].astype(float)
    out["ATR14"] = compute_atr(h, l, c, ATR_PERIOD)
    out["ATR_Pct"] = (out["ATR14"] / c.replace(0, np.nan)) * 100.0
    out["EMA20"] = c.ewm(span=EMA_FAST, adjust=False, min_periods=EMA_FAST).mean()
    out["EMA50"] = c.ewm(span=EMA_SLOW, adjust=False, min_periods=EMA_SLOW).mean()
    out["Trend_State"] = np.where(
        out["EMA20"].isna() | out["EMA50"].isna(),
        "UNKNOWN",
        np.where(out["EMA20"] >= out["EMA50"], "POSITIVE", "NEGATIVE"),
    )
    return out


def volatility_bucket(atr_pct: float | None, *, p33: float, p66: float) -> str:
    if atr_pct is None or (isinstance(atr_pct, float) and math.isnan(atr_pct)):
        return "UNKNOWN"
    if atr_pct <= p33:
        return "LOW"
    if atr_pct <= p66:
        return "MEDIUM"
    return "HIGH"


@dataclass(frozen=True)
class ReplayPosition:
    ticker: str
    entry_timestamp: pd.Timestamp
    entry_price: float
    shares: float
    decision_id: str
    region: str
    lot_id: str = ""
    lot_status: str = "OPEN"  # OPEN | CLOSED
    actual_exit_timestamp: pd.Timestamp | None = None
    actual_exit_price: float | None = None
    actual_exit_reason: str | None = None
    buy_row: int | None = None
    sell_row: int | None = None
    data_quality: str = "OK"
    exclusion_reason: str | None = None


@dataclass(frozen=True)
class ReplayLot:
    """One FIFO BUY observation (full or residual after partial sells)."""
    lot_id: str
    ticker: str
    region: str
    entry_timestamp: pd.Timestamp
    entry_price: float
    entry_quantity: float
    status: str  # OPEN | CLOSED
    buy_row: int
    sell_row: int | None = None
    exit_timestamp: pd.Timestamp | None = None
    exit_price: float | None = None
    exit_reason: str | None = None
    decision_id: str | None = None
    data_quality: str = "OK"
    exclusion_reason: str | None = None
    seq: int = 0


def _lot_id(ticker: str, entry_ts: pd.Timestamp, buy_row: int, qty: float, seq: int) -> str:
    ts = pd.Timestamp(entry_ts)
    return (
        f"LOT|{ticker}|{ts.strftime('%Y%m%d%H%M%S')}|"
        f"buyrow{buy_row}|qty{qty:.6f}|seq{seq}"
    )


def reconstruct_fifo_lots(portfolio_path: Path = PORTFOLIO_CSV) -> list[ReplayLot]:
    """Rebuild every BUY lot via chronological FIFO. Does not mutate portfolio.csv.

    Partial SELLs create separate CLOSED observations for consumed quantity and leave
    residual OPEN lots with the original entry price/timestamp.
    """
    if not portfolio_path.is_file():
        return []
    df = pd.read_csv(portfolio_path)
    if df.empty or "Action" not in df.columns:
        return []
    df = df.copy()
    df["_row"] = df.index.astype(int)
    open_q: dict[str, list[dict[str, Any]]] = {}
    lots: list[ReplayLot] = []
    seq = 0
    for _, row in df.iterrows():
        ticker = str(row.get("Ticker", "")).upper().strip()
        action = str(row.get("Action", "")).upper().strip()
        if action not in {"BUY", "SELL"} or not ticker:
            continue
        price = _f(row.get("Price"))
        shares = _f(row.get("Shares"))
        ts = pd.to_datetime(row.get("Date"), errors="coerce")
        buy_row = int(row["_row"])
        if action == "BUY":
            if shares <= 0 or price <= 0 or pd.isna(ts):
                seq += 1
                lots.append(
                    ReplayLot(
                        lot_id=_lot_id(ticker, ts if pd.notna(ts) else pd.Timestamp("1970-01-01"), buy_row, shares, seq),
                        ticker=ticker,
                        region=region_for_ticker(ticker),
                        entry_timestamp=pd.Timestamp(ts) if pd.notna(ts) else pd.Timestamp("1970-01-01"),
                        entry_price=price,
                        entry_quantity=shares,
                        status="OPEN",
                        buy_row=buy_row,
                        data_quality="INVALID_PRICE" if price <= 0 or shares <= 0 else "MISSING_ENTRY_TIMESTAMP",
                        exclusion_reason="INVALID_PRICE" if price <= 0 or shares <= 0 else "MISSING_ENTRY_TIMESTAMP",
                        seq=seq,
                    )
                )
                continue
            open_q.setdefault(ticker, []).append(
                {"buy_row": buy_row, "ts": pd.Timestamp(ts), "price": price, "rem": shares, "orig": shares}
            )
        else:
            need = shares
            exit_ts = pd.Timestamp(ts) if pd.notna(ts) else None
            reason = str(row.get("Reason", "") or "")
            sell_row = buy_row
            q = open_q.setdefault(ticker, [])
            while need > 1e-9 and q:
                lot = q[0]
                take = min(lot["rem"], need)
                seq += 1
                lots.append(
                    ReplayLot(
                        lot_id=_lot_id(ticker, lot["ts"], lot["buy_row"], take, seq),
                        ticker=ticker,
                        region=region_for_ticker(ticker),
                        entry_timestamp=lot["ts"],
                        entry_price=float(lot["price"]),
                        entry_quantity=float(take),
                        status="CLOSED",
                        buy_row=int(lot["buy_row"]),
                        sell_row=sell_row,
                        exit_timestamp=exit_ts,
                        exit_price=price if price > 0 else None,
                        exit_reason=reason or None,
                        decision_id=None,
                        data_quality="OK",
                        exclusion_reason=None,
                        seq=seq,
                    )
                )
                lot["rem"] -= take
                need -= take
                if lot["rem"] <= 1e-9:
                    q.pop(0)
    # residual OPEN
    for ticker, q in open_q.items():
        for lot in q:
            if lot["rem"] <= 1e-9:
                continue
            seq += 1
            lots.append(
                ReplayLot(
                    lot_id=_lot_id(ticker, lot["ts"], lot["buy_row"], lot["rem"], seq),
                    ticker=ticker,
                    region=region_for_ticker(ticker),
                    entry_timestamp=lot["ts"],
                    entry_price=float(lot["price"]),
                    entry_quantity=float(lot["rem"]),
                    status="OPEN",
                    buy_row=int(lot["buy_row"]),
                    decision_id=f"PF-{ticker}-{lot['ts'].strftime('%Y%m%d')}",
                    data_quality="OK",
                    seq=seq,
                )
            )
    lots.sort(key=lambda x: (x.entry_timestamp, x.ticker, x.seq))
    return lots


def reconcile_fifo_quantities(portfolio_path: Path = PORTFOLIO_CSV) -> dict[str, Any]:
    """Per-ticker: sum(BUY)-sum(SELL) == residual OPEN quantity."""
    if not portfolio_path.is_file():
        return {"ok": True, "tickers": {}}
    df = pd.read_csv(portfolio_path)
    lots = reconstruct_fifo_lots(portfolio_path)
    out: dict[str, Any] = {}
    ok = True
    for ticker, g in df.groupby(df["Ticker"].astype(str).str.upper()):
        buys = float(pd.to_numeric(g.loc[g["Action"].astype(str).str.upper() == "BUY", "Shares"], errors="coerce").fillna(0).sum())
        sells = float(pd.to_numeric(g.loc[g["Action"].astype(str).str.upper() == "SELL", "Shares"], errors="coerce").fillna(0).sum())
        residual = round(buys - sells, 6)
        open_qty = round(sum(l.entry_quantity for l in lots if l.ticker == ticker and l.status == "OPEN"), 6)
        match = abs(residual - open_qty) < 1e-4
        ok = ok and match
        out[str(ticker)] = {"buy": buys, "sell": sells, "residual": residual, "open_lots_qty": open_qty, "match": match}
    return {"ok": ok, "tickers": out}


def load_replay_lots(
    cohort: str = "ALL",
    portfolio_path: Path = PORTFOLIO_CSV,
) -> list[ReplayLot]:
    """Canonical lot loader. cohort in OPEN_ONLY | CLOSED_ONLY | ALL."""
    cohort_u = str(cohort or "ALL").upper().replace("-", "_")
    if cohort_u in {"OPEN", "OPEN_ONLY"}:
        cohort_u = "OPEN_ONLY"
    elif cohort_u in {"CLOSED", "CLOSED_ONLY"}:
        cohort_u = "CLOSED_ONLY"
    else:
        cohort_u = "ALL"
    lots = reconstruct_fifo_lots(portfolio_path)
    if cohort_u == "OPEN_ONLY":
        return [l for l in lots if l.status == "OPEN" and not l.exclusion_reason]
    if cohort_u == "CLOSED_ONLY":
        return [l for l in lots if l.status == "CLOSED" and not l.exclusion_reason]
    return [l for l in lots if not l.exclusion_reason]


def lots_to_positions(lots: list[ReplayLot]) -> list[ReplayPosition]:
    out: list[ReplayPosition] = []
    for lot in lots:
        out.append(
            ReplayPosition(
                ticker=lot.ticker,
                entry_timestamp=lot.entry_timestamp,
                entry_price=lot.entry_price,
                shares=lot.entry_quantity,
                decision_id=lot.decision_id or lot.lot_id,
                region=lot.region,
                lot_id=lot.lot_id,
                lot_status=lot.status,
                actual_exit_timestamp=lot.exit_timestamp,
                actual_exit_price=lot.exit_price,
                actual_exit_reason=lot.exit_reason,
                buy_row=lot.buy_row,
                sell_row=lot.sell_row,
                data_quality=lot.data_quality,
                exclusion_reason=lot.exclusion_reason,
            )
        )
    return out


def load_open_positions(portfolio_path: Path = PORTFOLIO_CSV) -> list[ReplayPosition]:
    if not portfolio_path.is_file():
        return []
    df = pd.read_csv(portfolio_path)
    if df.empty or "Action" not in df.columns:
        return []
    positions: dict[str, dict[str, Any]] = {}
    for _, row in df.iterrows():
        ticker = str(row.get("Ticker", "")).upper().strip()
        action = str(row.get("Action", "")).upper().strip()
        if not ticker:
            continue
        price = _f(row.get("Price"))
        shares = _f(row.get("Shares"))
        ts = pd.to_datetime(row.get("Date"), errors="coerce")
        if action == "BUY" and shares > 0 and price > 0:
            cur = positions.get(ticker)
            if cur is None:
                positions[ticker] = {
                    "shares": shares,
                    "cost": price * shares,
                    "entry_ts": ts,
                    "entry_price": price,
                }
            else:
                new_shares = cur["shares"] + shares
                new_cost = cur["cost"] + price * shares
                positions[ticker] = {
                    "shares": new_shares,
                    "cost": new_cost,
                    "entry_ts": cur["entry_ts"] if pd.notna(cur["entry_ts"]) else ts,
                    "entry_price": new_cost / new_shares if new_shares else price,
                }
        elif action == "SELL" and ticker in positions:
            cur = positions[ticker]
            remaining = cur["shares"] - shares
            if remaining <= 1e-9:
                del positions[ticker]
            else:
                avg = cur["cost"] / cur["shares"] if cur["shares"] else cur["entry_price"]
                positions[ticker] = {
                    "shares": remaining,
                    "cost": avg * remaining,
                    "entry_ts": cur["entry_ts"],
                    "entry_price": avg,
                }
    out: list[ReplayPosition] = []
    for ticker, cur in positions.items():
        if cur["shares"] <= 0 or pd.isna(cur["entry_ts"]):
            continue
        entry_ts = pd.Timestamp(cur["entry_ts"])
        out.append(
            ReplayPosition(
                ticker=ticker,
                entry_timestamp=entry_ts,
                entry_price=float(cur["entry_price"]),
                shares=float(cur["shares"]),
                decision_id=f"PF-{ticker}-{entry_ts.strftime('%Y%m%d')}",
                region=region_for_ticker(ticker),
            )
        )
    return sorted(out, key=lambda p: (p.entry_timestamp, p.ticker))


def download_enriched_bars(ticker: str, fetcher: Callable[[str], pd.DataFrame] | None = None) -> pd.DataFrame:
    if fetcher is not None:
        raw = fetcher(ticker)
    else:
        from research.momentum.momentum_continuation_research_v11 import download_history

        raw = download_history(ticker)
    if raw is None or raw.empty:
        return pd.DataFrame()
    return enrich_bars_causal(raw)


@dataclass
class ArmState:
    highest_price: float
    lowest_price: float
    trailing_active: bool = False
    trailing_stop: float | None = None
    initial_stop: float = 0.0
    bearish_confirm: int = 0
    atr_warmup: bool = True
    entry_atr14: float | None = None
    entry_atr_pct: float | None = None
    entry_ema20: float | None = None
    entry_ema50: float | None = None
    entry_trend: str = "UNKNOWN"
    mfe_pct: float = 0.0
    mae_pct: float = 0.0
    mfe_price: float = 0.0


@dataclass
class TradeResult:
    strategy_arm: str
    ticker: str
    region: str
    decision_id: str
    entry_timestamp: str
    entry_price: float
    shares: float
    exit_timestamp: str | None
    exit_price: float | None
    exit_reason: str
    pnl: float
    pnl_pct: float
    bars_held: int
    hold_days: float
    mfe_pct: float
    mae_pct: float
    profit_capture_rate: float | None
    profit_giveback: float
    premature_exit_proxy: bool
    trailing_active_at_exit: bool
    status: str
    data_quality: str
    entry_atr_pct: float | None
    entry_trend: str
    volatility_bucket: str
    lot_id: str = ""
    lot_status: str = "OPEN"
    actual_exit_timestamp: str | None = None
    actual_exit_price: float | None = None
    actual_exit_reason: str | None = None
    actual_realized_pnl: float | None = None
    exit_vs_actual: str | None = None  # EARLIER | LATER | SAME_DAY | NO_ACTUAL | FORCED


def atr_params(atr14: float | None, price: float) -> dict[str, Any]:
    if atr14 is None or price <= 0 or (isinstance(atr14, float) and math.isnan(atr14)):
        return {
            "atr14": None,
            "atr_pct": None,
            "initial_stop_pct": None,
            "activation_pct": None,
            "trail_distance_pct": None,
            "warmup": True,
        }
    atr_pct = (atr14 / price) * 100.0
    initial_stop_pct = clamp(max(3.0, 1.5 * atr_pct), 3.0, 7.0)
    activation_pct = max(5.0, 1.5 * initial_stop_pct)
    trail_distance_pct = clamp(2.0 * atr_pct, 3.0, 8.0)
    return {
        "atr14": atr14,
        "atr_pct": atr_pct,
        "initial_stop_pct": initial_stop_pct,
        "activation_pct": activation_pct,
        "trail_distance_pct": trail_distance_pct,
        "warmup": False,
    }


def init_state(entry_price: float) -> ArmState:
    return ArmState(highest_price=entry_price, lowest_price=entry_price, mfe_price=entry_price)


def _pnl(entry: float, exit_price: float, shares: float) -> tuple[float, float]:
    net = (exit_price - entry) * shares - COMMISSION_PER_TRADE_USD
    pct = ((exit_price - entry) / entry) * 100.0 if entry else 0.0
    return round(net, 4), round(pct, 4)


def _update_excursions(state: ArmState, entry: float, high: float, low: float) -> None:
    state.highest_price = max(state.highest_price, high)
    state.lowest_price = min(state.lowest_price, low)
    fav = ((high - entry) / entry) * 100.0
    adv = ((low - entry) / entry) * 100.0
    if fav > state.mfe_pct:
        state.mfe_pct = fav
        state.mfe_price = high
    if adv < state.mae_pct:
        state.mae_pct = adv


def _capture_giveback(entry: float, exit_price: float, mfe_pct: float, shares: float) -> tuple[float | None, float]:
    realized_pct = ((exit_price - entry) / entry) * 100.0 if entry else 0.0
    capture = None
    if realized_pct > 0 and mfe_pct > 1e-9:
        capture = round(clamp(realized_pct / mfe_pct, 0.0, 2.0), 4)
    mfe_profit = (entry * (mfe_pct / 100.0)) * shares
    realized_profit = (exit_price - entry) * shares
    return capture, round(max(0.0, mfe_profit - realized_profit), 4)


def _premature_proxy(bars: pd.DataFrame, exit_idx: int, mfe_price: float) -> bool:
    if exit_idx < 0 or mfe_price <= 0:
        return False
    future = bars.iloc[exit_idx + 1 : exit_idx + 1 + PREMATURE_LOOKAHEAD_BARS]
    if future.empty:
        return False
    return bool(float(future["High"].max()) > mfe_price * (1.0 + PREMATURE_EXCEED_PCT / 100.0))


def _seed_entry(state: ArmState, row: pd.Series) -> None:
    state.entry_atr14 = None if pd.isna(row.get("ATR14")) else _f(row.get("ATR14"))
    state.entry_atr_pct = None if pd.isna(row.get("ATR_Pct")) else _f(row.get("ATR_Pct"))
    state.entry_ema20 = None if pd.isna(row.get("EMA20")) else _f(row.get("EMA20"))
    state.entry_ema50 = None if pd.isna(row.get("EMA50")) else _f(row.get("EMA50"))
    state.entry_trend = str(row.get("Trend_State", "UNKNOWN"))



def post_entry_window(
    bars: pd.DataFrame,
    entry_ts: pd.Timestamp,
    max_days: int | None = MAX_REPLAY_CALENDAR_DAYS,
    max_bars: int | None = None,
    end_ts: Any = None,
) -> pd.DataFrame:
    """Bars from entry day inclusive through optional caps. Warmup bars stay in `bars` only.

    Caps (applied in order): explicit end_ts, context end_ts, max_bars/context max_bars, max_days.
    """
    if bars.empty:
        return bars
    start = pd.Timestamp(entry_ts).normalize()
    post = bars[bars.index >= start]
    # Resolve caps from args or context
    ctx_end = _REPLAY_CTX.get("end_ts")
    ctx_max_bars = _REPLAY_CTX.get("max_bars")
    effective_end = end_ts if end_ts is not None else ctx_end
    effective_max_bars = max_bars if max_bars is not None else ctx_max_bars
    if effective_end is not None:
        post = post[post.index <= pd.Timestamp(effective_end).normalize()]
    if max_days is not None:
        end = start + pd.Timedelta(days=int(max_days))
        post = post[post.index <= end]
    if effective_max_bars is not None:
        post = post.iloc[: int(effective_max_bars)]
    return post


def _actual_fields(pos: ReplayPosition) -> dict[str, Any]:
    actual_pnl = None
    if pos.actual_exit_price is not None and pos.entry_price and pos.shares:
        actual_pnl = round((float(pos.actual_exit_price) - float(pos.entry_price)) * float(pos.shares), 4)
    return {
        "lot_id": getattr(pos, "lot_id", "") or "",
        "lot_status": getattr(pos, "lot_status", "OPEN") or "OPEN",
        "actual_exit_timestamp": str(pos.actual_exit_timestamp) if getattr(pos, "actual_exit_timestamp", None) is not None else None,
        "actual_exit_price": pos.actual_exit_price if getattr(pos, "actual_exit_price", None) is not None else None,
        "actual_exit_reason": getattr(pos, "actual_exit_reason", None),
        "actual_realized_pnl": actual_pnl,
    }


def _exit_vs_actual(pos: ReplayPosition, exit_ts, reason: str) -> str | None:
    if str(reason).startswith("FORCED"):
        return "FORCED"
    actual = getattr(pos, "actual_exit_timestamp", None)
    if actual is None or pd.isna(actual):
        return "NO_ACTUAL"
    sim = pd.Timestamp(exit_ts).normalize()
    act = pd.Timestamp(actual).normalize()
    if sim == act:
        return "SAME_DAY"
    if sim < act:
        return "EARLIER"
    return "LATER"


def _open_result(arm, pos, state, reason, vol_p33, vol_p66) -> TradeResult:
    meta = _actual_fields(pos)
    return TradeResult(
        strategy_arm=arm, ticker=pos.ticker, region=pos.region, decision_id=pos.decision_id,
        entry_timestamp=str(pos.entry_timestamp), entry_price=pos.entry_price, shares=pos.shares,
        exit_timestamp=None, exit_price=None, exit_reason=reason, pnl=0.0, pnl_pct=0.0,
        bars_held=0, hold_days=0.0, mfe_pct=0.0, mae_pct=0.0, profit_capture_rate=None,
        profit_giveback=0.0, premature_exit_proxy=False, trailing_active_at_exit=False,
        status="OPEN", data_quality=reason if reason in {"NO_BARS", "HISTORY_EMPTY", "ENTRY_NOT_FOUND"} else "MISSING_BARS",
        entry_atr_pct=state.entry_atr_pct, entry_trend=state.entry_trend,
        volatility_bucket=volatility_bucket(state.entry_atr_pct, p33=vol_p33, p66=vol_p66),
        exit_vs_actual="NO_ACTUAL",
        **meta,
    )


def _close_result(arm, pos, state, all_bars, post, exit_i, exit_ts, exit_price, reason, vol_p33, vol_p66) -> TradeResult:
    pnl, pnl_pct = _pnl(pos.entry_price, exit_price, pos.shares)
    capture, giveback = _capture_giveback(pos.entry_price, exit_price, state.mfe_pct, pos.shares)
    abs_idx = list(all_bars.index).index(post.index[exit_i]) if exit_i < len(post) else -1
    premature = _premature_proxy(all_bars, abs_idx, state.mfe_price) if not str(reason).startswith("FORCED") else False
    hold_days = max(0.0, (pd.Timestamp(exit_ts) - pos.entry_timestamp).total_seconds() / 86400.0)
    meta = _actual_fields(pos)
    return TradeResult(
        strategy_arm=arm, ticker=pos.ticker, region=pos.region, decision_id=pos.decision_id,
        entry_timestamp=str(pos.entry_timestamp), entry_price=pos.entry_price, shares=pos.shares,
        exit_timestamp=str(exit_ts), exit_price=round(exit_price, 4), exit_reason=reason,
        pnl=pnl, pnl_pct=pnl_pct, bars_held=exit_i + 1, hold_days=round(hold_days, 2),
        mfe_pct=round(state.mfe_pct, 4), mae_pct=round(state.mae_pct, 4),
        profit_capture_rate=capture, profit_giveback=giveback, premature_exit_proxy=premature,
        trailing_active_at_exit=state.trailing_active, status="CLOSED",
        data_quality="OK" if state.entry_atr_pct is not None else "INSUFFICIENT_WARMUP",
        entry_atr_pct=state.entry_atr_pct, entry_trend=state.entry_trend,
        volatility_bucket=volatility_bucket(state.entry_atr_pct, p33=vol_p33, p66=vol_p66),
        exit_vs_actual=_exit_vs_actual(pos, exit_ts, reason),
        **meta,
    )


def _forced(arm, pos, state, bars, post, vol_p33, vol_p66) -> TradeResult:
    last_ts = post.index[-1]
    label = str(_REPLAY_CTX.get("forced_label") or "FORCED_END_OF_AVAILABLE_HISTORY")
    return _close_result(
        arm, pos, state, bars, post, len(post) - 1, last_ts,
        apply_slippage(_f(post.iloc[-1]["Close"])), label, vol_p33, vol_p66,
    )


def replay_baseline_fixed(pos, bars, *, vol_p33, vol_p66) -> TradeResult:
    state = init_state(pos.entry_price)
    state.initial_stop = pos.entry_price * 0.97
    post = post_entry_window(bars, pos.entry_timestamp)
    if post.empty:
        return _open_result("BASELINE_FIXED", pos, state, "NO_BARS", vol_p33, vol_p66)
    _seed_entry(state, post.iloc[0])
    for i, (ts, row) in enumerate(post.iterrows()):
        o, h, l, c = _f(row["Open"]), _f(row["High"]), _f(row["Low"]), _f(row["Close"])
        _update_excursions(state, pos.entry_price, h, l)
        if not state.trailing_active:
            stop_exit = resolve_stop_exit_price(o, l, state.initial_stop)
            if stop_exit is not None:
                return _close_result("BASELINE_FIXED", pos, state, bars, post, i, ts, stop_exit, "INITIAL_STOP", vol_p33, vol_p66)
        pnl_high = ((state.highest_price - pos.entry_price) / pos.entry_price) * 100.0
        if not state.trailing_active and pnl_high >= 5.0:
            state.trailing_active = True
        if state.trailing_active:
            candidate = max(state.highest_price * 0.97, pos.entry_price * 1.02)
            state.trailing_stop = candidate if state.trailing_stop is None else max(state.trailing_stop, candidate)
            trail_exit = resolve_stop_exit_price(o, l, state.trailing_stop)
            if trail_exit is not None:
                return _close_result("BASELINE_FIXED", pos, state, bars, post, i, ts, trail_exit, "TRAILING_STOP", vol_p33, vol_p66)
    return _forced("BASELINE_FIXED", pos, state, bars, post, vol_p33, vol_p66)


def replay_atr_adaptive(pos, bars, *, vol_p33, vol_p66) -> TradeResult:
    state = init_state(pos.entry_price)
    post = post_entry_window(bars, pos.entry_timestamp)
    if post.empty:
        return _open_result("ATR_ADAPTIVE", pos, state, "NO_BARS", vol_p33, vol_p66)
    _seed_entry(state, post.iloc[0])
    p0 = atr_params(state.entry_atr14, _f(post.iloc[0]["Close"]) or pos.entry_price)
    state.atr_warmup = bool(p0["warmup"])
    state.initial_stop = pos.entry_price * 0.97 if state.atr_warmup else pos.entry_price * (1.0 - float(p0["initial_stop_pct"]) / 100.0)
    for i, (ts, row) in enumerate(post.iterrows()):
        o, h, l, c = _f(row["Open"]), _f(row["High"]), _f(row["Low"]), _f(row["Close"])
        atr14 = None if pd.isna(row.get("ATR14")) else _f(row.get("ATR14"))
        params = atr_params(atr14, c or pos.entry_price)
        if not params["warmup"] and state.atr_warmup:
            state.atr_warmup = False
            if not state.trailing_active:
                state.initial_stop = pos.entry_price * (1.0 - float(params["initial_stop_pct"]) / 100.0)
        _update_excursions(state, pos.entry_price, h, l)
        if not state.trailing_active:
            stop_exit = resolve_stop_exit_price(o, l, state.initial_stop)
            if stop_exit is not None:
                return _close_result("ATR_ADAPTIVE", pos, state, bars, post, i, ts, stop_exit, "INITIAL_STOP", vol_p33, vol_p66)
        pnl_pct = ((state.highest_price - pos.entry_price) / pos.entry_price) * 100.0
        act = float(params["activation_pct"] or 5.0)
        if not state.trailing_active and pnl_pct >= (5.0 if params["warmup"] else act):
            state.trailing_active = True
        if state.trailing_active:
            atr_val = float(params["atr14"]) if params["atr14"] is not None else state.highest_price * 0.015
            trail_dist = float(params["trail_distance_pct"] or 3.0)
            candidate = max(
                state.highest_price - 2.0 * atr_val,
                state.highest_price * (1.0 - trail_dist / 100.0),
                pos.entry_price * 1.02,
            )
            state.trailing_stop = candidate if state.trailing_stop is None else max(state.trailing_stop, candidate)
            trail_exit = resolve_stop_exit_price(o, l, state.trailing_stop)
            if trail_exit is not None:
                return _close_result("ATR_ADAPTIVE", pos, state, bars, post, i, ts, trail_exit, "TRAILING_STOP", vol_p33, vol_p66)
    return _forced("ATR_ADAPTIVE", pos, state, bars, post, vol_p33, vol_p66)


def replay_trend_follower(pos, bars, *, vol_p33, vol_p66) -> TradeResult:
    state = init_state(pos.entry_price)
    state.initial_stop = pos.entry_price * 0.97
    post = post_entry_window(bars, pos.entry_timestamp)
    if post.empty:
        return _open_result("TREND_FOLLOWER", pos, state, "NO_BARS", vol_p33, vol_p66)
    _seed_entry(state, post.iloc[0])
    for i, (ts, row) in enumerate(post.iterrows()):
        o, h, l, c = _f(row["Open"]), _f(row["High"]), _f(row["Low"]), _f(row["Close"])
        _update_excursions(state, pos.entry_price, h, l)
        stop_exit = resolve_stop_exit_price(o, l, state.initial_stop)
        if stop_exit is not None:
            return _close_result("TREND_FOLLOWER", pos, state, bars, post, i, ts, stop_exit, "INITIAL_STOP", vol_p33, vol_p66)
        if str(row.get("Trend_State", "UNKNOWN")) == "NEGATIVE":
            state.bearish_confirm += 1
        else:
            state.bearish_confirm = 0
        if state.bearish_confirm >= 2:
            return _close_result(
                "TREND_FOLLOWER", pos, state, bars, post, i, ts, apply_slippage(c),
                "TREND_DETERIORATION_CONFIRMED", vol_p33, vol_p66,
            )
    return _forced("TREND_FOLLOWER", pos, state, bars, post, vol_p33, vol_p66)


def replay_hybrid(pos, bars, *, vol_p33, vol_p66) -> TradeResult:
    state = init_state(pos.entry_price)
    post = post_entry_window(bars, pos.entry_timestamp)
    if post.empty:
        return _open_result("HYBRID_ATR_TREND", pos, state, "NO_BARS", vol_p33, vol_p66)
    _seed_entry(state, post.iloc[0])
    p0 = atr_params(state.entry_atr14, _f(post.iloc[0]["Close"]) or pos.entry_price)
    state.atr_warmup = bool(p0["warmup"])
    state.initial_stop = pos.entry_price * 0.97 if state.atr_warmup else pos.entry_price * (1.0 - float(p0["initial_stop_pct"]) / 100.0)
    for i, (ts, row) in enumerate(post.iterrows()):
        o, h, l, c = _f(row["Open"]), _f(row["High"]), _f(row["Low"]), _f(row["Close"])
        atr14 = None if pd.isna(row.get("ATR14")) else _f(row.get("ATR14"))
        params = atr_params(atr14, c or pos.entry_price)
        if not params["warmup"] and state.atr_warmup:
            state.atr_warmup = False
            if not state.trailing_active:
                state.initial_stop = pos.entry_price * (1.0 - float(params["initial_stop_pct"]) / 100.0)
        _update_excursions(state, pos.entry_price, h, l)
        if not state.trailing_active:
            stop_exit = resolve_stop_exit_price(o, l, state.initial_stop)
            if stop_exit is not None:
                return _close_result("HYBRID_ATR_TREND", pos, state, bars, post, i, ts, stop_exit, "INITIAL_STOP", vol_p33, vol_p66)
        pnl_pct = ((state.highest_price - pos.entry_price) / pos.entry_price) * 100.0
        act = float(params["activation_pct"] or 5.0)
        if not state.trailing_active and pnl_pct >= (5.0 if params["warmup"] else act):
            state.trailing_active = True
        if state.trailing_active:
            atr_val = float(params["atr14"]) if params["atr14"] is not None else state.highest_price * 0.015
            trail_dist = float(params["trail_distance_pct"] or 3.0)
            candidate = max(
                state.highest_price - 2.0 * atr_val,
                state.highest_price * (1.0 - trail_dist / 100.0),
                pos.entry_price * 1.02,
            )
            state.trailing_stop = candidate if state.trailing_stop is None else max(state.trailing_stop, candidate)
            trail_exit = resolve_stop_exit_price(o, l, state.trailing_stop)
            if trail_exit is not None:
                return _close_result("HYBRID_ATR_TREND", pos, state, bars, post, i, ts, trail_exit, "TRAILING_STOP", vol_p33, vol_p66)
        if str(row.get("Trend_State", "UNKNOWN")) == "NEGATIVE":
            state.bearish_confirm += 1
        else:
            state.bearish_confirm = 0
        if state.bearish_confirm >= 2:
            atr_val = float(params["atr14"]) if params["atr14"] is not None else abs(c) * 0.015
            if state.trailing_active and state.trailing_stop is not None:
                tightened = max(state.trailing_stop, c - 1.0 * atr_val, pos.entry_price * 1.02)
                state.trailing_stop = max(state.trailing_stop, tightened)
                if c < state.trailing_stop or l <= state.trailing_stop:
                    exit_px = resolve_stop_exit_price(o, l, state.trailing_stop) or apply_slippage(c)
                    return _close_result(
                        "HYBRID_ATR_TREND", pos, state, bars, post, i, ts, exit_px,
                        "HYBRID_TREND_PROTECTION", vol_p33, vol_p66,
                    )
            else:
                return _close_result(
                    "HYBRID_ATR_TREND", pos, state, bars, post, i, ts, apply_slippage(c),
                    "TREND_DETERIORATION_CONFIRMED", vol_p33, vol_p66,
                )
    return _forced("HYBRID_ATR_TREND", pos, state, bars, post, vol_p33, vol_p66)


REPLAYERS = {
    "BASELINE_FIXED": replay_baseline_fixed,
    "ATR_ADAPTIVE": replay_atr_adaptive,
    "TREND_FOLLOWER": replay_trend_follower,
    "HYBRID_ATR_TREND": replay_hybrid,
}


def aggregate_arm_metrics(trades: list[TradeResult]) -> dict[str, Any]:
    closed = [t for t in trades if t.status == "CLOSED"]
    open_at_end = [t for t in trades if t.status == "OPEN"]
    pnls = pd.Series([t.pnl for t in closed], dtype=float)
    winners = pnls[pnls > 0]
    losers = pnls[pnls < 0]
    gp = float(winners.sum()) if len(winners) else 0.0
    gl = float(abs(losers.sum())) if len(losers) else 0.0
    pf = None if gl == 0 and gp == 0 else (float("inf") if gl == 0 else round(gp / gl, 4))
    hold_days = [t.hold_days for t in closed]
    bars_held = [t.bars_held for t in closed]
    captures = [t.profit_capture_rate for t in closed if t.profit_capture_rate is not None and t.pnl > 0]
    ordered = sorted(closed, key=lambda t: str(t.exit_timestamp or ""))
    cum = pd.Series([t.pnl for t in ordered], dtype=float).cumsum()
    mdd = float((cum - cum.cummax()).min()) if not cum.empty else 0.0
    n = len(closed)
    conf = "NONE"
    if n >= 100:
        conf = "HIGH"
    elif n >= 30:
        conf = "MEDIUM"
    elif n >= 10:
        conf = "LOW"
    elif n > 0:
        conf = "VERY_LOW"

    def _c(sub: str) -> int:
        return sum(1 for t in closed if sub in t.exit_reason)

    return {
        "sample_size": len(trades),
        "closed_trades": n,
        "open_at_end": len(open_at_end),
        "net_pnl": round(float(pnls.sum()), 2) if n else 0.0,
        "gross_profit": round(gp, 2),
        "gross_loss": round(gl, 2),
        "profit_factor": pf,
        "win_rate": round(float((pnls > 0).mean()), 4) if n else 0.0,
        "expectancy": round(float(pnls.mean()), 4) if n else 0.0,
        "average_winner": round(float(winners.mean()), 2) if len(winners) else 0.0,
        "average_loser": round(float(losers.mean()), 2) if len(losers) else 0.0,
        "median_winner": round(float(winners.median()), 2) if len(winners) else 0.0,
        "median_loser": round(float(losers.median()), 2) if len(losers) else 0.0,
        "largest_winner": round(float(winners.max()), 2) if len(winners) else 0.0,
        "largest_loser": round(float(losers.min()), 2) if len(losers) else 0.0,
        "max_drawdown": round(mdd, 2),
        "average_hold_time": round(float(np.mean(hold_days)), 2) if hold_days else None,
        "median_hold_time": round(float(np.median(hold_days)), 2) if hold_days else None,
        "average_bars_held": round(float(np.mean(bars_held)), 2) if bars_held else None,
        "median_bars_held": round(float(np.median(bars_held)), 2) if bars_held else None,
        "MFE_avg_pct": round(float(np.mean([t.mfe_pct for t in closed])), 4) if closed else None,
        "MAE_avg_pct": round(float(np.mean([t.mae_pct for t in closed])), 4) if closed else None,
        "profit_capture_rate": round(float(np.mean(captures)), 4) if captures else None,
        "profit_giveback": round(float(sum(t.profit_giveback for t in closed)), 2),
        "premature_exit_count": sum(1 for t in closed if t.premature_exit_proxy),
        "initial_stop_exit_count": _c("INITIAL_STOP"),
        "trailing_exit_count": _c("TRAILING_STOP"),
        "trend_exit_count": _c("TREND_DETERIORATION"),
        "hybrid_protection_exit_count": _c("HYBRID_TREND_PROTECTION"),
        "forced_end_of_replay_exit_count": _c("FORCED_END_OF_REPLAY"),
        "percent_positions_exceeding_5pct": round(100.0 * sum(1 for t in closed if t.mfe_pct >= 5.0) / n, 2) if n else 0.0,
        "percent_winners_exceeding_10pct": round(100.0 * sum(1 for t in closed if t.pnl > 0 and t.pnl_pct >= 10.0) / max(1, len(winners)), 2) if len(winners) else 0.0,
        "percent_winners_exceeding_20pct": round(100.0 * sum(1 for t in closed if t.pnl > 0 and t.pnl_pct >= 20.0) / max(1, len(winners)), 2) if len(winners) else 0.0,
        "confidence_classification": conf,
    }


def breakdown(trades: list[TradeResult], key: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[TradeResult]] = {}
    for t in trades:
        groups.setdefault(str(getattr(t, key, "UNKNOWN") or "UNKNOWN"), []).append(t)
    return {k: aggregate_arm_metrics(v) for k, v in sorted(groups.items())}


def run_bar_replay(
    *,
    portfolio_path: Path = PORTFOLIO_CSV,
    fetcher: Callable[[str], pd.DataFrame] | None = None,
    positions: list[ReplayPosition] | None = None,
    bars_by_ticker: dict[str, pd.DataFrame] | None = None,
    cohort: str = "ALL",
    max_bars: int | None = None,
    methodology: str = "UNBOUNDED_AVAILABLE_HISTORY",
    actual_exit_capped: bool = False,
    min_bars_required: int | None = None,
) -> dict[str, Any]:
    """Replay A/B/C/D for a cohort of positions/lots.

    Default cohort ALL uses FIFO lots (open+closed). Pass positions= to override.
    Actual closed exits are retained as benchmarks and do NOT truncate counterfactual replay
    unless actual_exit_capped=True.
    """
    lot_stats: dict[str, Any] = {}
    if positions is None:
        lots = load_replay_lots(cohort=cohort, portfolio_path=portfolio_path)
        positions = lots_to_positions(lots)
        all_lots = reconstruct_fifo_lots(portfolio_path)
        lot_stats = {
            "total_buy_lots": len(all_lots),
            "open_lots": sum(1 for l in all_lots if l.status == "OPEN"),
            "closed_lots": sum(1 for l in all_lots if l.status == "CLOSED"),
            "cohort": str(cohort).upper(),
            "cohort_lots_selected": len(lots),
            "fifo_reconcile": reconcile_fifo_quantities(portfolio_path),
            "lot_id_schema": LOT_ID_SCHEMA,
        }
    trades_by_arm: dict[str, list[TradeResult]] = {arm: [] for arm in STRATEGY_ARMS}
    data_quality: dict[str, Any] = {
        "positions": len(positions),
        "tickers_loaded": 0,
        "tickers_failed": [],
        "exclusion_reasons": {},
    }
    cache: dict[str, pd.DataFrame] = dict(bars_by_ticker or {})
    atr_samples: list[float] = []
    for pos in positions:
        if pos.ticker not in cache:
            try:
                cache[pos.ticker] = download_enriched_bars(pos.ticker, fetcher=fetcher)
            except Exception:
                cache[pos.ticker] = pd.DataFrame()
        bars = cache[pos.ticker]
        if bars.empty:
            data_quality["tickers_failed"].append(pos.ticker)
            data_quality["exclusion_reasons"]["HISTORY_EMPTY"] = data_quality["exclusion_reasons"].get("HISTORY_EMPTY", 0) + 1
        else:
            data_quality["tickers_loaded"] += 1
            atr_samples.extend([float(x) for x in bars["ATR_Pct"].dropna().tail(60).tolist()])
    vol_p33 = float(np.percentile(atr_samples, 33)) if atr_samples else 1.5
    vol_p66 = float(np.percentile(atr_samples, 66)) if atr_samples else 3.0

    eligible_positions: list[ReplayPosition] = []
    try:
        for pos in positions:
            bars = cache.get(pos.ticker, pd.DataFrame())
            if bars.empty:
                data_quality["exclusion_reasons"]["HISTORY_EMPTY"] = data_quality["exclusion_reasons"].get("HISTORY_EMPTY", 0) + 1
                for arm in STRATEGY_ARMS:
                    trades_by_arm[arm].append(
                        _open_result(arm, pos, init_state(pos.entry_price), "HISTORY_EMPTY", vol_p33, vol_p66)
                    )
                continue
            # Configure window for this lot
            end_ts = None
            if actual_exit_capped and getattr(pos, "actual_exit_timestamp", None) is not None:
                end_ts = pos.actual_exit_timestamp
                forced_label = "FORCED_ACTUAL_EXIT_CAP"
                meth = "ACTUAL_EXIT_CAPPED"
            elif actual_exit_capped:
                forced_label = "FORCED_CURRENT_DATE_OPEN_POSITION"
                meth = "ACTUAL_EXIT_CAPPED"
            elif max_bars is not None:
                forced_label = "FORCED_MAX_HORIZON"
                meth = methodology
            elif str(getattr(pos, "lot_status", "OPEN") or "OPEN").upper() == "OPEN":
                forced_label = "FORCED_CURRENT_DATE_OPEN_POSITION"
                meth = methodology
            else:
                forced_label = "FORCED_END_OF_AVAILABLE_HISTORY"
                meth = methodology
            set_replay_context(max_bars=max_bars, end_ts=end_ts, forced_label=forced_label, methodology=meth)
            post = post_entry_window(bars, pos.entry_timestamp)
            if post.empty:
                data_quality["exclusion_reasons"]["ENTRY_NOT_FOUND"] = data_quality["exclusion_reasons"].get("ENTRY_NOT_FOUND", 0) + 1
                for arm in STRATEGY_ARMS:
                    trades_by_arm[arm].append(
                        _open_result(arm, pos, init_state(pos.entry_price), "ENTRY_NOT_FOUND", vol_p33, vol_p66)
                    )
                continue
            start_n = pd.Timestamp(pos.entry_timestamp).normalize()
            avail = int((bars.index >= start_n).sum())
            # For horizon modes, require enough bars unless using available slice < required → exclude
            need = min_bars_required if min_bars_required is not None else max_bars
            if need is not None and avail < int(need):
                data_quality["exclusion_reasons"]["INSUFFICIENT_HORIZON"] = data_quality["exclusion_reasons"].get("INSUFFICIENT_HORIZON", 0) + 1
                for arm in STRATEGY_ARMS:
                    trades_by_arm[arm].append(
                        _open_result(arm, pos, init_state(pos.entry_price), "INSUFFICIENT_HORIZON", vol_p33, vol_p66)
                    )
                continue
            from research_core.accounting.price_basis_align import align_position_to_bars

            aligned_pos, align_meta = align_position_to_bars(pos, bars)
            if align_meta.get("status") == "DATA_INVALID" and align_meta.get("reason") == "NOTIONAL_DRIFT_AFTER_SPLIT_ALIGN":
                data_quality["exclusion_reasons"]["PRICE_BASIS_INVALID"] = data_quality["exclusion_reasons"].get("PRICE_BASIS_INVALID", 0) + 1
                for arm in STRATEGY_ARMS:
                    trades_by_arm[arm].append(
                        _open_result(arm, pos, init_state(pos.entry_price), "PRICE_BASIS_INVALID", vol_p33, vol_p66)
                    )
                continue
            eligible_positions.append(aligned_pos)
            for arm, fn in REPLAYERS.items():
                tr = fn(aligned_pos, bars, vol_p33=vol_p33, vol_p66=vol_p66)
                # Attach split meta onto trade via data_quality when applied
                if align_meta.get("ratio", 1.0) != 1.0 and tr.status == "CLOSED":
                    tr.data_quality = f"{tr.data_quality}|{align_meta.get('status')}"
                trades_by_arm[arm].append(tr)
    finally:
        reset_replay_context()

    strategies = []
    for arm in STRATEGY_ARMS:
        # Metrics only on CLOSED simulated trades with real exits / forced
        metrics = aggregate_arm_metrics([t for t in trades_by_arm[arm] if t.status == "CLOSED"])
        # Keep sample_size as all attempted
        metrics["sample_size"] = len(trades_by_arm[arm])
        metrics["attempted"] = len(trades_by_arm[arm])
        metrics["history_excluded"] = sum(1 for t in trades_by_arm[arm] if t.status == "OPEN")
        strategies.append({"strategy_id": arm, "metrics": metrics, "trades": [asdict(t) for t in trades_by_arm[arm]]})

    ranked = sorted(
        strategies,
        key=lambda s: (s["metrics"].get("net_pnl") or 0.0, s["metrics"].get("expectancy") or 0.0),
        reverse=True,
    )
    return {
        "certainty": "historical_counterfactual",
        "source": "bar_replay_adapter",
        "data_audit_verdict": "SMALL_BAR_REPLAY_ADAPTER_REQUIRED",
        "cohort": str(cohort).upper(),
        "methodology_id": ("ACTUAL_EXIT_CAPPED" if actual_exit_capped else methodology),
        "max_bars": max_bars,
        "actual_exit_capped": actual_exit_capped,
        "lot_reconstruction": lot_stats,
        "methodology": {
            "commission_per_trade_usd": COMMISSION_PER_TRADE_USD,
            "slippage_bps": SLIPPAGE_BPS,
            "stop_execution": "gap_open_else_stop",
            "same_bar_ambiguity": "conservative_stop_priority_then_trail",
            "forced_close": "last_available_close",
            "closed_actual_exit": "benchmark_only_does_not_truncate_counterfactual",
            "replay_window": "entry_day_to_last_available_bar_unless_MAX_REPLAY_CALENDAR_DAYS",
            "max_replay_calendar_days": MAX_REPLAY_CALENDAR_DAYS,
            "premature_exit": "proxy_only",
            "atr_warmup": "fixed_3pct_initial_stop_until_ATR14_available",
            "no_look_ahead": True,
            "indicator_sources": {
                "ATR14": "research.momentum.context_intelligence_research_v18.compute_atr",
                "EMA20_EMA50": "ewm span causal on Close",
                "trend": "EMA20>=EMA50 POSITIVE else NEGATIVE; 2-bar confirm",
            },
            "volatility_thresholds": {"p33_atr_pct": vol_p33, "p66_atr_pct": vol_p66},
        },
        "positions": len(eligible_positions),
        "positions_attempted": len(positions),
        "data_quality": data_quality,
        "strategies": strategies,
        "strategy_rankings": [
            {
                "strategy_id": s["strategy_id"],
                "net_pnl": s["metrics"]["net_pnl"],
                "profit_factor": s["metrics"]["profit_factor"],
                "expectancy": s["metrics"]["expectancy"],
                "max_drawdown": s["metrics"]["max_drawdown"],
                "profit_capture_rate": s["metrics"]["profit_capture_rate"],
            }
            for s in ranked
        ],
        "ticker_breakdown": {arm: breakdown([t for t in trades_by_arm[arm] if t.status == "CLOSED"], "ticker") for arm in STRATEGY_ARMS},
        "region_breakdown": {arm: breakdown([t for t in trades_by_arm[arm] if t.status == "CLOSED"], "region") for arm in STRATEGY_ARMS},
        "volatility_breakdown": {arm: breakdown([t for t in trades_by_arm[arm] if t.status == "CLOSED"], "volatility_bucket") for arm in STRATEGY_ARMS},
        "trend_regime_breakdown": {arm: breakdown([t for t in trades_by_arm[arm] if t.status == "CLOSED"], "entry_trend") for arm in STRATEGY_ARMS},
        "exit_reason_breakdown": {
            arm: {r: sum(1 for t in trades_by_arm[arm] if t.exit_reason == r)
                  for r in sorted({t.exit_reason for t in trades_by_arm[arm]})}
            for arm in STRATEGY_ARMS
        },
        "_trades_by_arm": trades_by_arm,
    }


def apply_realistic_cost_to_metrics(trades: list[TradeResult]) -> dict[str, Any]:
    """Sensitivity: ±5 bps entry/exit on fill prices — does not re-run strategy logic."""
    adjusted: list[TradeResult] = []
    for t in trades:
        if t.status != "CLOSED" or t.exit_price is None:
            continue
        entry = t.entry_price * (1.0 + REALISTIC_ENTRY_SLIPPAGE_BPS / 10_000.0)
        exit_px = t.exit_price * (1.0 - REALISTIC_EXIT_SLIPPAGE_BPS / 10_000.0)
        pnl = round((exit_px - entry) * t.shares - COMMISSION_PER_TRADE_USD, 4)
        pct = round(((exit_px - entry) / entry) * 100.0, 4) if entry else 0.0
        # shallow copy via dataclass replace pattern
        adjusted.append(
            TradeResult(
                **{**asdict(t), "pnl": pnl, "pnl_pct": pct, "entry_price": entry, "exit_price": exit_px}
            )
        )
    return aggregate_arm_metrics(adjusted)


def actual_closed_benchmark(lots: list[ReplayLot] | None = None, *, fx_fetcher=None) -> dict[str, Any]:
    lots = lots if lots is not None else load_replay_lots("CLOSED_ONLY")
    from research_core.accounting.fx_normalize import build_lot_usd_ledger, instrument_currency

    rows = []
    for lot in lots:
        if lot.status != "CLOSED" or lot.exit_price is None:
            continue
        pnl = (float(lot.exit_price) - float(lot.entry_price)) * float(lot.entry_quantity)
        ledger = build_lot_usd_ledger(
            lot_id=lot.lot_id,
            ticker=lot.ticker,
            entry_timestamp=lot.entry_timestamp,
            exit_timestamp=lot.exit_timestamp,
            entry_price_local=float(lot.entry_price),
            exit_price_local=float(lot.exit_price),
            quantity=float(lot.entry_quantity),
            fetcher=fx_fetcher,
        )
        rows.append({
            "lot_id": lot.lot_id,
            "ticker": lot.ticker,
            "region": lot.region,
            "instrument_currency": instrument_currency(lot.ticker),
            "pnl": pnl,
            "pnl_native": pnl,
            "pnl_usd": ledger.realized_pnl_usd,
            "fx_validation": ledger.validation_status,
            "fx_reason": ledger.validation_reason,
            "ledger": ledger.to_dict(),
            "pnl_pct": ((lot.exit_price - lot.entry_price) / lot.entry_price) * 100.0 if lot.entry_price else 0.0,
            "exit_reason": lot.exit_reason or "UNKNOWN",
            "hold_days": (
                (pd.Timestamp(lot.exit_timestamp) - pd.Timestamp(lot.entry_timestamp)).total_seconds() / 86400.0
                if lot.exit_timestamp is not None else None
            ),
        })
    if not rows:
        return {"sample_size": 0, "metrics": {}}
    pnls = pd.Series([r["pnl"] for r in rows], dtype=float)
    winners = pnls[pnls > 0]
    losers = pnls[pnls < 0]
    gp = float(winners.sum()) if len(winners) else 0.0
    gl = float(abs(losers.sum())) if len(losers) else 0.0
    pf = None if gl == 0 and gp == 0 else (float("inf") if gl == 0 else round(gp / gl, 4))
    ordered = pnls.cumsum()
    mdd = float((ordered - ordered.cummax()).min()) if not ordered.empty else 0.0
    reasons: dict[str, int] = {}
    for r in rows:
        reasons[r["exit_reason"]] = reasons.get(r["exit_reason"], 0) + 1
    usd_vals = [r["pnl_usd"] for r in rows if r.get("pnl_usd") is not None]
    usd = pd.Series(usd_vals, dtype=float) if usd_vals else pd.Series(dtype=float)
    invalid_fx = [r["lot_id"] for r in rows if r.get("fx_validation") != "OK"]
    by_ccy: dict[str, float] = {}
    for r in rows:
        ccy = str(r.get("instrument_currency") or "?")
        by_ccy[ccy] = by_ccy.get(ccy, 0.0) + float(r.get("pnl_native") or 0.0)
    by_ccy_usd: dict[str, float] = {}
    for r in rows:
        if r.get("pnl_usd") is None:
            continue
        ccy = str(r.get("instrument_currency") or "?")
        by_ccy_usd[ccy] = by_ccy_usd.get(ccy, 0.0) + float(r["pnl_usd"])
    return {
        "sample_size": len(rows),
        "actual_net_pnl": round(float(pnls.sum()), 2),
        "actual_net_pnl_native_unnormalized": round(float(pnls.sum()), 2),
        "actual_net_pnl_usd": round(float(usd.sum()), 2) if len(usd) else None,
        "actual_profit_factor": pf,
        "actual_win_rate": round(float((pnls > 0).mean()), 4),
        "actual_expectancy": round(float(pnls.mean()), 4),
        "actual_average_winner": round(float(winners.mean()), 2) if len(winners) else 0.0,
        "actual_average_loser": round(float(losers.mean()), 2) if len(losers) else 0.0,
        "actual_max_drawdown": round(mdd, 2),
        "actual_exit_reason_breakdown": reasons,
        "pnl_by_currency_native": {k: round(v, 4) for k, v in sorted(by_ccy.items())},
        "pnl_by_currency_usd": {k: round(v, 4) for k, v in sorted(by_ccy_usd.items())},
        "fx_invalid_lots": invalid_fx,
        "lots": rows,
        "currency_note": "actual_net_pnl is native-unnormalized (legacy); prefer actual_net_pnl_usd",
    }


def compare_to_actual(trades: list[TradeResult], actual: dict[str, Any]) -> dict[str, Any]:
    closed = [t for t in trades if t.status == "CLOSED"]
    sim_pnl = sum(t.pnl for t in closed)
    actual_pnl = float(actual.get("actual_net_pnl") or 0.0)
    earlier = sum(1 for t in closed if t.exit_vs_actual == "EARLIER")
    later = sum(1 for t in closed if t.exit_vs_actual == "LATER")
    same = sum(1 for t in closed if t.exit_vs_actual == "SAME_DAY")
    # avoided losses / reduced winners vs actual per lot where actual_realized_pnl known
    avoided = 0
    reduced_winners = 0
    enlarged_winners = 0
    for t in closed:
        if t.actual_realized_pnl is None:
            continue
        if t.actual_realized_pnl < 0 and t.pnl > t.actual_realized_pnl:
            avoided += 1
        if t.actual_realized_pnl > 0 and t.pnl < t.actual_realized_pnl:
            reduced_winners += 1
        if t.actual_realized_pnl > 0 and t.pnl > t.actual_realized_pnl:
            enlarged_winners += 1
    return {
        "delta_vs_actual_pnl": round(sim_pnl - actual_pnl, 2),
        "delta_vs_actual_expectancy": round(
            (sum(t.pnl for t in closed) / len(closed) if closed else 0.0) - float(actual.get("actual_expectancy") or 0.0),
            4,
        ),
        "earlier_exit_count_vs_actual": earlier,
        "later_exit_count_vs_actual": later,
        "same_day_exit_count": same,
        "avoided_actual_losses": avoided,
        "reduced_actual_winners": reduced_winners,
        "enlarged_actual_winners": enlarged_winners,
        "note": "Counterfactual deltas are research-only; not guaranteed realizable profit.",
    }


def write_forward_observations(trades_by_arm: dict[str, list[TradeResult]], path: Path = FORWARD_OBS_CSV) -> Path:
    rows = []
    generated = _now()
    for arm, trades in trades_by_arm.items():
        for t in trades:
            rows.append({
                "observation_id": f"{t.decision_id}-{arm}",
                "decision_id": t.decision_id,
                "ticker": t.ticker,
                "region": t.region,
                "strategy_arm": arm,
                "entry_timestamp": t.entry_timestamp,
                "entry_price": t.entry_price,
                "entry_atr14": None,
                "entry_atr_pct": t.entry_atr_pct,
                "entry_ema20": None,
                "entry_ema50": None,
                "entry_trend_state": t.entry_trend,
                "highest_price": None,
                "lowest_price": None,
                "trailing_active": t.trailing_active_at_exit,
                "trailing_stop": None,
                "simulated_exit_timestamp": t.exit_timestamp,
                "simulated_exit_price": t.exit_price,
                "simulated_exit_reason": t.exit_reason,
                "simulated_pnl": t.pnl,
                "simulated_pnl_pct": t.pnl_pct,
                "MFE": t.mfe_pct,
                "MAE": t.mae_pct,
                "bars_held": t.bars_held,
                "status": t.status,
                "data_quality": t.data_quality,
                "generated_at": generated,
            })
    cols = list(rows[0].keys()) if rows else [
        "observation_id", "decision_id", "ticker", "region", "strategy_arm",
        "entry_timestamp", "entry_price", "entry_atr14", "entry_atr_pct",
        "entry_ema20", "entry_ema50", "entry_trend_state", "highest_price",
        "lowest_price", "trailing_active", "trailing_stop",
        "simulated_exit_timestamp", "simulated_exit_price", "simulated_exit_reason",
        "simulated_pnl", "simulated_pnl_pct", "MFE", "MAE", "bars_held",
        "status", "data_quality", "generated_at",
    ]
    pd.DataFrame(rows, columns=cols).to_csv(path, index=False)
    return path
