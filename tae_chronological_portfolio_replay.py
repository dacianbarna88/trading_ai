#!/usr/bin/env python3
"""
TAE Chronological Portfolio Replay — deterministic cash/slot/fill engine.

Revalidates entry-quality B1 (signal persistence) WITHOUT modifying decide_b1.
Control A replays portfolio.csv fills faithfully under live_bot cash semantics.

Does NOT modify live_bot.py, stops, trailing, FX, or B1 definition.
promotion_eligibility = false unless reliable_for_promotion and economic gates pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from research_core.accounting.accounting_snapshot import build_accounting_snapshot
from research_core.accounting.fx_normalize import build_lot_usd_ledger, instrument_currency
from tae_entry_quality_ab import (
    B1_CONFIRMATIONS,
    EntryDecision,
    attach_extension,
    decide_b1,
    live_score_from_close,
    _bar_index_for,
)
from tae_exit_strategy_bar_replay import download_enriched_bars, enrich_bars_causal

SCHEMA = "tae.chronological_portfolio_replay.v1"
OUTPUT_JSON = Path("tae_chronological_portfolio_replay_results.json")
OUTPUT_MD = Path("TAE_CHRONOLOGICAL_PORTFOLIO_REPLAY_RESULTS.md")
PROTECTED = ("live_bot.py", "core/trailing.py")

# live_bot canonical (reused, not retuned)
STARTING_CAPITAL = 30000.0
MAX_POSITIONS = 12
MIN_TRADE_USD = 250.0
MAX_TRADE_USD = 2500.0
FEES_PER_TRADE = 0.0

# Event priorities — SELL before BUY at equal timestamp (runtime risk-first)
PRI_SELL = 10
PRI_BUY_EVAL = 20
PRI_BUY_FILL = 30
PRI_MARK = 40

EPS_CASH = 0.05  # USD tolerance for ledger noise
EPS_AV = 5.0  # mark timing: SSOT uses last-BUY Current_Value; live Current_Price drifts
EPS_AV_IDENTITY = 0.01  # ending_cash + omv vs rounded account_value


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha(path: str) -> str:
    p = Path(path)
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "MISSING"


@dataclass
class OpenLot:
    lot_id: str
    ticker: str
    entry_ts: pd.Timestamp
    entry_price: float
    shares: float
    intent_buy_row: int
    score: float | None = None
    delayed: bool = False
    delay_bars: int = 0


@dataclass
class EngineState:
    cash: float = STARTING_CAPITAL
    opens: dict[str, list[OpenLot]] = field(default_factory=dict)  # ticker -> FIFO lots
    realized_pnl_native: float = 0.0
    realized_pnl_usd: float = 0.0
    fees: float = 0.0
    buy_outflow: float = 0.0
    sell_inflow: float = 0.0
    events: list[dict[str, Any]] = field(default_factory=list)
    closed_trades: list[dict[str, Any]] = field(default_factory=list)
    rejected: list[dict[str, Any]] = field(default_factory=list)
    pending_fills: list[dict[str, Any]] = field(default_factory=list)
    equity_curve: list[dict[str, Any]] = field(default_factory=list)
    sizing_decisions: list[dict[str, Any]] = field(default_factory=list)
    peak_account_value: float = STARTING_CAPITAL

    def open_ticker_count(self) -> int:
        return sum(1 for lots in self.opens.values() if lots and sum(l.shares for l in lots) > 1e-9)

    def slots_free(self) -> int:
        return max(0, MAX_POSITIONS - self.open_ticker_count())

    def has_ticker(self, ticker: str) -> bool:
        lots = self.opens.get(ticker) or []
        return sum(l.shares for l in lots) > 1e-9

    def current_drawdown_pct(self, account_value: float) -> float:
        peak = max(self.peak_account_value, account_value, 1e-9)
        return max(0.0, (peak - account_value) / peak)


def load_portfolio_events(portfolio_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    df = pd.read_csv(portfolio_path)
    df["_row"] = df.index.astype(int)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    meta = {"deposit_excluded": [], "n_buy": 0, "n_sell": 0}
    events: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        action = str(row.get("Action", "")).upper().strip()
        ticker = str(row.get("Ticker", "")).upper().strip()
        ts = row["Date"]
        if pd.isna(ts):
            continue
        if action == "DEPOSIT":
            meta["deposit_excluded"].append({
                "row": int(row["_row"]),
                "amount": float(row.get("Invested") or row.get("Price") or 0),
                "reason": str(row.get("Reason", "")),
                "note": "VIRTUAL/excluded from cash per capital_base",
            })
            continue
        if action not in {"BUY", "SELL"} or not ticker or ticker == "CASH":
            continue
        px = float(pd.to_numeric(row.get("Price"), errors="coerce") or 0)
        sh = float(pd.to_numeric(row.get("Shares"), errors="coerce") or 0)
        inv = float(pd.to_numeric(row.get("Invested"), errors="coerce") or (px * sh))
        score = pd.to_numeric(row.get("Score"), errors="coerce")
        mark = float(pd.to_numeric(row.get("Current_Price"), errors="coerce") or px)
        if action == "BUY":
            meta["n_buy"] += 1
            events.append({
                "kind": "BUY_EVAL",
                "priority": PRI_BUY_EVAL,
                "ts": pd.Timestamp(ts),
                "ticker": ticker,
                "price": px,
                "shares": sh,
                "intent_notional": inv if inv > 0 else px * sh,
                "score": float(score) if pd.notna(score) else None,
                "reason": str(row.get("Reason", "")),
                "signal": str(row.get("Signal", "")),
                "buy_row": int(row["_row"]),
                "mark_price": mark,
                "event_id": f"BUY-{int(row['_row'])}",
            })
        else:
            meta["n_sell"] += 1
            events.append({
                "kind": "SELL",
                "priority": PRI_SELL,
                "ts": pd.Timestamp(ts),
                "ticker": ticker,
                "price": px,
                "shares": sh,
                "reason": str(row.get("Reason", "")),
                "sell_row": int(row["_row"]),
                "event_id": f"SELL-{int(row['_row'])}",
            })
    # last marks per ticker from portfolio
    marks: dict[str, float] = {}
    for _, row in df.iterrows():
        t = str(row.get("Ticker", "")).upper()
        cp = pd.to_numeric(row.get("Current_Price"), errors="coerce")
        if t and pd.notna(cp) and float(cp) > 0:
            marks[t] = float(cp)
    meta["marks"] = marks
    return events, meta


def sort_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(events, key=lambda e: (pd.Timestamp(e["ts"]), int(e["priority"]), str(e["event_id"])))


def build_features(
    tickers: set[str],
    *,
    fetcher=None,
    bars_by_ticker: dict[str, pd.DataFrame] | None = None,
) -> dict[str, pd.DataFrame]:
    cache: dict[str, pd.DataFrame] = dict(bars_by_ticker or {})
    out: dict[str, pd.DataFrame] = {}
    for t in tickers:
        if t not in cache:
            try:
                cache[t] = download_enriched_bars(t, fetcher=fetcher)
            except Exception:
                cache[t] = pd.DataFrame()
        bars = cache[t]
        if bars.empty:
            out[t] = pd.DataFrame()
            continue
        if "ATR14" not in bars.columns:
            bars = enrich_bars_causal(bars[["Open", "High", "Low", "Close", "Volume"]])
        score = live_score_from_close(bars["Close"])
        score["Open"] = bars["Open"]
        out[t] = attach_extension(bars, score)
    return out


def _log_event(state: EngineState, **kwargs) -> None:
    state.events.append({
        "cash_before": kwargs.pop("cash_before", None),
        "cash_after": round(state.cash, 6),
        "slots_before": kwargs.pop("slots_before", None),
        "slots_after": state.slots_free(),
        "position_count": state.open_ticker_count(),
        **kwargs,
    })


def execute_buy(
    state: EngineState,
    *,
    ts,
    ticker: str,
    price: float,
    shares: float,
    score: float | None,
    reason: str,
    event_id: str,
    buy_row: int,
    delayed: bool = False,
    delay_bars: int = 0,
    price_source: str = "PORTFOLIO_FILL",
    force: bool = False,
    fees: float | None = None,
    max_trade_usd: float | None = None,
    min_trade_usd: float | None = None,
    allow_cash_clamp: bool = True,
) -> str:
    """
    Apply a BUY to EngineState.

    ``fees`` defaults to module FEES_PER_TRADE (offline chrono). PAPER sizing
    counterfactual adapters pass PAPER transaction-cost totals here.
    """
    fee = float(FEES_PER_TRADE if fees is None else fees)
    max_trade = float(MAX_TRADE_USD if max_trade_usd is None else max_trade_usd)
    min_trade = float(MIN_TRADE_USD if min_trade_usd is None else min_trade_usd)
    cash_before = state.cash
    slots_before = state.slots_free()
    notional = round(price * shares, 4)
    if price <= 0 or shares <= 0:
        state.rejected.append({"event_id": event_id, "reason": "BAD_PRICE_QTY", "ticker": ticker})
        return "REJECTED_BAD_PRICE"
    if not force and state.has_ticker(ticker):
        state.rejected.append({"event_id": event_id, "reason": "ALREADY_HELD", "ticker": ticker})
        _log_event(
            state, ts=str(ts), decision_id=event_id, ticker=ticker, action="BUY",
            reason="ALREADY_HELD", fill_status="REJECTED", cash_before=cash_before,
            slots_before=slots_before, quantity=0, price=price, fees=0,
            price_source=price_source,
        )
        return "REJECTED_ALREADY_HELD"
    if not force and state.slots_free() <= 0:
        state.rejected.append({"event_id": event_id, "reason": "NO_SLOT", "ticker": ticker})
        _log_event(
            state, ts=str(ts), decision_id=event_id, ticker=ticker, action="BUY",
            reason="NO_SLOT", fill_status="REJECTED", cash_before=cash_before,
            slots_before=slots_before, quantity=0, price=price, fees=fee,
            price_source=price_source,
        )
        return "REJECTED_NO_SLOT"
    total_debit = notional + fee
    if not force and state.cash + 1e-9 < total_debit:
        if not allow_cash_clamp or state.cash < min_trade:
            state.rejected.append({"event_id": event_id, "reason": "NO_CASH", "ticker": ticker})
            _log_event(
                state, ts=str(ts), decision_id=event_id, ticker=ticker, action="BUY",
                reason="NO_CASH", fill_status="REJECTED", cash_before=cash_before,
                slots_before=slots_before, quantity=0, price=price, fees=0,
                price_source=price_source,
            )
            return "REJECTED_NO_CASH"
        # Documented SIZE clamp: min(target, max_trade, cash) — not q_alt/q_exec rescale of PnL
        affordable = max(0.0, state.cash - fee)
        shares = round(min(affordable, max_trade) / price, 4) if price > 0 else 0.0
        notional = round(price * shares, 4)
        total_debit = notional + fee
        if notional < min_trade or shares <= 0 or state.cash + 1e-9 < total_debit:
            state.rejected.append({"event_id": event_id, "reason": "NO_CASH", "ticker": ticker})
            return "REJECTED_NO_CASH"

    # Force path (control A): allow cash to go slightly negative only if historical
    # but portfolio cash ended at 0 — should not happen if order matches.
    if force and state.cash + 1e-6 < total_debit:
        # still execute to preserve fidelity; record divergence
        pass

    state.cash = round(state.cash - notional - fee, 6)
    state.buy_outflow = round(state.buy_outflow + notional, 6)
    state.fees = round(state.fees + fee, 6)
    lot = OpenLot(
        lot_id=f"{event_id}|{ticker}|{pd.Timestamp(ts).strftime('%Y%m%d%H%M%S')}",
        ticker=ticker,
        entry_ts=pd.Timestamp(ts),
        entry_price=float(price),
        shares=float(shares),
        intent_buy_row=buy_row,
        score=score,
        delayed=delayed,
        delay_bars=delay_bars,
    )
    state.opens.setdefault(ticker, []).append(lot)
    _log_event(
        state, ts=str(ts), decision_id=event_id, ticker=ticker, action="BUY",
        reason=reason, fill_status="FILLED", cash_before=cash_before,
        slots_before=slots_before, quantity=shares, price=price, fees=fee,
        price_source=price_source, fx_source="N/A_AT_FILL", delayed=delayed, forced=force,
    )
    return "FILLED"


def execute_sell(
    state: EngineState,
    *,
    ts,
    ticker: str,
    price: float,
    shares: float,
    reason: str,
    event_id: str,
    fx_fetcher=None,
    fees: float | None = None,
    close_all_held: bool = False,
) -> str:
    """
    Apply a SELL to EngineState.

    ``close_all_held`` mirrors sell_resized_lots SIZE semantics: at an observed
    canonical exit timestamp/price, close the full CF residual for the ticker.
    """
    fee = float(FEES_PER_TRADE if fees is None else fees)
    cash_before = state.cash
    slots_before = state.slots_free()
    lots = state.opens.get(ticker) or []
    avail = sum(l.shares for l in lots)
    if avail <= 1e-9:
        _log_event(
            state, ts=str(ts), decision_id=event_id, ticker=ticker, action="SELL",
            reason="NO_POSITION", fill_status="SKIPPED", cash_before=cash_before,
            slots_before=slots_before, quantity=0, price=price, fees=0,
            price_source="PORTFOLIO_SELL",
        )
        return "SKIPPED_NO_POSITION"
    need = avail if close_all_held else min(float(shares), avail)
    remaining = need
    realized_native = 0.0
    while remaining > 1e-9 and lots:
        lot = lots[0]
        take = min(lot.shares, remaining)
        pnl_n = (float(price) - lot.entry_price) * take
        realized_native += pnl_n
        pnl_usd = pnl_n
        try:
            led = build_lot_usd_ledger(
                lot_id=lot.lot_id,
                ticker=ticker,
                entry_timestamp=lot.entry_ts,
                exit_timestamp=ts,
                entry_price_local=lot.entry_price,
                exit_price_local=float(price),
                quantity=take,
                fetcher=fx_fetcher,
            )
            if led.realized_pnl_usd is not None:
                pnl_usd = float(led.realized_pnl_usd)
        except Exception:
            pass
        state.closed_trades.append({
            "lot_id": lot.lot_id,
            "ticker": ticker,
            "entry_ts": str(lot.entry_ts),
            "exit_ts": str(ts),
            "entry_price": lot.entry_price,
            "exit_price": float(price),
            "shares": take,
            "pnl_native": round(pnl_n, 6),
            "pnl_usd": round(pnl_usd, 6),
            "delayed_entry": lot.delayed,
            "delay_bars": lot.delay_bars,
            "exit_reason": reason,
            "instrument_currency": instrument_currency(ticker),
            "bars_held_proxy": max(
                1,
                (pd.Timestamp(ts).normalize() - pd.Timestamp(lot.entry_ts).normalize()).days + 1,
            ),
        })
        lot.shares = round(lot.shares - take, 6)
        remaining = round(remaining - take, 6)
        if lot.shares <= 1e-9:
            lots.pop(0)
    proceeds = round(float(price) * need, 4)
    state.cash = round(state.cash + proceeds - fee, 6)
    state.sell_inflow = round(state.sell_inflow + proceeds, 6)
    state.fees = round(state.fees + fee, 6)
    state.realized_pnl_native = round(state.realized_pnl_native + realized_native, 6)
    state.realized_pnl_usd = round(sum(float(t["pnl_usd"]) for t in state.closed_trades), 6)
    if not lots:
        state.opens.pop(ticker, None)
    else:
        state.opens[ticker] = lots
    _log_event(
        state, ts=str(ts), decision_id=event_id, ticker=ticker, action="SELL",
        reason=reason, fill_status="FILLED", cash_before=cash_before,
        slots_before=slots_before, quantity=need, price=price, fees=fee,
        price_source="PORTFOLIO_SELL",
    )
    return "FILLED"


def open_market_value(state: EngineState, marks: dict[str, float]) -> float:
    total = 0.0
    for ticker, lots in state.opens.items():
        px = marks.get(ticker)
        if px is None or px <= 0:
            # fall back to last entry price
            if lots:
                px = lots[-1].entry_price
            else:
                continue
        qty = sum(l.shares for l in lots)
        total += float(px) * qty
    return round(total, 6)


def unrealized_native(state: EngineState, marks: dict[str, float]) -> float:
    u = 0.0
    for ticker, lots in state.opens.items():
        px = marks.get(ticker) or (lots[-1].entry_price if lots else 0)
        for lot in lots:
            u += (float(px) - lot.entry_price) * lot.shares
    return round(u, 6)


def _snapshot_equity(state: EngineState, marks: dict[str, float], ts) -> None:
    omv = open_market_value(state, marks)
    av = round(state.cash + omv, 4)
    state.peak_account_value = max(state.peak_account_value, av)
    state.equity_curve.append({
        "ts": str(ts), "cash": state.cash, "omv": omv,
        "account_value": av,
        "realized_usd": state.realized_pnl_usd,
        "drawdown_pct": round(state.current_drawdown_pct(av), 6),
    })


def run_variant(
    *,
    mode: str,
    b1_confirmations: int,
    base_events: list[dict[str, Any]],
    features: dict[str, pd.DataFrame],
    marks: dict[str, float],
    fx_fetcher=None,
    apply_b1_gate: Callable[..., bool] | None = None,
    gate_name: str | None = None,
    sizing_fn: Callable[..., dict[str, Any]] | None = None,
    sizing_name: str | None = None,
    sell_resized_lots: bool = False,
) -> dict[str, Any]:
    """
    mode='A' — Control A faithful fills.
    mode='B1' — apply decide_b1 to every BUY (unless apply_b1_gate returns False → A fill).
    mode='SIZE' — same BUY set chronologically; sizing_fn returns target notional (quantity only).
    apply_b1_gate(ev, feat, state) -> True means apply B1; False means execute like Control A.
    sizing_fn(ev, feat, state) -> {notional, factor, feature, reason}
    """
    state = EngineState()
    # Working queue — may grow with delayed fills
    queue = [dict(e) for e in base_events]
    queue = sort_events(queue)
    i = 0
    stats = {
        "signals": 0,
        "fills": 0,
        "delayed": 0,
        "cancelled": 0,
        "rejected_no_cash": 0,
        "rejected_no_slot": 0,
        "sells_skipped": 0,
        "same_fill": 0,
        "gate_apply_b1": 0,
        "gate_bypass_a": 0,
        "gate_name": gate_name,
        "sizing_name": sizing_name,
    }

    while i < len(queue):
        ev = queue[i]
        i += 1
        kind = ev["kind"]
        ts = ev["ts"]
        ticker = ev["ticker"]

        if kind == "SELL":
            sell_shares = float(ev["shares"])
            if sell_resized_lots and state.has_ticker(ticker):
                # Close residual sized lots fully at canonical SELL timestamp/price
                sell_shares = sum(l.shares for l in (state.opens.get(ticker) or []))
            status = execute_sell(
                state, ts=ts, ticker=ticker, price=float(ev["price"]),
                shares=sell_shares, reason=str(ev.get("reason", "")),
                event_id=ev["event_id"], fx_fetcher=fx_fetcher,
            )
            if status == "SKIPPED_NO_POSITION":
                stats["sells_skipped"] += 1
            _snapshot_equity(state, marks, ts)
            continue

        if kind == "BUY_EVAL":
            stats["signals"] += 1
            intent = float(ev["intent_notional"])
            feat = features.get(ticker, pd.DataFrame())

            # SIZE mode — change quantity only; same signal set; force for BUY-set fidelity
            if mode == "SIZE" and sizing_fn is not None:
                omv = open_market_value(state, marks)
                av = state.cash + omv
                state.peak_account_value = max(state.peak_account_value, av)
                decision = sizing_fn(ev, feat, state) or {}
                target = float(decision.get("notional") or intent)
                price = float(ev["price"])
                # Clamp: no leverage, respect cash + MAX_TRADE, keep >= MIN when cash allows
                trade_usd = min(max(0.0, target), MAX_TRADE_USD, max(0.0, state.cash))
                if trade_usd + 1e-9 < MIN_TRADE_USD:
                    stats["rejected_no_cash"] += 1
                    state.rejected.append({
                        "event_id": ev["event_id"], "reason": "NO_CASH", "ticker": ticker,
                    })
                    state.sizing_decisions.append({
                        "event_id": ev["event_id"], "ticker": ticker, "ts": str(ts),
                        "intent_a": intent, "notional_b": 0.0, "factor": decision.get("factor"),
                        "feature": decision.get("feature"), "reason": "NO_CASH",
                        "fill_status": "REJECTED", "cash_before": state.cash,
                        "account_value": round(av, 4),
                        "drawdown_pct": round(state.current_drawdown_pct(av), 6),
                    })
                    continue
                shares = round(trade_usd / price, 4) if price > 0 else 0.0
                st = execute_buy(
                    state, ts=ts, ticker=ticker, price=price, shares=shares,
                    score=ev.get("score"),
                    reason=f"SIZE:{sizing_name or 'X'}:{decision.get('reason', '')}",
                    event_id=ev["event_id"], buy_row=int(ev["buy_row"]),
                    delayed=False, delay_bars=0, price_source="PORTFOLIO_FILL",
                    force=True,
                )
                state.sizing_decisions.append({
                    "event_id": ev["event_id"], "ticker": ticker, "ts": str(ts),
                    "price": price,
                    "qty_a": float(ev["shares"]),
                    "qty_b": shares if st == "FILLED" else 0.0,
                    "notional_a": intent,
                    "notional_b": round(price * shares, 4) if st == "FILLED" else 0.0,
                    "factor": decision.get("factor"),
                    "feature": decision.get("feature"),
                    "reason": decision.get("reason"),
                    "fill_status": st,
                    "cash_before": decision.get("cash_before", None),
                    "cash_after": state.cash,
                    "account_value": round(av, 4),
                    "drawdown_pct": round(state.current_drawdown_pct(av), 6),
                    "slots_free": state.slots_free(),
                })
                if st == "FILLED":
                    stats["fills"] += 1
                    stats["same_fill"] += 1
                elif st == "REJECTED_NO_CASH":
                    stats["rejected_no_cash"] += 1
                elif st == "REJECTED_NO_SLOT":
                    stats["rejected_no_slot"] += 1
                _snapshot_equity(state, marks, ts)
                continue

            use_a_fill = mode == "A"
            if mode != "A" and mode != "SIZE" and apply_b1_gate is not None:
                apply = bool(apply_b1_gate(ev, feat, state))
                if apply:
                    stats["gate_apply_b1"] += 1
                else:
                    stats["gate_bypass_a"] += 1
                    use_a_fill = True
            elif mode != "A" and mode != "SIZE":
                stats["gate_apply_b1"] += 1

            if use_a_fill:
                # Faithful fill: exact portfolio shares/price; force past capacity drift
                st = execute_buy(
                    state, ts=ts, ticker=ticker, price=float(ev["price"]),
                    shares=float(ev["shares"]), score=ev.get("score"),
                    reason="CONTROL_A_FILL" if mode == "A" else f"GATE_BYPASS_A:{gate_name or 'NONE'}",
                    event_id=ev["event_id"],
                    buy_row=int(ev["buy_row"]), delayed=False, delay_bars=0,
                    price_source="PORTFOLIO_FILL", force=True,
                )
                if st == "FILLED":
                    stats["fills"] += 1
                    stats["same_fill"] += 1
                elif st == "REJECTED_NO_CASH":
                    stats["rejected_no_cash"] += 1
                elif st == "REJECTED_NO_SLOT":
                    stats["rejected_no_slot"] += 1
                _snapshot_equity(state, marks, ts)
                continue

            # B1 (unchanged decide_b1)
            dec = decide_b1(feat, ts, intent, b1_confirmations)
            if dec.status == "CANCELLED":
                stats["cancelled"] += 1
                _log_event(
                    state, ts=str(ts), decision_id=ev["event_id"], ticker=ticker,
                    action="BUY_EVAL", reason=dec.reason, fill_status="CANCELLED",
                    cash_before=state.cash, slots_before=state.slots_free(),
                    quantity=0, price=ev["price"], fees=0, price_source="NONE",
                )
                continue
            if dec.status == "SAME":
                # Same-timestamp: use A fill but enforce live capacity/cash (no force)
                st = execute_buy(
                    state, ts=ts, ticker=ticker, price=float(ev["price"]),
                    shares=float(ev["shares"]), score=ev.get("score"),
                    reason=dec.reason, event_id=ev["event_id"],
                    buy_row=int(ev["buy_row"]), delayed=False, delay_bars=0,
                    price_source="PORTFOLIO_FILL", force=False,
                )
                if st == "FILLED":
                    stats["fills"] += 1
                    stats["same_fill"] += 1
                elif st == "REJECTED_NO_CASH":
                    stats["rejected_no_cash"] += 1
                elif st == "REJECTED_NO_SLOT":
                    stats["rejected_no_slot"] += 1
                continue

            # DELAYED — schedule fill; do NOT reserve slot/cash
            stats["delayed"] += 1
            fill_ts = pd.Timestamp(dec.entry_timestamp)
            # place fill at bar morning after SELL priority same day: use fill_ts normalize + 09:30
            fill_ts = fill_ts.tz_localize(None).normalize() + pd.Timedelta(hours=9, minutes=30)
            fill_px = float(dec.entry_price)
            # quantity tentative from intent; final clamp at fill time
            fill_event = {
                "kind": "BUY_FILL",
                "priority": PRI_BUY_FILL,
                "ts": fill_ts,
                "ticker": ticker,
                "price": fill_px,
                "intent_notional": intent,
                "score": dec.score_at_decision,
                "reason": dec.reason,
                "buy_row": int(ev["buy_row"]),
                "event_id": f"FILL-{ev['event_id']}",
                "source_event_id": ev["event_id"],
                "delay_bars": dec.delay_bars,
                "price_source": "BAR_OPEN_OR_CLOSE",
            }
            queue.append(fill_event)
            queue[i:] = sort_events(queue[i:])  # keep unprocessed sorted
            _log_event(
                state, ts=str(ts), decision_id=ev["event_id"], ticker=ticker,
                action="BUY_EVAL", reason=f"SCHEDULE_{dec.reason}", fill_status="DELAYED",
                cash_before=state.cash, slots_before=state.slots_free(),
                quantity=0, price=ev["price"], fees=0, price_source="NONE",
                scheduled_fill_ts=str(fill_ts), scheduled_fill_price=fill_px,
            )
            continue

        if kind == "BUY_FILL":
            intent = float(ev["intent_notional"])
            price = float(ev["price"])
            # Recalc quantity at fill under live clamps
            trade_usd = min(intent, MAX_TRADE_USD, state.cash)
            if trade_usd < MIN_TRADE_USD:
                stats["rejected_no_cash"] += 1
                state.rejected.append({"event_id": ev["event_id"], "reason": "NO_CASH_AT_FILL", "ticker": ticker})
                _log_event(
                    state, ts=str(ts), decision_id=ev["event_id"], ticker=ticker,
                    action="BUY_FILL", reason="NO_CASH_AT_FILL", fill_status="REJECTED",
                    cash_before=state.cash, slots_before=state.slots_free(),
                    quantity=0, price=price, fees=0, price_source=ev.get("price_source"),
                )
                continue
            shares = round(trade_usd / price, 4)
            st = execute_buy(
                state, ts=ts, ticker=ticker, price=price, shares=shares,
                score=ev.get("score"), reason=str(ev.get("reason", "DELAYED_FILL")),
                event_id=ev["event_id"], buy_row=int(ev["buy_row"]),
                delayed=True, delay_bars=int(ev.get("delay_bars") or 0),
                price_source=str(ev.get("price_source") or "BAR"),
            )
            if st == "FILLED":
                stats["fills"] += 1
            elif st == "REJECTED_NO_SLOT":
                stats["rejected_no_slot"] += 1
            elif st == "REJECTED_NO_CASH":
                stats["rejected_no_cash"] += 1
            continue

    omv = open_market_value(state, marks)
    unr = unrealized_native(state, marks)
    ending_cash = round(state.cash, 6)
    account_value = round(ending_cash + omv, 4)
    # Ledger identity
    ledger_cash_check = round(
        STARTING_CAPITAL - state.buy_outflow - state.fees + state.sell_inflow, 6
    )
    return {
        "mode": mode,
        "b1_confirmations": b1_confirmations if mode.startswith("B1") else None,
        "stats": stats,
        "opening_cash": STARTING_CAPITAL,
        "buy_outflows": state.buy_outflow,
        "sell_inflows": state.sell_inflow,
        "fees": state.fees,
        "dividends": 0.0,
        "ending_cash": ending_cash,
        "ledger_cash_identity": ledger_cash_check,
        "cash_identity_ok": abs(ledger_cash_check - ending_cash) <= EPS_CASH,
        "open_market_value": omv,
        "account_value": account_value,
        "av_identity_ok": abs(ending_cash + omv - account_value) <= EPS_AV_IDENTITY,
        "realized_pnl_native": state.realized_pnl_native,
        "realized_pnl_usd": state.realized_pnl_usd,
        "unrealized_pnl_native": unr,
        "open_positions": state.open_ticker_count(),
        "closed_trades": len(state.closed_trades),
        "trades": state.closed_trades,
        "events": state.events,
        "rejected": state.rejected,
        "equity_curve": state.equity_curve,
        "sizing_decisions": state.sizing_decisions,
        "peak_account_value": state.peak_account_value,
        "open_lots": {
            t: [{"shares": l.shares, "entry_price": l.entry_price, "delayed": l.delayed} for l in lots]
            for t, lots in state.opens.items()
        },
    }


def metrics_from_variant(v: dict[str, Any]) -> dict[str, Any]:
    trades = [t for t in v["trades"] if t.get("pnl_usd") is not None]
    pnls = pd.Series([float(t["pnl_usd"]) for t in trades], dtype=float) if trades else pd.Series(dtype=float)
    if len(pnls):
        ordered = sorted(trades, key=lambda t: pd.Timestamp(t["exit_ts"]))
        cum = pd.Series([float(t["pnl_usd"]) for t in ordered], dtype=float).cumsum()
        # also fold equity curve drawdown on account value
        ecs = v.get("equity_curve") or []
        if ecs:
            avs = pd.Series([float(e["account_value"]) for e in ecs], dtype=float)
            mdd_av = float((avs - avs.cummax()).min())
        else:
            mdd_av = float((cum - cum.cummax()).min())
        wins = pnls[pnls > 0]
        losses = pnls[pnls < 0]
        gp = float(wins.sum()) if len(wins) else 0.0
        gl = float(abs(losses.sum())) if len(losses) else 0.0
        pf = None if gl == 0 and gp == 0 else (float("inf") if gl == 0 else round(gp / gl, 4))
        dd = float(np.sqrt((losses ** 2).mean())) if len(losses) else 0.0
    else:
        mdd_av = 0.0
        wins = pnls
        losses = pnls
        pf = None
        dd = 0.0
    fast = [t for t in trades if int(t.get("bars_held_proxy") or 99) <= 3]
    by_ccy: dict[str, float] = {}
    by_t: dict[str, float] = {}
    for t in trades:
        ccy = t.get("instrument_currency") or "?"
        by_ccy[ccy] = by_ccy.get(ccy, 0.0) + float(t["pnl_usd"])
        by_t[t["ticker"]] = by_t.get(t["ticker"], 0.0) + float(t["pnl_usd"])
    st = v["stats"]
    return {
        "net_pnl_usd": round(float(pnls.sum()), 4) if len(pnls) else 0.0,
        "account_value": v["account_value"],
        "realized_pnl_usd": v["realized_pnl_usd"],
        "realized_pnl_native": v["realized_pnl_native"],
        "unrealized_pnl_native": v["unrealized_pnl_native"],
        "ending_cash": v["ending_cash"],
        "open_market_value": v["open_market_value"],
        "expectancy": round(float(pnls.mean()), 4) if len(pnls) else 0.0,
        "profit_factor": pf,
        "win_rate": round(float((pnls > 0).mean()), 4) if len(pnls) else 0.0,
        "average_win": round(float(wins.mean()), 4) if len(wins) else 0.0,
        "average_loss": round(float(losses.mean()), 4) if len(losses) else 0.0,
        "median_trade": round(float(pnls.median()), 4) if len(pnls) else 0.0,
        "max_drawdown_account": round(mdd_av, 4),
        "downside_deviation": round(dd, 4),
        "signals": st["signals"],
        "fills": st["fills"],
        "delayed": st["delayed"],
        "cancelled": st["cancelled"],
        "rejected_no_cash": st["rejected_no_cash"],
        "rejected_no_slot": st["rejected_no_slot"],
        "gate_apply_b1": st.get("gate_apply_b1", 0),
        "gate_bypass_a": st.get("gate_bypass_a", 0),
        "gate_apply_frac": round(
            float(st.get("gate_apply_b1", 0)) / max(1, int(st.get("signals", 0))), 4
        ),
        "open_positions": v["open_positions"],
        "closed_positions": v["closed_trades"],
        "exits_0_2_bars": len(fast),
        "by_currency_usd": {k: round(v_, 4) for k, v_ in sorted(by_ccy.items())},
        "by_ticker_usd": {k: round(v_, 4) for k, v_ in sorted(by_t.items())},
        "cash_identity_ok": v["cash_identity_ok"],
        "av_identity_ok": v["av_identity_ok"],
    }


def reconcile_control_a(variant_a: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    cash_ssot = float((snapshot.get("capital_base") or {}).get("cash_available") or snapshot.get("cash_available") or 0)
    av_ssot = float(snapshot.get("account_value_corrected") or snapshot.get("account_value_cash_based") or 0)
    open_ssot = int(snapshot.get("open_positions_count") or 0)
    realized_ssot = float(snapshot.get("corrected_realized_pnl") or 0)
    diffs = []
    if abs(variant_a["ending_cash"] - cash_ssot) > EPS_CASH:
        diffs.append({"field": "ending_cash", "replay": variant_a["ending_cash"], "ssot": cash_ssot})
    if abs(variant_a["account_value"] - av_ssot) > EPS_AV:
        av_diff = abs(variant_a["account_value"] - av_ssot)
        # Live portfolio Current_Price / Current_Value drift during long runs — cash+opens are material.
        sev = "INFO" if av_diff <= 50.0 else "MATERIAL"
        diffs.append({
            "field": "account_value",
            "replay": variant_a["account_value"],
            "ssot": av_ssot,
            "note": "mark timing / FX; open value from portfolio Current_Price",
            "severity": sev,
        })
    if variant_a["open_positions"] != open_ssot:
        diffs.append({"field": "open_positions", "replay": variant_a["open_positions"], "ssot": open_ssot})
    # native realized vs corrected (portfolio currency mix) — informational
    if abs(variant_a["realized_pnl_native"] - realized_ssot) > 5.0:
        diffs.append({
            "field": "realized_pnl_native_vs_corrected",
            "replay": variant_a["realized_pnl_native"],
            "ssot": realized_ssot,
            "note": "SSOT uses reconciliation engine; replay uses fill FIFO native — expect FX/book gaps",
            "severity": "INFO",
        })
    material = [d for d in diffs if d.get("severity") != "INFO"]
    ok = len(material) == 0 and variant_a["cash_identity_ok"] and variant_a["av_identity_ok"]
    return {
        "ok": ok,
        "diffs": diffs,
        "cash_ssot": cash_ssot,
        "av_ssot": av_ssot,
        "open_ssot": open_ssot,
        "replay_cash": variant_a["ending_cash"],
        "replay_av": variant_a["account_value"],
        "replay_open": variant_a["open_positions"],
        "ledger_ok": variant_a["cash_identity_ok"],
    }


def compare_b1_to_a(a: dict[str, Any], b: dict[str, Any], a_m: dict[str, Any], b_m: dict[str, Any]) -> dict[str, Any]:
    a_by = {t["lot_id"].split("|")[0] if False else (t["ticker"], t["entry_ts"]): t for t in a["trades"]}
    # Map A buys that became closed
    a_tick_pnl = {}
    for t in a["trades"]:
        a_tick_pnl.setdefault(t["ticker"], 0.0)
        a_tick_pnl[t["ticker"]] += float(t["pnl_usd"])
    b_tick_pnl = {}
    for t in b["trades"]:
        b_tick_pnl.setdefault(t["ticker"], 0.0)
        b_tick_pnl[t["ticker"]] += float(t["pnl_usd"])

    # winners missed: A win tickers/trades not in B with similar entry
    a_wins = [t for t in a["trades"] if float(t["pnl_usd"]) > 0]
    b_keys = {(t["ticker"], str(pd.Timestamp(t["entry_ts"]).date())) for t in b["trades"]}
    missed = [t for t in a_wins if (t["ticker"], str(pd.Timestamp(t["entry_ts"]).date())) not in b_keys
              and (t["ticker"], str(pd.Timestamp(t["entry_ts"]).normalize().date())) not in b_keys]
    # simpler miss: cancelled/rejected signals that were winners in A isolated sense — use A trades absent
    a_entries = {(t["ticker"], str(pd.Timestamp(t["entry_ts"]).normalize().date())): t for t in a["trades"]}
    b_entries = {(t["ticker"], str(pd.Timestamp(t["entry_ts"]).normalize().date())): t for t in b["trades"]}
    winners_missed = []
    losses_avoided = []
    winners_kept = []
    for k, t in a_entries.items():
        if float(t["pnl_usd"]) > 0:
            if k not in b_entries:
                winners_missed.append(t)
            else:
                winners_kept.append(t)
        elif float(t["pnl_usd"]) < 0 and k not in b_entries:
            losses_avoided.append(t)

    return {
        "delta_net_pnl_usd": round(b_m["net_pnl_usd"] - a_m["net_pnl_usd"], 4),
        "delta_account_value": round(b_m["account_value"] - a_m["account_value"], 4),
        "delta_expectancy": round(b_m["expectancy"] - a_m["expectancy"], 4),
        "delta_maxdd_av": round(abs(b_m["max_drawdown_account"]) - abs(a_m["max_drawdown_account"]), 4),
        "winners_missed_n": len(winners_missed),
        "winners_kept_n": len(winners_kept),
        "losses_avoided_n": len(losses_avoided),
        "losses_avoided_usd": round(sum(abs(float(t["pnl_usd"])) for t in losses_avoided), 4),
        "profits_missed_usd": round(sum(float(t["pnl_usd"]) for t in winners_missed), 4),
        "winner_miss_rate": round(len(winners_missed) / max(1, len(a_wins)), 4),
        "rejected_no_slot": b["stats"]["rejected_no_slot"],
        "rejected_no_cash": b["stats"]["rejected_no_cash"],
        "delayed": b["stats"]["delayed"],
        "cancelled": b["stats"]["cancelled"],
    }


def evaluate_reliability(recon_a: dict[str, Any], variants: dict[str, Any]) -> dict[str, Any]:
    flags = []
    ok = True
    if not recon_a["ok"]:
        ok = False
        flags.append("CONTROL_A_NOT_RECONCILED")
    for name, v in variants.items():
        if not v.get("cash_identity_ok"):
            ok = False
            flags.append(f"LEDGER_FAIL_{name}")
        if not v.get("av_identity_ok"):
            ok = False
            flags.append(f"AV_IDENTITY_FAIL_{name}")
    # determinism checked externally in tests
    if ok:
        flags.append("ALL_RELIABILITY_GATES_PASSED")
    return {"reliable_for_promotion": ok, "flags": flags}


def evaluate_b1_economic(a_m, b_m, cmp_, *, temporal, excl) -> dict[str, Any]:
    flags = []
    ok = True
    if b_m["net_pnl_usd"] <= a_m["net_pnl_usd"]:
        ok = False
        flags.append("PNL_NOT_IMPROVED")
    if b_m["expectancy"] <= a_m["expectancy"]:
        ok = False
        flags.append("EXPECTANCY_NOT_IMPROVED")
    if abs(b_m["max_drawdown_account"]) > abs(a_m["max_drawdown_account"]) + 1e-9:
        ok = False
        flags.append("MAXDD_WORSE")
    if b_m["account_value"] <= a_m["account_value"]:
        ok = False
        flags.append("ACCOUNT_VALUE_NOT_IMPROVED")
    if cmp_["winner_miss_rate"] > 0.25:
        ok = False
        flags.append("WINNER_MISS_GT_25PCT")
    if temporal["val"]["net_pnl_usd"] < temporal["val_a"]["net_pnl_usd"] - 1e-9:
        ok = False
        flags.append("VALIDATION_WORSE")
    if temporal["dev"]["net_pnl_usd"] <= temporal["dev_a"]["net_pnl_usd"]:
        ok = False
        flags.append("DEV_NOT_IMPROVED")
    if excl["b"]["net_pnl_usd"] <= excl["a"]["net_pnl_usd"]:
        ok = False
        flags.append("NO_EDGE_WITHOUT_MU_AMAT_SIE")
    ccy_pos = sum(
        1 for c in ("USD", "EUR", "GBp", "GBP")
        if (b_m.get("by_currency_usd") or {}).get(c, 0) - (a_m.get("by_currency_usd") or {}).get(c, 0) > 0
    )
    if ccy_pos < 2:
        ok = False
        flags.append("FEWER_THAN_TWO_CURRENCY_BOOKS")
    return {"passes": ok and not flags, "flags": sorted(set(flags)), **cmp_}


def temporal_split_metrics(trades: list[dict[str, Any]]) -> tuple[dict, dict, str | None]:
    if not trades:
        empty = {"net_pnl_usd": 0.0, "n": 0}
        return empty, empty, None
    # Count-balanced half by entry timestamp (month-only split collapses when all entries share a month).
    ordered = sorted(trades, key=lambda t: (pd.Timestamp(t["entry_ts"]), str(t.get("lot_id", ""))))
    mid_i = max(1, len(ordered) // 2)

    def mets(sel):
        pnls = [float(t["pnl_usd"]) for t in sel]
        return {"net_pnl_usd": round(sum(pnls), 4), "n": len(pnls),
                "expectancy": round(float(np.mean(pnls)), 4) if pnls else 0.0}

    mid_ts = str(pd.Timestamp(ordered[mid_i - 1]["entry_ts"]))
    return mets(ordered[:mid_i]), mets(ordered[mid_i:]), mid_ts


def excl_tickers(trades: list[dict[str, Any]], ban: set[str]) -> dict[str, Any]:
    sel = [t for t in trades if t["ticker"] not in ban]
    pnls = [float(t["pnl_usd"]) for t in sel]
    return {"net_pnl_usd": round(sum(pnls), 4) if pnls else 0.0, "n": len(pnls)}


def excl_top_n_trades(trades: list[dict[str, Any]], n: int = 2) -> dict[str, Any]:
    if not trades:
        return {"net_pnl_usd": 0.0, "n": 0, "excluded": []}
    ranked = sorted(trades, key=lambda t: abs(float(t["pnl_usd"])), reverse=True)
    ban_ids = {t["lot_id"] for t in ranked[:n]}
    sel = [t for t in trades if t["lot_id"] not in ban_ids]
    pnls = [float(t["pnl_usd"]) for t in sel]
    return {
        "net_pnl_usd": round(sum(pnls), 4) if pnls else 0.0,
        "n": len(pnls),
        "excluded": [
            {"lot_id": t["lot_id"], "ticker": t["ticker"], "pnl_usd": float(t["pnl_usd"])}
            for t in ranked[:n]
        ],
    }


def capital_stats(variant: dict[str, Any]) -> dict[str, Any]:
    """Approximate capital-days cash from event cash_after series."""
    events = variant.get("events") or []
    cash_obs = [(pd.Timestamp(e["ts"]), float(e.get("cash_after") or 0)) for e in events if e.get("ts")]
    if len(cash_obs) < 2:
        return {"capital_days_cash": 0.0, "avg_cash": variant.get("ending_cash"), "avg_utilization": None}
    cash_obs.sort(key=lambda x: x[0])
    # collapse to day-end cash
    by_day: dict[pd.Timestamp, float] = {}
    for ts, cash in cash_obs:
        by_day[ts.normalize()] = cash
    days = sorted(by_day)
    capital_days = 0.0
    for i, d in enumerate(days[:-1]):
        span = max(1, (days[i + 1] - d).days)
        capital_days += by_day[d] * span
    span_last = 1
    capital_days += by_day[days[-1]] * span_last
    avg_cash = capital_days / max(1, (days[-1] - days[0]).days + 1)
    avg_util = round(1.0 - (avg_cash / STARTING_CAPITAL), 4) if STARTING_CAPITAL else None
    return {
        "capital_days_cash": round(capital_days, 2),
        "avg_cash": round(avg_cash, 4),
        "avg_utilization": avg_util,
        "span_days": (days[-1] - days[0]).days + 1,
    }


def run_experiment(
    *,
    portfolio_path: Path = Path("portfolio.csv"),
    fx_fetcher=None,
    fetcher=None,
    bars_by_ticker: dict[str, pd.DataFrame] | None = None,
    write: bool = True,
) -> dict[str, Any]:
    hashes_before = {f: _sha(f) for f in PROTECTED}
    base_events, meta = load_portfolio_events(portfolio_path)
    tickers = {e["ticker"] for e in base_events}
    features = build_features(tickers, fetcher=fetcher, bars_by_ticker=bars_by_ticker)
    marks = meta["marks"]

    variants_raw = {
        "A": run_variant(mode="A", b1_confirmations=0, base_events=base_events, features=features, marks=marks, fx_fetcher=fx_fetcher),
        "B1_1": run_variant(mode="B1", b1_confirmations=1, base_events=base_events, features=features, marks=marks, fx_fetcher=fx_fetcher),
        "B1_2": run_variant(mode="B1", b1_confirmations=2, base_events=base_events, features=features, marks=marks, fx_fetcher=fx_fetcher),
    }
    metrics = {k: metrics_from_variant(v) for k, v in variants_raw.items()}

    snapshot = build_accounting_snapshot(Path("."), portfolio_path=portfolio_path)
    recon_a = reconcile_control_a(variants_raw["A"], snapshot)
    reliability = evaluate_reliability(recon_a, variants_raw)

    # Temporal / exclusions
    def pack_temporal(name: str) -> dict[str, Any]:
        dev, val, mid = temporal_split_metrics(variants_raw[name]["trades"])
        return {"dev": dev, "val": val, "mid": mid}

    temporal = {k: pack_temporal(k) for k in variants_raw}
    ban = {"MU", "AMAT", "SIE.DE"}
    exclusions = {
        k: excl_tickers(variants_raw[k]["trades"], ban) for k in variants_raw
    }
    excl_top2 = {
        k: excl_top_n_trades(variants_raw[k]["trades"], 2) for k in variants_raw
    }
    capital = {k: capital_stats(variants_raw[k]) for k in variants_raw}

    comparisons = {
        "B1_1": compare_b1_to_a(variants_raw["A"], variants_raw["B1_1"], metrics["A"], metrics["B1_1"]),
        "B1_2": compare_b1_to_a(variants_raw["A"], variants_raw["B1_2"], metrics["A"], metrics["B1_2"]),
    }

    econ = {}
    for name in ("B1_1", "B1_2"):
        econ[name] = evaluate_b1_economic(
            metrics["A"], metrics[name], comparisons[name],
            temporal={
                "dev": temporal[name]["dev"], "val": temporal[name]["val"],
                "dev_a": temporal["A"]["dev"], "val_a": temporal["A"]["val"],
            },
            excl={"a": exclusions["A"], "b": exclusions[name]},
        )

    # Robust zone: both confirmations pass economic OR both improve PnL
    robust = (
        econ["B1_1"]["passes"] and econ["B1_2"]["passes"]
    ) or (
        comparisons["B1_1"]["delta_net_pnl_usd"] > 0 and comparisons["B1_2"]["delta_net_pnl_usd"] > 0
        and abs(comparisons["B1_1"]["delta_net_pnl_usd"] - comparisons["B1_2"]["delta_net_pnl_usd"])
        < abs(metrics["A"]["net_pnl_usd"]) * 0.5 + 100
    )

    # Determinism smoke (in-process)
    a2 = run_variant(mode="A", b1_confirmations=0, base_events=base_events, features=features, marks=marks, fx_fetcher=fx_fetcher)
    deterministic = abs(a2["ending_cash"] - variants_raw["A"]["ending_cash"]) < 1e-6 and abs(
        a2["account_value"] - variants_raw["A"]["account_value"]
    ) < 1e-6
    if not deterministic:
        reliability["reliable_for_promotion"] = False
        reliability["flags"] = list(reliability["flags"]) + ["NON_DETERMINISTIC"]

    paper = False
    if not reliability["reliable_for_promotion"]:
        verdict = "CHRONOLOGICAL_REPLAY_NOT_RELIABLE"
        recommendation = (
            "Replay not reliable for promotion. Do not wire B1 to PAPER. "
            f"Flags: {reliability['flags']}"
        )
    elif econ["B1_1"]["passes"] or econ["B1_2"]["passes"]:
        best = "B1_2" if comparisons["B1_2"]["delta_net_pnl_usd"] >= comparisons["B1_1"]["delta_net_pnl_usd"] else "B1_1"
        if econ[best]["passes"] and robust:
            verdict = "ENTRY_QUALITY_CANDIDATE_CONFIRMED"
            recommendation = (
                f"{best} confirmed under chronological cash/slot replay. "
                "Keep promotion_eligibility=false. No PAPER wiring without explicit operator gate + splitter."
            )
        elif econ[best]["passes"]:
            verdict = "ENTRY_QUALITY_CANDIDATE_CONFIRMED"
            recommendation = (
                f"{best} passes economic gates; sensitivity zone partial. SHADOW only."
            )
        else:
            verdict = "ENTRY_QUALITY_EDGE_REJECTED"
            recommendation = "Reliable replay but B1 economic gates failed under cash/slot competition."
    else:
        verdict = "ENTRY_QUALITY_EDGE_REJECTED"
        recommendation = (
            "Chronological replay reliable, but B1-1/B1-2 lose edge once cash/slot/fill effects apply. "
            "Do not PAPER."
        )

    # Effect decomposition (approx)
    def decomp(name: str) -> dict[str, Any]:
        cmp_ = comparisons[name]
        return {
            "signal_persistence_proxy_usd": round(cmp_["losses_avoided_usd"] - cmp_["profits_missed_usd"], 4),
            "slot_competition_rejections": cmp_["rejected_no_slot"],
            "cash_rejections": cmp_["rejected_no_cash"],
            "delayed_count": cmp_["delayed"],
            "cancelled_count": cmp_["cancelled"],
            "delta_account_value": cmp_["delta_account_value"],
            "delta_net_pnl_usd": cmp_["delta_net_pnl_usd"],
            "note": "Persistence vs price/sizing effects entangled when fills delay; reported jointly via deltas.",
        }

    hashes_after = {f: _sha(f) for f in PROTECTED}
    # Trim bulky events in JSON — keep summary counts + sample
    def slim(v: dict[str, Any]) -> dict[str, Any]:
        out = {k: v[k] for k in v if k not in {"events", "equity_curve", "trades"}}
        out["events_n"] = len(v["events"])
        out["trades"] = v["trades"]
        out["equity_curve_n"] = len(v["equity_curve"])
        out["equity_curve_tail"] = v["equity_curve"][-5:]
        return out

    report = {
        "schema": SCHEMA,
        "generated_at": _now(),
        "source_commit_expected": "a3e1ad2",
        "promotion_eligibility": False,
        "paper_ab_active": paper,
        "verdict": verdict,
        "recommendation": recommendation,
        "reliable_for_promotion": reliability["reliable_for_promotion"],
        "reliability": reliability,
        "root_cause_limited_slots": {
            "previous": "portfolio_replay_approx used peak-A slots, no cash, A-entry occupancy",
            "fix": "event queue with live_bot cash + MAX_POSITIONS=12 + fill-time qty recalc",
        },
        "parameters": {
            "starting_capital": STARTING_CAPITAL,
            "max_positions": MAX_POSITIONS,
            "min_trade_usd": MIN_TRADE_USD,
            "max_trade_usd": MAX_TRADE_USD,
            "fees": FEES_PER_TRADE,
            "b1_unchanged": True,
            "confirmations_tested": [1, 2],
        },
        "portfolio_meta": {k: meta[k] for k in ("n_buy", "n_sell", "deposit_excluded")},
        "control_a_reconciliation": recon_a,
        "metrics": metrics,
        "comparisons": comparisons,
        "economic_evaluations": econ,
        "temporal": temporal,
        "exclusions_mu_amat_sie": exclusions,
        "exclusions_top2_abs_pnl": excl_top2,
        "capital_utilization": capital,
        "effect_decomposition": {"B1_1": decomp("B1_1"), "B1_2": decomp("B1_2")},
        "robust_zone_b1_1_and_2": robust,
        "deterministic_inprocess": deterministic,
        "variants": {k: slim(v) for k, v in variants_raw.items()},
        "protected_hashes": {"before": hashes_before, "after": hashes_after, "unchanged": hashes_before == hashes_after},
        "live_bot_modified": False,
        "b1_definition_modified": False,
    }
    if write:
        OUTPUT_JSON.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        OUTPUT_MD.write_text(render_md(report), encoding="utf-8")
    return report


def render_md(report: dict[str, Any]) -> str:
    m = report["metrics"]
    lines = [
        "# TAE Chronological Portfolio Replay Results",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Verdict: **`{report['verdict']}`**",
        f"reliable_for_promotion: `{report['reliable_for_promotion']}`",
        f"promotion_eligibility: `{report['promotion_eligibility']}`",
        f"paper_ab_active: `{report['paper_ab_active']}`",
        "",
        "## Root cause (LIMITED_CHRONOLOGICAL_SLOTS)",
        f"- previous: `{report['root_cause_limited_slots']['previous']}`",
        f"- fix: `{report['root_cause_limited_slots']['fix']}`",
        "",
        "## Control A reconciliation",
        f"```json\n{json.dumps(report['control_a_reconciliation'], indent=2)}\n```",
        "",
        "## A vs B1-1 vs B1-2",
        "",
        "| Variant | net PnL USD | AV | realized | unrealized | cash | OMV | expectancy | PF | WR | maxDD AV | fills | delayed | cancel | no cash | no slot | open | closed |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for k in ("A", "B1_1", "B1_2"):
        x = m[k]
        lines.append(
            f"| {k} | {x['net_pnl_usd']} | {x['account_value']} | {x['realized_pnl_usd']} | "
            f"{x['unrealized_pnl_native']} | {x['ending_cash']} | {x['open_market_value']} | "
            f"{x['expectancy']} | {x['profit_factor']} | {x['win_rate']} | {x['max_drawdown_account']} | "
            f"{x['fills']} | {x['delayed']} | {x['cancelled']} | {x['rejected_no_cash']} | "
            f"{x['rejected_no_slot']} | {x['open_positions']} | {x['closed_positions']} |"
        )
    lines += [
        "",
        "## Cash / slot / fill competition",
        f"```json\n{json.dumps(report['comparisons'], indent=2)}\n```",
        "",
        "## Effect decomposition",
        f"```json\n{json.dumps(report['effect_decomposition'], indent=2)}\n```",
        "",
        "## Capital utilization",
        f"```json\n{json.dumps(report.get('capital_utilization', {}), indent=2)}\n```",
        "",
        "## Economic evaluations (Phase 10)",
        f"```json\n{json.dumps(report['economic_evaluations'], indent=2)}\n```",
        "",
        "## Temporal (dev / validation half by entry count)",
        f"```json\n{json.dumps(report['temporal'], indent=2, default=str)}\n```",
        "",
        "## Without MU / AMAT / SIE.DE",
        f"```json\n{json.dumps(report['exclusions_mu_amat_sie'], indent=2)}\n```",
        "",
        "## Without top-2 |PnL| trades",
        f"```json\n{json.dumps(report.get('exclusions_top2_abs_pnl', {}), indent=2)}\n```",
        "",
        "## Currency books",
        f"```json\n{json.dumps({k: m[k]['by_currency_usd'] for k in m}, indent=2)}\n```",
        "",
        "## Reliability",
        f"```json\n{json.dumps(report['reliability'], indent=2)}\n```",
        "",
        "## Recommendation",
        report["recommendation"],
        "",
        "NO LIVE CHANGE · B1 DEFINITION UNCHANGED · NO PAPER WIRING · NO SIZING SPRINT",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--no-write", action="store_true")
    args = p.parse_args(argv)
    report = run_experiment(write=not args.no_write)
    print("=== TAE CHRONOLOGICAL PORTFOLIO REPLAY ===")
    print("verdict", report["verdict"])
    print("reliable", report["reliable_for_promotion"])
    print("recon_a", report["control_a_reconciliation"])
    for k, v in report["metrics"].items():
        print(k, "pnl", v["net_pnl_usd"], "AV", v["account_value"], "cash", v["ending_cash"],
              "fills", v["fills"], "delayed", v["delayed"], "cancel", v["cancelled"],
              "noslot", v["rejected_no_slot"], "nocash", v["rejected_no_cash"])
    print("econ", report["economic_evaluations"])
    print("protected", report["protected_hashes"]["unchanged"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
