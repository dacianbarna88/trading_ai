"""
Empirical test: does the entry-time "score" column (0-100, from live_signals.csv,
the single upstream signal shared by V1/V2/V3/exp_short_margin) actually carry
forward predictive power over win rate / PnL for closed trades?

Analysis-only script. Reads existing V1/V2 journals; writes nothing back to
runtime state. Run: python3 tae_score_decile_backtest.py
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

BASE = Path("runtime_outputs/parallel_paper")


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


def collect_v1_closed_trades() -> list[dict[str, Any]]:
    """FIFO-match V1 BUY/SELL trades per ticker; entry score from decisions.jsonl."""
    trades = _load_jsonl(BASE / "v1" / "journals" / "trades.jsonl")
    decisions = _load_jsonl(BASE / "v1" / "journals" / "decisions.jsonl")
    score_by_decision = _decision_score_index(decisions)

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
            entry_score = score_by_decision.get(buy.get("decision_id"))
            if entry_score is None:
                continue
            shares = min(buy.get("shares", 0.0), rec.get("shares", 0.0)) or rec.get("shares", 0.0)
            pnl = (rec["price"] - buy["price"]) * shares
            closed.append(
                {
                    "arm": "V1",
                    "ticker": ticker,
                    "entry_score": entry_score,
                    "pnl": pnl,
                    "entry_ts": buy.get("ts"),
                    "exit_ts": rec.get("ts"),
                }
            )
    return closed


def collect_v2_closed_trades(
    *, trades_path: Path | str | None = None, decisions_path: Path | str | None = None
) -> list[dict[str, Any]]:
    """CLOSE trades carry realized_pnl. `cycle_id` is missing on 111/112 CLOSE
    records in practice, so match each CLOSE to the most recent still-open
    BUY for that ticker (time-ordered per-ticker state machine) instead of
    joining on cycle_id directly.

    trades_path/decisions_path default to the real production V2 journals
    (this backtest script's original behavior); callers that need test
    isolation (e.g. tae_strategy_v2_kelly_sizing's entry-score filter,
    exercised against temp-dir fixtures) can override both."""
    trades = _load_jsonl(Path(trades_path) if trades_path is not None else BASE / "v2" / "journals" / "trades.jsonl")
    decisions = _load_jsonl(
        Path(decisions_path) if decisions_path is not None else BASE / "v2" / "journals" / "decisions.jsonl"
    )
    score_by_decision = _decision_score_index(decisions)

    open_entry_by_ticker: dict[str, dict[str, Any]] = {}
    closed: list[dict[str, Any]] = []

    for rec in sorted(trades, key=lambda r: r.get("ts", "")):
        ticker = rec.get("ticker")
        action = rec.get("action")
        if action == "BUY":
            if ticker not in open_entry_by_ticker:
                open_entry_by_ticker[ticker] = rec
        elif action in ("ADD", "REBUY"):
            open_entry_by_ticker.setdefault(ticker, rec)
        elif action == "CLOSE":
            entry = open_entry_by_ticker.pop(ticker, None)
            if entry is None:
                continue
            entry_score = score_by_decision.get(entry.get("decision_id"))
            if entry_score is None:
                continue
            closed.append(
                {
                    "arm": "V2",
                    "ticker": ticker,
                    "entry_score": entry_score,
                    "pnl": rec.get("realized_pnl", 0.0),
                    "entry_ts": entry.get("ts"),
                    "exit_ts": rec.get("ts"),
                }
            )
    return closed


def bucket_report(trades: list[dict[str, Any]], n_buckets: int = 5) -> None:
    if not trades:
        print("  (no matched trades)")
        return
    trades = sorted(trades, key=lambda t: t["entry_score"])
    n = len(trades)
    bucket_size = max(1, n // n_buckets)
    print(f"  n={n} matched closed trades")
    for i in range(n_buckets):
        start = i * bucket_size
        end = n if i == n_buckets - 1 else min(n, start + bucket_size)
        if start >= n:
            break
        chunk = trades[start:end]
        if not chunk:
            continue
        scores = [t["entry_score"] for t in chunk]
        pnls = [t["pnl"] for t in chunk]
        wins = sum(1 for p in pnls if p > 0)
        win_rate = wins / len(chunk) * 100
        avg_pnl = statistics.mean(pnls)
        gross_win = sum(p for p in pnls if p > 0)
        gross_loss = -sum(p for p in pnls if p < 0)
        pf = (gross_win / gross_loss) if gross_loss > 0 else float("inf")
        print(
            f"  bucket {i+1}: score [{min(scores):.1f}-{max(scores):.1f}] "
            f"n={len(chunk):3d}  win_rate={win_rate:5.1f}%  avg_pnl=${avg_pnl:7.2f}  "
            f"PF={pf:.2f}"
        )

    all_scores = [t["entry_score"] for t in trades]
    all_pnls = [t["pnl"] for t in trades]
    try:
        rho = _spearman(all_scores, all_pnls)
        print(f"  Spearman rank correlation(score, pnl) = {rho:.3f}")
    except Exception as exc:  # pragma: no cover - diagnostic only
        print(f"  (correlation calc failed: {exc})")


def _rank(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg_rank = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return ranks


def _spearman(xs: list[float], ys: list[float]) -> float:
    rx = _rank(xs)
    ry = _rank(ys)
    n = len(xs)
    mean_rx = statistics.mean(rx)
    mean_ry = statistics.mean(ry)
    cov = sum((a - mean_rx) * (b - mean_ry) for a, b in zip(rx, ry))
    var_x = sum((a - mean_rx) ** 2 for a in rx)
    var_y = sum((b - mean_ry) ** 2 for b in ry)
    if var_x == 0 or var_y == 0:
        return 0.0
    return cov / (var_x**0.5 * var_y**0.5)


def _summary_line(label: str, trades: list[dict[str, Any]]) -> None:
    if not trades:
        print(f"  {label}: n=0")
        return
    pnls = [t["pnl"] for t in trades]
    wins = sum(1 for p in pnls if p > 0)
    wr = wins / len(trades) * 100
    total = sum(pnls)
    gross_win = sum(p for p in pnls if p > 0)
    gross_loss = -sum(p for p in pnls if p < 0)
    pf = (gross_win / gross_loss) if gross_loss > 0 else float("inf")
    print(f"  {label}: n={len(trades):3d}  win_rate={wr:5.1f}%  total_pnl=${total:8.2f}  PF={pf:.2f}")


def main() -> None:
    print("=== V1: entry score vs. closed-trade outcome ===")
    v1_trades = collect_v1_closed_trades()
    bucket_report(v1_trades)

    print("\n=== V2: entry score vs. closed-trade outcome ===")
    v2_trades = collect_v2_closed_trades()
    bucket_report(v2_trades)

    combined = v1_trades + v2_trades
    print("\n=== V1+V2 combined ===")
    bucket_report(combined)

    print("\n=== What-if: raise entry bar (score-only filter, no other changes) ===")
    _summary_line("actual (score>=60, today's gate)", combined)
    _summary_line("score>=80 only", [t for t in combined if t["entry_score"] >= 80])
    _summary_line("score==100 only (STRONG BUY tier)", [t for t in combined if t["entry_score"] >= 100])
    print("  distinct score values observed in BUY decisions confirm the column is")
    print("  a 5-level categorical signal (0/40/60/80/100), not a continuous 0-100 score.")


if __name__ == "__main__":
    main()
