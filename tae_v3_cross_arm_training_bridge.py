#!/usr/bin/env python3
"""
Bridges V1/V2's own realized closed-trade outcomes into V3's training pool.

Context (2026-09-09): tae_strategy_v3_learning_policy.LearningScorer trains
exclusively from runtime_outputs/longitudinal_memory/decisions.jsonl, which
is fed only by the canonical live_bot.py pipeline (tae_paper_decision_engine.py)
-- never by the V1/V2/V3 parallel-paper arms. That file has only 11 resolved
SELL_PAPER outcomes system-wide, far below the 15-sample fit threshold in
LearningScorer.fit(), so V3's exit-side model (SELL_PAPER/PROTECT_PAPER)
never actually fits -- it falls back to a thin, noisy base rate forever.

Meanwhile V1 (52 closed SELLs) and V2 (68 closed CLOSEs), both with real,
already-realized PnL, sit completely unused by V3's learning. This module
converts them into the same record shape tae_strategy_v3_learning_policy.
load_training_data() expects, so pooling them is a couple of lines at the
call site.

Non-circularity: the label is `expected_profit_delta` set to the ACTUAL
realized PnL of the closed trade (sign only matters to _label_from_expected_delta),
not a forecast made at decision time. This is real ground truth, not a
proxy for it.

Feature-fidelity caveat (kept honest, not hidden): V1/V2's own journals
don't carry the canonical pipeline's enriched decision-time context
(capital_efficiency, horizon_alignment_score, market_regime,
volatility_regime) -- those fields default to neutral/absent on bridged
rows, exactly as they would for any record missing them. Only
`growth_score` has a real analog (V1/V2's own 0-100 technical `score`
field from the same live_bot.py-style signal family) -- though its
distribution differs from the canonical pipeline's growth_score (V1/V2's
mean ~74 vs canonical's mean ~11, because V1/V2 only log `score` for
already-selected trade candidates while canonical logs it for the whole
scored universe including rejects). So bridged rows mainly inform the
model's overall base rate / intercept for exit actions -- exactly what's
needed to escape the n<15 base-rate-only fallback -- rather than
delivering full per-feature learning on par with canonical rows.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

ARM_JOURNAL_ROOTS: dict[str, Path] = {
    "v1": Path("runtime_outputs/parallel_paper/v1/journals"),
    "v2": Path("runtime_outputs/parallel_paper/v2/journals"),
}

BRIDGED_ACTION = "SELL_PAPER"
DEFAULT_GROWTH_SCORE = 50.0


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _decision_scores_by_id(decisions_path: Path) -> dict[str, float]:
    out: dict[str, float] = {}
    for d in _read_jsonl(decisions_path):
        did = d.get("decision_id")
        score = d.get("score")
        if did and score is not None:
            try:
                out[str(did)] = float(score)
            except (TypeError, ValueError):
                continue
    return out


def _v1_realized_pnls(trades: list[dict[str, Any]]) -> list[tuple[dict[str, Any], float]]:
    """Weighted-average-cost reconstruction: V1's SELL trade records carry
    no realized_pnl field directly (unlike V2's CLOSE records, which do)."""
    pos_cost: dict[str, list[float]] = {}
    out: list[tuple[dict[str, Any], float]] = []
    for d in trades:
        ticker = d.get("ticker")
        if not ticker:
            continue
        action = d.get("action")
        try:
            shares = float(d.get("shares") or 0.0)
            price = float(d.get("price") or 0.0)
        except (TypeError, ValueError):
            continue
        if action == "BUY":
            held = pos_cost.setdefault(ticker, [0.0, 0.0])
            held[0] += shares
            held[1] += shares * price
        elif action == "SELL":
            held = pos_cost.get(ticker, [0.0, 0.0])
            avg_cost = held[1] / held[0] if held[0] > 0 else price
            sell_shares = min(shares, held[0]) if held[0] > 0 else shares
            pnl = (price - avg_cost) * sell_shares
            out.append((d, pnl))
            if held[0] > 0:
                remaining = max(held[0] - sell_shares, 0.0)
                held[0] = remaining
                held[1] = avg_cost * remaining
    return out


def bridged_training_records(arm: str) -> Iterator[dict[str, Any]]:
    """Yields records shaped like tae_strategy_v3_learning_policy.
    load_training_data() expects. Action is always SELL_PAPER -- the
    closest true analog to a V1/V2 exit decision; V1/V2 have no separate
    "protect" action to map onto PROTECT_PAPER, so that bucket is left
    untouched rather than fabricated."""
    root = ARM_JOURNAL_ROOTS.get(arm)
    if root is None:
        return
    trades = _read_jsonl(root / "trades.jsonl")
    scores = _decision_scores_by_id(root / "decisions.jsonl")

    if arm == "v1":
        for d, pnl in _v1_realized_pnls(trades):
            did = d.get("decision_id")
            score = scores.get(str(did)) if did else None
            yield {
                "action": BRIDGED_ACTION,
                "growth_score": score if score is not None else DEFAULT_GROWTH_SCORE,
                "expected_profit_delta": pnl,
                "_bridge_source": "v1_trades",
            }
    elif arm == "v2":
        for d in trades:
            if d.get("action") != "CLOSE":
                continue
            pnl = d.get("realized_pnl")
            if pnl is None:
                continue
            try:
                pnl = float(pnl)
            except (TypeError, ValueError):
                continue
            did = d.get("decision_id")
            score = scores.get(str(did)) if did else None
            yield {
                "action": BRIDGED_ACTION,
                "growth_score": score if score is not None else DEFAULT_GROWTH_SCORE,
                "expected_profit_delta": pnl,
                "_bridge_source": "v2_trades",
            }


V3_JOURNAL_ROOT = Path("runtime_outputs/parallel_paper/v3/journals")


def v3_own_training_records() -> Iterator[dict[str, Any]]:
    """V3 learning from its own realized exits (2026-09-09 addition).

    Distinct from bridged_training_records(): this is V3's own experience,
    not another arm's. Its learning_events.jsonl already carries realized_pnl
    directly (no cost-basis reconstruction needed, unlike V1) and a
    holding_duration_sec field -- which, until today, was ALWAYS None (the
    field existed in the schema but no caller ever passed a computed value
    into record_execution_learning_feedback()). Now that
    tae_parallel_paper_runtime.py's V3 SELL path computes it from
    position_cycle_id, new exits carry a real value; historical ones stay
    None and fall back to _extract_features()'s neutral default, same as
    any other record missing the field.
    """
    for d in _read_jsonl(V3_JOURNAL_ROOT / "learning_events.jsonl"):
        if d.get("event_type") != "EXECUTION_OUTCOME" or d.get("action") != "SELL":
            continue
        pnl = d.get("realized_pnl")
        if pnl is None:
            continue
        try:
            pnl = float(pnl)
        except (TypeError, ValueError):
            continue
        hd_sec = d.get("holding_duration_sec")
        record: dict[str, Any] = {
            "action": BRIDGED_ACTION,
            "growth_score": DEFAULT_GROWTH_SCORE,
            "expected_profit_delta": pnl,
            "_bridge_source": "v3_own_exits",
        }
        if hd_sec is not None:
            try:
                record["holding_duration_hours"] = float(hd_sec) / 3600.0
            except (TypeError, ValueError):
                pass
        yield record


def all_bridged_training_records() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for arm in ARM_JOURNAL_ROOTS:
        out.extend(bridged_training_records(arm))
    out.extend(v3_own_training_records())
    return out
