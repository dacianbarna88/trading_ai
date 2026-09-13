"""
Read-only, once-per-day report: how much real diversification exists
across V1/V2/V3/exp_short_margin, versus how much they're just four
slices of one shared score column holding the same names.

Confirmed today (2026-09-12 audit): all four arms decide off the same
`score`/`signal` fields from default_mark_provider() (live_signals.csv),
sliced by different thresholds -- not four independent signals. This
report turns "we suspect correlation" into a measured number: ticker
overlap between arms, and combined-book concentration if all four arms
are treated as one portfolio.

Run: python3 tae_cross_arm_overlap_report.py
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ARMS = ["v1", "v2", "v3", "exp_short_margin"]
BASE = Path("runtime_outputs/parallel_paper")


def _load_portfolio(arm: str) -> dict[str, Any]:
    path = BASE / arm / "portfolio.json"
    if not path.exists():
        return {}
    with path.open() as f:
        return json.load(f)


def _open_positions(portfolio: dict[str, Any]) -> dict[str, dict[str, Any]]:
    positions = portfolio.get("positions") or {}
    return {t: pos for t, pos in positions.items() if abs(_f(pos.get("shares"))) > 0}


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _position_notional(pos: dict[str, Any]) -> float:
    price = _f(pos.get("current_price"), _f(pos.get("last_valid_mark")))
    return abs(_f(pos.get("shares")) * price)


def main() -> None:
    per_arm: dict[str, dict[str, dict[str, Any]]] = {}
    for arm in ARMS:
        per_arm[arm] = _open_positions(_load_portfolio(arm))

    print("=== Cross-arm overlap report ===")
    for arm, positions in per_arm.items():
        print(f"  {arm}: {len(positions)} open positions")

    ticker_to_arms: dict[str, list[str]] = {}
    for arm, positions in per_arm.items():
        for ticker in positions:
            ticker_to_arms.setdefault(ticker, []).append(arm)

    overlapping = {t: arms for t, arms in ticker_to_arms.items() if len(arms) >= 2}
    print(f"\n=== Tickers held by 2+ arms simultaneously: {len(overlapping)} ===")
    for t, arms in sorted(overlapping.items(), key=lambda kv: -len(kv[1])):
        print(f"  {t}: held by {', '.join(arms)}")

    total_unique_tickers = len(ticker_to_arms)
    total_open_slots = sum(len(p) for p in per_arm.values())
    print(f"\n{total_unique_tickers} unique tickers across {total_open_slots} open position-slots "
          f"({total_open_slots - total_unique_tickers} redundant slots on already-held names).")

    print("\n=== Combined-book concentration (all 4 arms as one portfolio) ===")
    combined_notional: dict[str, float] = {}
    for arm, positions in per_arm.items():
        for ticker, pos in positions.items():
            combined_notional[ticker] = combined_notional.get(ticker, 0.0) + _position_notional(pos)
    total_notional = sum(combined_notional.values())
    if total_notional <= 0:
        print("  (no notional data)")
        return
    top = sorted(combined_notional.items(), key=lambda kv: -kv[1])[:10]
    print(f"  total combined notional: ${total_notional:,.2f}")
    for ticker, notional in top:
        pct = notional / total_notional * 100
        arms_holding = ",".join(ticker_to_arms[ticker])
        print(f"  {ticker}: ${notional:,.2f} ({pct:.1f}% of combined book) — {arms_holding}")

    top10_pct = sum(n for _, n in top) / total_notional * 100
    print(f"\n  Top 10 tickers = {top10_pct:.1f}% of the combined book's notional exposure.")


if __name__ == "__main__":
    main()
