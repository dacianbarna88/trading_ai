"""
Execution-realism stress test — roadmap item 7 (2026-09-14): how much
slippage/transaction cost would it take to erase the edge found across
Sprint 2/3's real V1/V2 trades?

Recomputes GROSS pnl (entry/exit fill price × shares, ignoring whatever
transaction-cost assumption was already baked into the real fills) for
every closed V1+V2 trade, then re-applies a range of hypothetical
round-trip cost levels (bps of notional, charged on both entry and exit)
to find where the aggregate edge breaks even. Compares against this
project's actual assumed cost (tae_paper_transaction_costs.py's default:
5 bps slippage per side = 10 bps round-trip, $0 commission).

Analysis-only, no new data source. Run: python3 tae_execution_realism_stress_test.py
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BASE = Path("runtime_outputs/parallel_paper")

# Same sweep spirit as every other backtest this sprint: report the real
# numbers at each level, don't pre-judge which one is "realistic."
COST_LEVELS_BPS_ROUND_TRIP = [0, 5, 10, 20, 30, 50, 75, 100, 150, 200, 300]


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _decision_score_index(decisions: list[dict[str, Any]]) -> dict[str, float]:
    idx: dict[str, float] = {}
    for d in decisions:
        did = d.get("decision_id")
        score = d.get("score")
        if did is not None and score is not None:
            idx[did] = float(score)
    return idx


def collect_v1_gross_trades() -> list[dict[str, Any]]:
    trades = _load_jsonl(BASE / "v1" / "journals" / "trades.jsonl")
    score_by_decision = _decision_score_index(_load_jsonl(BASE / "v1" / "journals" / "decisions.jsonl"))
    open_lots: dict[str, list[dict[str, Any]]] = {}
    closed: list[dict[str, Any]] = []
    for rec in sorted(trades, key=lambda r: r.get("ts", "")):
        ticker = rec.get("ticker")
        action = rec.get("action")
        if action == "BUY":
            open_lots.setdefault(ticker, []).append(rec)
        elif action == "SELL":
            lots = open_lots.get(ticker) or []
            if not lots:
                continue
            buy = lots.pop(0)
            shares = min(buy.get("shares", 0.0), rec.get("shares", 0.0)) or rec.get("shares", 0.0)
            entry_price = float(buy["price"])
            exit_price = float(rec["price"])
            closed.append(
                {
                    "arm": "V1",
                    "ticker": ticker,
                    "shares": shares,
                    "entry_score": score_by_decision.get(buy.get("decision_id")),
                    "entry_notional": entry_price * shares,
                    "exit_notional": exit_price * shares,
                    "gross_pnl": (exit_price - entry_price) * shares,
                }
            )
    return closed


def collect_v2_gross_trades() -> list[dict[str, Any]]:
    trades = _load_jsonl(BASE / "v2" / "journals" / "trades.jsonl")
    score_by_decision = _decision_score_index(_load_jsonl(BASE / "v2" / "journals" / "decisions.jsonl"))
    open_entry_by_ticker: dict[str, dict[str, Any]] = {}
    closed: list[dict[str, Any]] = []
    for rec in sorted(trades, key=lambda r: r.get("ts", "")):
        ticker = rec.get("ticker")
        action = rec.get("action")
        if action == "BUY":
            open_entry_by_ticker.setdefault(ticker, rec)
        elif action in ("ADD", "REBUY"):
            open_entry_by_ticker.setdefault(ticker, rec)
        elif action == "CLOSE":
            entry = open_entry_by_ticker.pop(ticker, None)
            if entry is None or "price" not in entry:
                continue
            shares = float(rec.get("shares", 0.0))
            entry_price = float(entry["price"])
            exit_price = float(rec["price"])
            closed.append(
                {
                    "arm": "V2",
                    "ticker": ticker,
                    "shares": shares,
                    "entry_score": score_by_decision.get(entry.get("decision_id")),
                    "entry_notional": entry_price * shares,
                    "exit_notional": exit_price * shares,
                    "gross_pnl": (exit_price - entry_price) * shares,
                }
            )
    return closed


def _apply_cost(trade: dict[str, Any], round_trip_bps: float) -> float:
    """Cost split evenly across entry+exit notional (half the round-trip
    rate on each leg — same convention as tae_paper_transaction_costs.py
    charging slippage on both BUY and SELL)."""
    half_rate = (round_trip_bps / 2.0) / 10000.0
    cost = trade["entry_notional"] * half_rate + trade["exit_notional"] * half_rate
    return trade["gross_pnl"] - cost


def _report_sweep(label: str, trades: list[dict[str, Any]]) -> None:
    print(f"\n=== {label}: {len(trades)} trades ===")
    if not trades:
        print("  (no trades in this bucket)")
        return
    avg_notional = sum(t["entry_notional"] for t in trades) / len(trades)
    print(f"  Average position notional: ${avg_notional:,.2f}")
    print(f"  {'bps':>6} {'win_rate':>9} {'total_pnl':>12} {'PF':>6}")
    breakeven_bps = None
    for bps in COST_LEVELS_BPS_ROUND_TRIP:
        net_pnls = [_apply_cost(t, bps) for t in trades]
        wins = sum(1 for p in net_pnls if p > 0)
        wr = wins / len(net_pnls) * 100
        total = sum(net_pnls)
        gross_win = sum(p for p in net_pnls if p > 0)
        gross_loss = -sum(p for p in net_pnls if p < 0)
        pf = gross_win / gross_loss if gross_loss > 0 else float("inf")
        print(f"  {bps:>6} {wr:>8.1f}% {total:>11,.2f} {pf:>6.2f}")
        if breakeven_bps is None and total < 0:
            breakeven_bps = bps
    if breakeven_bps is None:
        print("  Stays profitable across the entire tested range (0-300bps).")
    elif breakeven_bps == 0:
        print("  Already net-negative even at ZERO transaction cost -- costs are not the problem here.")
    else:
        print(f"  Crosses zero somewhere at/before {breakeven_bps} bps round-trip.")


def _add_entry_ts(trades: list[dict[str, Any]], score_trades: list[dict[str, Any]]) -> None:
    """Join entry_ts from the score-decile collectors (which already parse
    it) onto our gross-pnl trades, matched by (ticker, arm, order) --
    both lists are built from the same underlying journals in the same
    time order, so positional zip per (arm, ticker) group is exact."""
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for t in score_trades:
        by_key.setdefault((t["arm"], t["ticker"]), []).append(t)
    for t in trades:
        bucket = by_key.get((t["arm"], t["ticker"]))
        if bucket:
            t["entry_ts"] = bucket.pop(0).get("entry_ts")


def main() -> None:
    v1 = collect_v1_gross_trades()
    v2 = collect_v2_gross_trades()
    combined = v1 + v2
    print(f"V1: {len(v1)} closed trades, V2: {len(v2)} closed trades, combined: {len(combined)}")

    _report_sweep("ALL closed trades (unfiltered)", combined)

    validated = [t for t in combined if (t.get("entry_score") or 0) >= 100]
    _report_sweep("Score==100 subset (Sprint 3's first-found edge tier)", validated)

    print("\nFetching VIX/liquidity history to test the compound-filter bucket "
          "(score=100 AND VIX=LOW AND liquidity=HIGH -- the one bucket Sprint 3 "
          "found genuinely profitable, PF 1.19)...")
    try:
        import tae_score_decile_backtest as scoredecile
        import tae_macro_regime_backtest as macro_bt
        import tae_liquidity_backtest as liq_bt
        import tae_liquidity_signal as liq
        import pandas as pd

        score_v1 = scoredecile.collect_v1_closed_trades()
        score_v2 = scoredecile.collect_v2_closed_trades()
        _add_entry_ts(v1, score_v1)
        _add_entry_ts(v2, score_v2)
        combined = v1 + v2

        macro_hist = macro_bt.fetch_macro_history()
        tickers = sorted({t["ticker"] for t in combined})
        vol_hist = liq_bt.fetch_volume_history(tickers)

        compound = []
        for t in combined:
            if (t.get("entry_score") or 0) < 100 or not t.get("entry_ts"):
                continue
            entry_date = pd.Timestamp(t["entry_ts"]).tz_localize(None)
            regime = macro_bt._regime_as_of(macro_hist, entry_date)
            if regime["vix_tercile"] != "LOW":
                continue
            vol = vol_hist.get(t["ticker"])
            if vol is None:
                continue
            window = vol[vol.index <= entry_date]
            if len(window) < liq.AVG_VOLUME_WINDOW + 1:
                continue
            avg_vol = liq.average_volume([float(v) for v in window])
            if avg_vol is None or avg_vol < liq.MIN_AVG_VOLUME:
                continue
            compound.append(t)
        _report_sweep("Compound-filter bucket (score=100 AND VIX=LOW AND liquidity=HIGH)", compound)
    except Exception as exc:
        print(f"  (skipped -- {exc})")

    print("\n=== This project's actual assumed cost today ===")
    try:
        from tae_paper_transaction_costs import DEFAULT_CONFIG

        actual_bps = (
            DEFAULT_CONFIG["PAPER_SLIPPAGE_BPS"] + DEFAULT_CONFIG["PAPER_SPREAD_BPS"] + DEFAULT_CONFIG["PAPER_COMMISSION_BPS"]
        ) * 2  # both legs
        print(f"PAPER_SLIPPAGE_BPS={DEFAULT_CONFIG['PAPER_SLIPPAGE_BPS']} + "
              f"PAPER_SPREAD_BPS={DEFAULT_CONFIG['PAPER_SPREAD_BPS']} + "
              f"PAPER_COMMISSION_BPS={DEFAULT_CONFIG['PAPER_COMMISSION_BPS']} per leg "
              f"= {actual_bps} bps assumed round-trip (plus ${DEFAULT_CONFIG['PAPER_COMMISSION_USD']} flat/fill).")
        net_at_actual = sum(_apply_cost(t, actual_bps) for t in combined)
        print(f"Net PnL at the project's own assumed cost: ${net_at_actual:,.2f}")
    except ImportError:
        print("Could not import tae_paper_transaction_costs for comparison.")


if __name__ == "__main__":
    main()
