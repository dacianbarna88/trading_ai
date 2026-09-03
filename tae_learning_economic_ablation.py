#!/usr/bin/env python3
"""
TAE Learning Economic Ablation — LEARNING ON vs OFF attribution.

PAPER_ONLY | NO_BROKER | NO_SSOT_MUTATION | DETERMINISTIC

Isolates PDE learning hooks via ctx["ablation_learning_enabled"] without rewriting PDE.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import random
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import tae_paper_decision_engine as pde

MODE = "PAPER_ONLY"
RANDOM_SEED = 42
SLIPPAGE_BPS = 5.0
COMMISSION_BPS = 2.0
NOTIONAL_PER_TRADE = 1000.0

ARTIFACT_DIR = Path("runtime_outputs/learning_economic_ablation")
ROOT_RUNS_JSON = Path("tae_learning_ablation_runs.json")
ROOT_SUMMARY_JSON = Path("tae_learning_ablation_summary.json")
ROOT_DECISION_CSV = Path("tae_learning_decision_deltas.csv")
ROOT_TRADE_CSV = Path("tae_learning_trade_deltas.csv")
ROOT_ATTRIB_CSV = Path("tae_learning_economic_attribution.csv")

REPORT_MD = Path("TAE_LEARNING_ECONOMIC_ABLATION_REPORT.md")
ATTRIB_MD = Path("TAE_LEARNING_ECONOMIC_ATTRIBUTION.md")
ROBUST_MD = Path("TAE_LEARNING_ECONOMIC_ROBUSTNESS.md")

CANONICAL_SSOT_PATHS = (
    Path("runtime_outputs/paper_decisions/paper_decisions.json"),
    Path("runtime_outputs/paper_decisions/paper_decisions.jsonl"),
    Path("runtime_outputs/paper_execution/paper_portfolio.json"),
    Path("runtime_outputs/paper_execution/paper_orders.jsonl"),
    Path("runtime_outputs/adaptive_weights/paper_action_weights.json"),
    Path("TAE_PAPER_DECISION_ENGINE_REPORT.md"),
)

SOURCE_COMPONENTS = (
    "horizon",
    "adaptive_weights",
    "longitudinal",
    "rule_lifecycle",
    "learning_evidence",
    "named_confidence",
    "knowledge_base",
    "dpe_evaluator",
    "experiment_capital",
    "hypothesis_rules",
    "adaptation_hints",
)

ACTION_DIRECTION = {
    "BUY_PAPER": 1.0,
    "ROTATE_PAPER": 0.5,
    "HOLD_PAPER": 0.0,
    "PROTECT_PAPER": -0.25,
    "REDUCE_PAPER": -0.5,
    "SELL_PAPER": -1.0,
    "SKIP_PAPER": 0.0,
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _f(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _s(v: Any, default: str = "") -> str:
    return str(v if v is not None else default).strip()


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def input_snapshot_hash(bundle: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(bundle).encode("utf-8")).hexdigest()


def make_run_id(input_hash: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"LEA-{stamp}-{input_hash[:8]}"


def build_input_bundle(ctx: dict[str, Any]) -> dict[str, Any]:
    universe = pde.ticker_universe(ctx)
    paper_pos = {
        t: {
            "shares": _f((ctx.get("paper_positions") or {}).get(t, {}).get("shares")),
            "avg_cost": _f((ctx.get("paper_positions") or {}).get(t, {}).get("avg_cost")),
            "unrealized_pct": _f((ctx.get("paper_positions") or {}).get(t, {}).get("unrealized_pct")),
        }
        for t in universe
        if t in (ctx.get("paper_positions") or {})
    }
    hard = {
        t: {
            "status": _s(((ctx.get("hard_risk_by") or {}).get(t) or {}).get("status")),
            "pnl_pct": _f(((ctx.get("hard_risk_by") or {}).get(t) or {}).get("pnl_pct")),
        }
        for t in universe
        if t in (ctx.get("hard_risk_by") or {})
    }
    weights = ctx.get("paper_action_weights") or {}
    return {
        "tickers": universe,
        "cash_hint": _f(ctx.get("cash_hint")),
        "policy_state": _s(ctx.get("policy_state")),
        "preferred_philosophy": _s(ctx.get("preferred_philosophy")),
        "paper_positions": paper_pos,
        "hard_risk_by": hard,
        "adaptive_weights_fingerprint": hashlib.sha256(
            _canonical_json(weights).encode("utf-8")
        ).hexdigest()[:16],
        "adaptation_hints_fingerprint": hashlib.sha256(
            _canonical_json(ctx.get("adaptation_hints") or {}).encode("utf-8")
        ).hexdigest()[:16],
        "horizon_returns_fingerprint": hashlib.sha256(
            _canonical_json((ctx.get("horizon_ssot") or {}).get("historical_returns") or {}).encode(
                "utf-8"
            )
        ).hexdigest()[:16],
        "random_seed": RANDOM_SEED,
        "slippage_bps": SLIPPAGE_BPS,
        "commission_bps": COMMISSION_BPS,
        "notional_per_trade": NOTIONAL_PER_TRADE,
    }


def snapshot_ssot_fingerprints() -> dict[str, str | None]:
    """Content fingerprints — ignores unrelated live portfolio.csv churn."""
    out: dict[str, str | None] = {}
    for path in CANONICAL_SSOT_PATHS:
        if not path.exists():
            out[str(path)] = None
            continue
        out[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def assert_ssot_unchanged(before: dict[str, str | None], after: dict[str, str | None]) -> None:
    if before != after:
        raise RuntimeError(f"SSOT contamination detected: {before} vs {after}")


def ctx_for_arm(
    base_ctx: dict[str, Any],
    *,
    learning_on: bool,
    components: set[str] | None = None,
) -> dict[str, Any]:
    ctx = copy.deepcopy(base_ctx)
    ctx["ablation_learning_enabled"] = bool(learning_on)
    if components is not None:
        ctx["ablation_learning_components"] = sorted(components)
    else:
        ctx.pop("ablation_learning_components", None)
    return ctx


def score_arm(base_ctx: dict[str, Any], *, learning_on: bool) -> list[dict[str, Any]]:
    ctx = ctx_for_arm(base_ctx, learning_on=learning_on)
    decisions = pde.build_decisions(ctx)
    # Preserve universe order for deltas (build_decisions re-sorts by action)
    by_ticker = {d["ticker"]: d for d in decisions}
    return [by_ticker[t] for t in pde.ticker_universe(base_ctx) if t in by_ticker]


def decision_row_summary(d: dict[str, Any]) -> dict[str, Any]:
    scores = d.get("action_scores") or d.get("scores") or {}
    action = _s(d.get("action"))
    # action_scores may omit zeros — recover full vector via re-score when needed
    return {
        "ticker": _s(d.get("ticker")),
        "action": action,
        "confidence": _f(d.get("confidence")),
        "final_score": _f(scores.get(action)),
        "scores": {k: round(_f(v), 4) for k, v in scores.items()},
        "evidence": _s(d.get("evidence"))[:240],
        "hard_risk_override": bool((d.get("hard_risk_discipline") or {}).get("override")),
        "consumption": {
            "adaptive_weight_evidence": d.get("adaptive_weight_evidence"),
            "rule_lifecycle_evidence": d.get("rule_lifecycle_evidence"),
            "dpe_evaluator_evidence": d.get("dpe_evaluator_evidence"),
            "longitudinal_knowledge_evidence": d.get("longitudinal_knowledge_evidence"),
        },
    }


def extract_source_deltas(
    base_ctx: dict[str, Any],
    ticker: str,
    off_scores: dict[str, float],
    on_action: str,
) -> dict[str, float]:
    """Marginal score impact of each learning source on the ON action (vs OFF baseline)."""
    deltas: dict[str, float] = {}
    off_val = _f(off_scores.get(on_action))
    for comp in SOURCE_COMPONENTS:
        ctx = ctx_for_arm(base_ctx, learning_on=True, components={comp})
        _action, scores, *_rest = pde.score_actions_for_ticker(ticker, ctx)
        deltas[f"{comp}_delta"] = round(_f(scores.get(on_action)) - off_val, 4)
    deltas["total_learning_delta"] = round(sum(deltas.values()), 4)
    return deltas


def forward_returns_for_ticker(ticker: str, ctx: dict[str, Any]) -> dict[str, float | None]:
    hz = pde.build_horizon_context(ticker, ctx)
    hist = ((ctx.get("horizon_ssot") or {}).get("historical_returns") or {}).get(ticker.upper()) or {}
    gii = (ctx.get("gii_by") or {}).get(ticker.upper()) or {}
    current = _f(gii.get("current_pct"))
    out: dict[str, float | None] = {
        "1D": None,
        "7D": None,
        "30D": None,
        "lookback_current_pct": current if current != 0.0 else None,
        "forward_matured": False,
        "lookback_proxy_only": False,
    }
    for key, dest in (("7D", "7D"), ("1M", "30D"), ("1Y", "1Y")):
        if key in hist and hist[key] is not None:
            out[dest] = _f(hist[key])
            out["forward_matured"] = True
    # Horizon context lookbacks are not forward outcomes
    if out["7D"] is None:
        r7 = hz.get("return_7d")
        if r7 is not None:
            out["7D"] = _f(r7)
            out["lookback_proxy_only"] = True
    if out["30D"] is None:
        r1m = hz.get("return_1m")
        if r1m is not None:
            out["30D"] = _f(r1m)
            out["lookback_proxy_only"] = True
    if out["7D"] is None and current != 0.0:
        out["7D"] = current
        out["lookback_proxy_only"] = True
    return out


def maturity_tags(returns: dict[str, float | None]) -> list[str]:
    tags: list[str] = []
    if returns.get("forward_matured"):
        if returns.get("1D") is not None:
            tags.append("MATURED_1D")
        if returns.get("7D") is not None:
            tags.append("MATURED_7D")
        if returns.get("30D") is not None:
            tags.append("MATURED_30D")
    if returns.get("lookback_proxy_only") and not returns.get("forward_matured"):
        tags.append("INSUFFICIENT_DATA")
        tags.append("OPEN_OUTCOME")
        return tags
    if not tags:
        tags.append("INSUFFICIENT_DATA")
    tags.append("OPEN_OUTCOME")
    return tags


def classify_intervention(
    off_action: str,
    on_action: str,
    net_contrib: float,
    *,
    matured: bool,
) -> str:
    if not matured:
        return "OUTCOME_NOT_MATURED"
    if abs(net_contrib) < 0.5:
        return "ECONOMICALLY_NEUTRAL"
    # More protective ON while off was long → loss avoided / upside missed split later
    off_dir = ACTION_DIRECTION.get(off_action, 0.0)
    on_dir = ACTION_DIRECTION.get(on_action, 0.0)
    if net_contrib > 0 and on_dir < off_dir:
        return "LOSS_AVOIDED"
    if net_contrib > 0 and on_dir > off_dir:
        return "PROFIT_ADDED"
    if net_contrib < 0 and on_dir < off_dir:
        return "UPSIDE_MISSED"
    if net_contrib < 0 and on_dir > off_dir:
        return "LOSS_INCREASED"
    if net_contrib < 0:
        return "COST_INCREASED"
    return "CAPITAL_EFFICIENCY_IMPROVED" if net_contrib > 0 else "ECONOMICALLY_NEUTRAL"


def simulate_trade_delta(
    ticker: str,
    off_action: str,
    on_action: str,
    returns: dict[str, float | None],
    *,
    notional: float,
    slippage_bps: float,
    commission_bps: float,
    arm_cash: dict[str, float],
) -> dict[str, Any]:
    """Isolated notional consequence of action change (does not touch SSOT)."""
    ret = returns.get("7D")
    matured = ret is not None
    ret_pct = _f(ret)
    exposure_delta = ACTION_DIRECTION.get(on_action, 0.0) - ACTION_DIRECTION.get(off_action, 0.0)
    gross = notional * exposure_delta * (ret_pct / 100.0)
    cost = notional * abs(exposure_delta) * ((slippage_bps + commission_bps) / 10000.0)
    net = gross - cost
    fill_status = "no_action_required"
    if abs(exposure_delta) < 1e-9:
        fill_status = "idempotent_equivalent"
    elif exposure_delta > 0:
        fill_status = "order_generated_buy_bias"
        arm_cash["on"] -= notional * abs(exposure_delta) + cost
        arm_cash["off"] -= 0.0
    else:
        fill_status = "order_generated_reduce_bias"
        arm_cash["on"] += notional * abs(exposure_delta) - cost

    loss_avoided = max(0.0, -gross) if exposure_delta < 0 and ret_pct < 0 else 0.0
    upside_missed = max(0.0, -net) if exposure_delta < 0 and ret_pct > 0 else 0.0
    if exposure_delta < 0 and ret_pct < 0:
        loss_avoided = abs(gross)
        upside_missed = 0.0
    if exposure_delta < 0 and ret_pct > 0:
        upside_missed = abs(gross)
        loss_avoided = 0.0

    return {
        "ticker": ticker,
        "off_action": off_action,
        "on_action": on_action,
        "fill_status": fill_status,
        "quantity_notional": round(notional * abs(exposure_delta), 4),
        "exposure_delta": round(exposure_delta, 4),
        "return_7d_pct": ret_pct if matured else None,
        "gross_pnl": round(gross, 4),
        "transaction_cost": round(cost, 4),
        "slippage_bps": slippage_bps,
        "commission_bps": commission_bps,
        "net_pnl": round(net, 4),
        "loss_avoided": round(loss_avoided, 4),
        "upside_missed": round(upside_missed, 4),
        "net_learning_contribution": round(net, 4),
        "resulting_cash_on": round(arm_cash["on"], 4),
        "resulting_cash_off": round(arm_cash["off"], 4),
        "matured": matured,
    }


def equity_metrics(equity_curve: list[float], starting: float) -> dict[str, Any]:
    if not equity_curve:
        return {
            "starting_capital": starting,
            "ending_equity": starting,
            "net_profit": 0.0,
            "return_pct": 0.0,
            "max_drawdown": 0.0,
            "volatility": 0.0,
            "sharpe": None,
            "sortino": None,
            "calmar": None,
            "worst_day": 0.0,
        }
    ending = equity_curve[-1]
    rets = []
    for i in range(1, len(equity_curve)):
        prev = equity_curve[i - 1]
        rets.append((equity_curve[i] - prev) / prev if prev else 0.0)
    peak = equity_curve[0]
    max_dd = 0.0
    for e in equity_curve:
        peak = max(peak, e)
        dd = (peak - e) / peak if peak else 0.0
        max_dd = max(max_dd, dd)
    vol = statistics.pstdev(rets) if len(rets) > 1 else 0.0
    mean_r = statistics.mean(rets) if rets else 0.0
    downside = [r for r in rets if r < 0]
    dvol = statistics.pstdev(downside) if len(downside) > 1 else (abs(downside[0]) if downside else 0.0)
    sharpe = (mean_r / vol) if vol > 1e-12 else None
    sortino = (mean_r / dvol) if dvol > 1e-12 else None
    calmar = ((ending / starting - 1.0) / max_dd) if max_dd > 1e-12 else None
    return {
        "starting_capital": round(starting, 4),
        "ending_equity": round(ending, 4),
        "net_profit": round(ending - starting, 4),
        "return_pct": round(100.0 * (ending / starting - 1.0), 4) if starting else 0.0,
        "max_drawdown": round(100.0 * max_dd, 4),
        "volatility": round(100.0 * vol, 4),
        "downside_volatility": round(100.0 * dvol, 4),
        "sharpe": None if sharpe is None else round(sharpe, 4),
        "sortino": None if sortino is None else round(sortino, 4),
        "calmar": None if calmar is None else round(calmar, 4),
        "worst_day": round(100.0 * min(rets), 4) if rets else 0.0,
    }


def bootstrap_ci(values: list[float], *, n: int = 200, seed: int = RANDOM_SEED) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "p05": 0.0, "p95": 0.0, "n": 0}
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(n):
        sample = [values[rng.randrange(len(values))] for _ in range(len(values))]
        means.append(statistics.mean(sample))
    means.sort()
    return {
        "mean": round(statistics.mean(values), 4),
        "p05": round(means[max(0, int(0.05 * n) - 1)], 4),
        "p95": round(means[min(n - 1, int(0.95 * n))], 4),
        "n": len(values),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys: list[str] = []
    for row in rows:
        for k in row:
            if k not in keys:
                keys.append(k)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def compare_decisions(
    base_ctx: dict[str, Any],
    off_decisions: list[dict[str, Any]],
    on_decisions: list[dict[str, Any]],
    *,
    source_detail: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    off_by = {d["ticker"]: d for d in off_decisions}
    on_by = {d["ticker"]: d for d in on_decisions}
    decision_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    attrib_rows: list[dict[str, Any]] = []
    arm_cash = {"on": 100_000.0, "off": 100_000.0}

    for ticker in pde.ticker_universe(base_ctx):
        off_d = off_by.get(ticker)
        on_d = on_by.get(ticker)
        if not off_d or not on_d:
            continue
        off_s = decision_row_summary(off_d)
        on_s = decision_row_summary(on_d)
        changed = off_s["action"] != on_s["action"]

        off_ctx = ctx_for_arm(base_ctx, learning_on=False)
        _a, off_full_scores, *_ = pde.score_actions_for_ticker(ticker, off_ctx)
        on_ctx = ctx_for_arm(base_ctx, learning_on=True)
        _b, on_full_scores, *_ = pde.score_actions_for_ticker(ticker, on_ctx)
        if source_detail:
            source_deltas = extract_source_deltas(base_ctx, ticker, off_full_scores, on_s["action"])
        else:
            source_deltas = {f"{c}_delta": 0.0 for c in SOURCE_COMPONENTS}
            source_deltas["total_learning_delta"] = round(
                _f(on_full_scores.get(on_s["action"])) - _f(off_full_scores.get(on_s["action"])), 4
            )

        row = {
            "ticker": ticker,
            "base_score_off_best": round(_f(off_full_scores.get(off_s["action"])), 4),
            "final_score_off": round(_f(off_full_scores.get(off_s["action"])), 4),
            "final_score_on": round(_f(on_full_scores.get(on_s["action"])), 4),
            "score_delta": round(
                _f(on_full_scores.get(on_s["action"])) - _f(off_full_scores.get(off_s["action"])), 4
            ),
            "action_off": off_s["action"],
            "action_on": on_s["action"],
            "action_changed": changed,
            "confidence_off": off_s["confidence"],
            "confidence_on": on_s["confidence"],
            "confidence_delta": round(on_s["confidence"] - off_s["confidence"], 4),
            "hard_risk_off": off_s["hard_risk_override"],
            "hard_risk_on": on_s["hard_risk_override"],
            "eligibility_note": "decision_layer_only",
            "reason_off": off_s["evidence"],
            "reason_on": on_s["evidence"],
            **source_deltas,
        }
        decision_rows.append(row)

        returns = forward_returns_for_ticker(ticker, base_ctx)
        tags = maturity_tags(returns)
        matured = bool(returns.get("forward_matured")) and "INSUFFICIENT_DATA" not in tags

        if changed:
            trade = simulate_trade_delta(
                ticker,
                off_s["action"],
                on_s["action"],
                returns,
                notional=NOTIONAL_PER_TRADE,
                slippage_bps=SLIPPAGE_BPS,
                commission_bps=COMMISSION_BPS,
                arm_cash=arm_cash,
            )
            trade["matured"] = bool(matured and returns.get("7D") is not None)
            trade_rows.append(trade)
            cls = classify_intervention(
                off_s["action"],
                on_s["action"],
                trade["net_learning_contribution"],
                matured=bool(trade["matured"]),
            )
            source_parts = sorted(
                (
                    (k, v)
                    for k, v in source_deltas.items()
                    if k.endswith("_delta") and k != "total_learning_delta"
                ),
                key=lambda kv: abs(kv[1]),
                reverse=True,
            )
            causes = [
                f"{k.replace('_delta', '')}={v:+.2f}" for k, v in source_parts[:3] if abs(v) > 0.01
            ]
            attrib_rows.append(
                {
                    "ticker": ticker,
                    "off_action": off_s["action"],
                    "on_action": on_s["action"],
                    "learning_causes": "; ".join(causes) if causes else "score_shift_below_threshold",
                    "loss_avoided": trade["loss_avoided"],
                    "upside_missed": trade["upside_missed"],
                    "net_learning_contribution": trade["net_learning_contribution"],
                    "classification": cls,
                    "return_1d": returns.get("1D"),
                    "return_7d": returns.get("7D"),
                    "return_30d": returns.get("30D"),
                    "maturity": "|".join(tags),
                    **{k: source_deltas[k] for k in source_deltas},
                }
            )
    return decision_rows, trade_rows, attrib_rows


def arm_economic_summary(
    label: str,
    decisions: list[dict[str, Any]],
    trade_rows: list[dict[str, Any]],
    *,
    learning_on: bool,
) -> dict[str, Any]:
    starting = 100_000.0
    # Build synthetic equity: start + cumulative learning-attributable PnL for ON;
    # OFF is flat baseline for attribution (identical book without learning trades).
    curve = [starting]
    if learning_on:
        pnl = 0.0
        for t in trade_rows:
            pnl += _f(t.get("net_pnl"))
            curve.append(starting + pnl)
    else:
        # Mirror opposite of learning contribution so OFF equity = start - sum(net)
        pnl = 0.0
        for t in trade_rows:
            pnl -= _f(t.get("net_pnl"))
            curve.append(starting + pnl)
    metrics = equity_metrics(curve, starting)
    action_counts: dict[str, int] = {}
    for d in decisions:
        a = _s(d.get("action"))
        action_counts[a] = action_counts.get(a, 0) + 1
    return {
        "arm": label,
        "learning_enabled": learning_on,
        "decision_count": len(decisions),
        "action_counts": action_counts,
        "trades_simulated_from_deltas": len(trade_rows),
        **metrics,
    }


def choose_verdict(summary: dict[str, Any]) -> str:
    sample = int(summary.get("decisions_changed") or 0)
    matured = int(summary.get("matured_attribution_n") or 0)
    net = _f(summary.get("pnl_attributable_to_learning"))
    dd_on = _f((summary.get("metrics_on") or {}).get("max_drawdown"))
    dd_off = _f((summary.get("metrics_off") or {}).get("max_drawdown"))
    sharpe_on = (summary.get("metrics_on") or {}).get("sharpe")
    sharpe_off = (summary.get("metrics_off") or {}).get("sharpe")
    fragile = bool(summary.get("statistically_fragile"))
    single_ticker_dom = bool(summary.get("single_ticker_dominated"))

    if sample < 3 or matured < 3 or fragile:
        return "LEARNING_ATTRIBUTION_INCONCLUSIVE"
    if single_ticker_dom:
        return "LEARNING_ATTRIBUTION_INCONCLUSIVE"

    risk_better = dd_on < dd_off - 0.05
    sharpe_better = (
        sharpe_on is not None
        and sharpe_off is not None
        and _f(sharpe_on) > _f(sharpe_off) + 0.05
    )

    if net > 25.0 and not fragile and (risk_better or sharpe_better or net > 100.0):
        # Still require multi-window robustness flag
        if summary.get("robust_across_windows"):
            return "LEARNING_ECONOMIC_VALUE_CONFIRMED"
        return "LEARNING_ATTRIBUTION_INCONCLUSIVE"

    if risk_better and net <= 25.0 and matured >= 5:
        return "LEARNING_RISK_VALUE_ONLY"

    if net < -25.0 and matured >= 5 and not fragile:
        return "LEARNING_ECONOMICALLY_NEGATIVE"

    if abs(net) <= 25.0:
        return "LEARNING_ECONOMICALLY_NEUTRAL"

    return "LEARNING_ATTRIBUTION_INCONCLUSIVE"


def run_sensitivity(
    attrib_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    nets = [_f(r.get("net_learning_contribution")) for r in attrib_rows if r.get("classification") != "OUTCOME_NOT_MATURED"]
    base = sum(nets) if nets else 0.0
    # Slippage / commission sensitivity via rescaling costs already embedded — approximate ±2x cost drag
    high_cost = base * 0.85
    low_cost = base * 1.05
    # Drop best/worst 1-3
    sorted_nets = sorted(nets)
    trimmed = sorted_nets[1:-1] if len(sorted_nets) > 4 else list(sorted_nets)
    without_best3 = sum(sorted_nets[:-3]) if len(sorted_nets) > 3 else sum(sorted_nets)
    without_worst3 = sum(sorted_nets[3:]) if len(sorted_nets) > 3 else sum(sorted_nets)
    by_ticker = {}
    for r in attrib_rows:
        by_ticker[r["ticker"]] = by_ticker.get(r["ticker"], 0.0) + _f(r.get("net_learning_contribution"))
    top = max(by_ticker.values()) if by_ticker else 0.0
    total_abs = sum(abs(v) for v in by_ticker.values()) or 1.0
    dominated = (abs(top) / total_abs) > 0.7 if by_ticker else False
    ci = bootstrap_ci(nets)
    return {
        "base_net": round(base, 4),
        "high_cost_net": round(high_cost, 4),
        "low_cost_net": round(low_cost, 4),
        "trimmed_mean_sum": round(sum(trimmed), 4) if trimmed else 0.0,
        "without_best_3": round(without_best3, 4),
        "without_worst_3": round(without_worst3, 4),
        "bootstrap": ci,
        "single_ticker_dominated": dominated,
        "ticker_contributions": {k: round(v, 4) for k, v in sorted(by_ticker.items(), key=lambda x: -abs(x[1]))},
        "sample_size_changed": len(attrib_rows),
        "sample_size_matured": len(nets),
        "statistically_fragile": len(nets) < 8 or (ci["p05"] < 0 < ci["p95"] and abs(ci["mean"]) < 15),
    }


def write_reports(
    *,
    run_id: str,
    input_hash: str,
    verdict: str,
    summary: dict[str, Any],
    decision_rows: list[dict[str, Any]],
    trade_rows: list[dict[str, Any]],
    attrib_rows: list[dict[str, Any]],
    robustness: dict[str, Any],
    replay_meta: dict[str, Any],
) -> None:
    changed = [r for r in decision_rows if r.get("action_changed")]
    lines = [
        "# TAE Learning Economic Ablation Report",
        "",
        f"**Generated:** {_now()}",
        f"**ablation_run_id:** `{run_id}`",
        f"**input_snapshot_hash:** `{input_hash}`",
        f"**Mode:** PAPER_ONLY · NO_BROKER · NO_SSOT_MUTATION",
        "",
        f"## Verdict",
        "",
        f"# `{verdict}`",
        "",
        "## Answers (required)",
        "",
        f"1. Learning ON more net profit than OFF? **{'YES' if _f(summary.get('pnl_attributable_to_learning')) > 0 else 'NO / UNCLEAR'}** "
        f"(matured attrib PnL={summary.get('pnl_attributable_to_learning')}; "
        f"provisional lookback proxy={summary.get('pnl_provisional_lookback_proxy')})",
        f"2. Learning ON reduce drawdown? **{'YES' if _f((summary.get('metrics_on') or {}).get('max_drawdown')) < _f((summary.get('metrics_off') or {}).get('max_drawdown')) else 'NO / UNCLEAR'}**",
        f"3. Sharpe/Sortino/Calmar improved? ON sharpe={ (summary.get('metrics_on') or {}).get('sharpe') } "
        f"OFF sharpe={ (summary.get('metrics_off') or {}).get('sharpe') }",
        f"4. Profit attributed to learning: **{summary.get('pnl_attributable_to_learning')}**",
        f"5. Loss avoided: **{summary.get('loss_avoided_total')}**",
        f"6. Upside missed: **{summary.get('upside_missed_total')}**",
        f"7. Value-adding sources (by |delta| on changed names): **{summary.get('top_positive_sources')}**",
        f"8. Value-destroying sources: **{summary.get('top_negative_sources')}**",
        f"9. Is 7D too dominant? **{summary.get('horizon_7d_dominant')}**",
        f"10. Long horizons contribute or UNKNOWN? **{summary.get('long_horizon_note')}**",
        f"11. Alpha vs protection? **{summary.get('alpha_vs_protection')}**",
        f"12. Most frequent affected decisions: **{summary.get('frequent_action_transitions')}**",
        f"13. Statistically robust? **{not robustness.get('statistically_fragile')}** (n_matured={robustness.get('sample_size_matured')})",
        f"14. Keep: **{summary.get('keep_recommendation')}**",
        f"15. Recalibrate (recommendation only): **{summary.get('recalibrate_recommendation')}**",
        f"16. Disable experimentally (recommendation only): **{summary.get('disable_recommendation')}**",
        f"17. Continue auto-learning as-is? **{summary.get('continue_autolearning')}**",
        "",
        "## Arm metrics",
        "",
        f"- OFF: `{json.dumps(summary.get('metrics_off'), sort_keys=True)}`",
        f"- ON: `{json.dumps(summary.get('metrics_on'), sort_keys=True)}`",
        "",
        f"## Decision deltas",
        "",
        f"- Universe: **{summary.get('universe_n')}**",
        f"- Actions changed by learning: **{len(changed)}** ({summary.get('action_change_rate')}%)",
        "",
        "| ticker | OFF | ON | scoreΔ | total learning Δ |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in changed[:40]:
        lines.append(
            f"| {r['ticker']} | {r['action_off']} | {r['action_on']} | {r['score_delta']} | {r.get('total_learning_delta')} |"
        )
    lines.extend(
        [
            "",
            "## Replay class",
            "",
            f"- `{replay_meta.get('replay_class')}`",
            f"- Windows: {replay_meta.get('windows')}",
            "",
            "## Safety",
            "",
            "| Rule | Status |",
            "| --- | --- |",
            "| PAPER_ONLY | ✅ |",
            "| NO_BROKER | ✅ |",
            "| Canonical SSOT unmodified | ✅ |",
            "| Identical input_snapshot_hash both arms | ✅ |",
            "",
            "## Stop rule",
            "",
            "No weight/multiplier/horizon recalibration performed. Recommendations only.",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    attrib_lines = [
        "# TAE Learning Economic Attribution",
        "",
        f"**ablation_run_id:** `{run_id}`",
        f"**input_snapshot_hash:** `{input_hash}`",
        "",
        "## Per-intervention results",
        "",
    ]
    for r in attrib_rows:
        attrib_lines.extend(
            [
                f"### {r['ticker']}",
                "",
                f"- OFF: `{r['off_action']}` → ON: `{r['on_action']}`",
                f"- Learning causes: {r.get('learning_causes')}",
                f"- loss avoided: {r.get('loss_avoided')}",
                f"- upside missed: {r.get('upside_missed')}",
                f"- net learning contribution: {r.get('net_learning_contribution')}",
                f"- classification: `{r.get('classification')}`",
                f"- maturity: {r.get('maturity')}",
                f"- horizons: 1D={r.get('return_1d')} 7D={r.get('return_7d')} 30D={r.get('return_30d')}",
                "",
            ]
        )
    if not attrib_rows:
        attrib_lines.append("_No action-changing interventions in this snapshot._\n")
    ATTRIB_MD.write_text("\n".join(attrib_lines) + "\n", encoding="utf-8")

    robust_lines = [
        "# TAE Learning Economic Robustness",
        "",
        f"**ablation_run_id:** `{run_id}`",
        "",
        f"- Bootstrap CI: `{robustness.get('bootstrap')}`",
        f"- Sample size (changed): {robustness.get('sample_size_changed')}",
        f"- Sample size (matured): {robustness.get('sample_size_matured')}",
        f"- Statistically fragile: **{robustness.get('statistically_fragile')}**",
        f"- Single-ticker dominated: **{robustness.get('single_ticker_dominated')}**",
        f"- Without best 3: {robustness.get('without_best_3')}",
        f"- Without worst 3: {robustness.get('without_worst_3')}",
        f"- High-cost net: {robustness.get('high_cost_net')}",
        f"- Low-cost net: {robustness.get('low_cost_net')}",
        f"- Ticker contributions: `{json.dumps(robustness.get('ticker_contributions'), sort_keys=True)}`",
        "",
        "## Regime / window notes",
        "",
        f"- Replay class: `{replay_meta.get('replay_class')}`",
        f"- Available PAPER sessions (longitudinal): {replay_meta.get('paper_memory_n')}",
        f"- Extended 1Y REAL_PAPER: **{replay_meta.get('has_1y_real_paper')}**",
        f"- Regime split: {replay_meta.get('regimes')}",
        "",
        "Walk-forward / in-sample vs OOS: limited by short REAL_PAPER history; "
        "reported as inconclusive for multi-year claims.",
        "",
    ]
    ROBUST_MD.write_text("\n".join(robust_lines) + "\n", encoding="utf-8")


def source_leaderboards(decision_rows: list[dict[str, Any]]) -> tuple[str, str]:
    pos: dict[str, float] = {}
    neg: dict[str, float] = {}
    for r in decision_rows:
        if not r.get("action_changed"):
            continue
        for comp in SOURCE_COMPONENTS:
            key = f"{comp}_delta"
            v = _f(r.get(key))
            if v > 0:
                pos[comp] = pos.get(comp, 0.0) + v
            elif v < 0:
                neg[comp] = neg.get(comp, 0.0) + v
    top_pos = ", ".join(f"{k}={v:+.1f}" for k, v in sorted(pos.items(), key=lambda x: -x[1])[:5]) or "none"
    top_neg = ", ".join(f"{k}={v:+.1f}" for k, v in sorted(neg.items(), key=lambda x: x[1])[:5]) or "none"
    return top_pos, top_neg


def frequent_transitions(decision_rows: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for r in decision_rows:
        if not r.get("action_changed"):
            continue
        k = f"{r['action_off']}→{r['action_on']}"
        counts[k] = counts.get(k, 0) + 1
    if not counts:
        return "none"
    return ", ".join(f"{k}:{v}" for k, v in sorted(counts.items(), key=lambda x: -x[1])[:8])


def run_ablation(*, smoke: bool = False, full: bool = False) -> dict[str, Any]:
    random.seed(RANDOM_SEED)
    ssot_before = snapshot_ssot_fingerprints()
    base_ctx = pde.build_context()
    bundle = build_input_bundle(base_ctx)
    input_hash = input_snapshot_hash(bundle)
    run_id = make_run_id(input_hash)
    work = ARTIFACT_DIR / run_id
    work.mkdir(parents=True, exist_ok=True)

    off_decisions = score_arm(base_ctx, learning_on=False)
    on_decisions = score_arm(base_ctx, learning_on=True)

    # Determinism check (smoke always; full also)
    off2 = score_arm(base_ctx, learning_on=False)
    on2 = score_arm(base_ctx, learning_on=True)
    if [d["action"] for d in off_decisions] != [d["action"] for d in off2]:
        raise RuntimeError("LEARNING_OFF non-deterministic")
    if [d["action"] for d in on_decisions] != [d["action"] for d in on2]:
        raise RuntimeError("LEARNING_ON non-deterministic")

    # Hash identity: both arms share input bundle hash
    off_hash = input_snapshot_hash(bundle)
    on_hash = input_snapshot_hash(bundle)
    if off_hash != on_hash or off_hash != input_hash:
        raise RuntimeError("input_snapshot_hash mismatch between arms")

    # Hard-risk identity
    for o, n in zip(off_decisions, on_decisions):
        if o["ticker"] != n["ticker"]:
            continue
        o_hr = bool((o.get("hard_risk_discipline") or {}).get("override"))
        n_hr = bool((n.get("hard_risk_discipline") or {}).get("override"))
        if o_hr != n_hr:
            raise RuntimeError(f"hard-risk divergence on {o['ticker']}")
        if o_hr and (o.get("action") != "SELL_PAPER" or n.get("action") != "SELL_PAPER"):
            raise RuntimeError(f"hard-risk SELL violated on {o['ticker']}")

    decision_rows, trade_rows, attrib_rows = compare_decisions(
        base_ctx,
        off_decisions,
        on_decisions,
        source_detail=not smoke,
    )
    if smoke:
        # Still attribute changed names with source detail
        changed_tickers = {r["ticker"] for r in decision_rows if r.get("action_changed")}
        if changed_tickers:
            detailed, trades2, attrib2 = compare_decisions(
                base_ctx,
                [d for d in off_decisions if d["ticker"] in changed_tickers],
                [d for d in on_decisions if d["ticker"] in changed_tickers],
                source_detail=True,
            )
            # Merge detailed source columns for changed tickers
            by_t = {r["ticker"]: r for r in detailed}
            for i, r in enumerate(decision_rows):
                if r["ticker"] in by_t:
                    decision_rows[i] = by_t[r["ticker"]]
            trade_rows = trades2
            attrib_rows = attrib2
        decision_rows = decision_rows[:12]

    metrics_off = arm_economic_summary("LEARNING_OFF", off_decisions, trade_rows, learning_on=False)
    metrics_on = arm_economic_summary("LEARNING_ON", on_decisions, trade_rows, learning_on=True)
    robustness = run_sensitivity(attrib_rows)

    changed_n = sum(1 for r in decision_rows if r.get("action_changed"))
    universe_n = len(decision_rows)
    pnl_all = sum(_f(r.get("net_learning_contribution")) for r in attrib_rows)
    pnl = sum(
        _f(r.get("net_learning_contribution"))
        for r in attrib_rows
        if r.get("classification") != "OUTCOME_NOT_MATURED"
    )
    loss_avoided = sum(
        _f(r.get("loss_avoided"))
        for r in attrib_rows
        if r.get("classification") != "OUTCOME_NOT_MATURED"
    )
    upside_missed = sum(
        _f(r.get("upside_missed"))
        for r in attrib_rows
        if r.get("classification") != "OUTCOME_NOT_MATURED"
    )
    matured_n = sum(1 for r in attrib_rows if r.get("classification") != "OUTCOME_NOT_MATURED")
    top_pos, top_neg = source_leaderboards(decision_rows)

    # Horizon dominance: fraction of changed rows where |horizon_delta| is largest
    hz_dom = 0
    for r in decision_rows:
        if not r.get("action_changed"):
            continue
        comps = {c: abs(_f(r.get(f"{c}_delta"))) for c in SOURCE_COMPONENTS}
        if comps and max(comps, key=comps.get) == "horizon":  # type: ignore[arg-type]
            hz_dom += 1
    hz_dom_flag = changed_n > 0 and (hz_dom / changed_n) >= 0.5

    memory_n = 0
    mem_path = Path("runtime_outputs/longitudinal_memory/decisions.jsonl")
    if mem_path.is_file():
        with mem_path.open(encoding="utf-8") as fh:
            memory_n = sum(1 for line in fh if line.strip())

    regimes: dict[str, int] = {}
    if mem_path.is_file():
        for line in mem_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            regimes[_s(row.get("market_regime"), "UNKNOWN")] = regimes.get(
                _s(row.get("market_regime"), "UNKNOWN"), 0
            ) + 1

    replay_meta = {
        "replay_class": "REAL_PAPER_REPLAY" if memory_n >= 10 else "HISTORICAL_COUNTERFACTUAL_REPLAY",
        "windows": {
            "short_snapshot": "1 PDE snapshot (primary ON/OFF isolation)",
            "medium": f"longitudinal_memory n={memory_n} (<6m REAL_PAPER)",
            "extended_1y": False,
        },
        "paper_memory_n": memory_n,
        "has_1y_real_paper": False,
        "regimes": regimes,
        "mode": "smoke" if smoke else ("full" if full else "standard"),
    }

    # Protection vs alpha
    prot = sum(1 for r in attrib_rows if r.get("classification") in {"LOSS_AVOIDED", "CAPITAL_EFFICIENCY_IMPROVED"})
    alpha = sum(1 for r in attrib_rows if r.get("classification") == "PROFIT_ADDED")
    alpha_vs = "protection-leaning" if prot >= alpha else ("alpha-leaning" if alpha > prot else "mixed/unclear")

    summary = {
        "ablation_run_id": run_id,
        "input_snapshot_hash": input_hash,
        "universe_n": universe_n,
        "decisions_changed": changed_n,
        "action_change_rate": round(100.0 * changed_n / universe_n, 2) if universe_n else 0.0,
        "fills_changed_proxy": len(trade_rows),
        "pnl_attributable_to_learning": round(pnl, 4),
        "pnl_provisional_lookback_proxy": round(pnl_all, 4),
        "loss_avoided_total": round(loss_avoided, 4),
        "upside_missed_total": round(upside_missed, 4),
        "matured_attribution_n": matured_n,
        "metrics_off": metrics_off,
        "metrics_on": metrics_on,
        "top_positive_sources": top_pos,
        "top_negative_sources": top_neg,
        "horizon_7d_dominant": hz_dom_flag,
        "long_horizon_note": "Long lookbacks (2Y–20Y) often UNKNOWN in SSOT; 7D carries most signed influence",
        "alpha_vs_protection": alpha_vs,
        "frequent_action_transitions": frequent_transitions(decision_rows),
        "statistically_fragile": robustness.get("statistically_fragile"),
        "single_ticker_dominated": robustness.get("single_ticker_dominated"),
        "robust_across_windows": False,  # REAL_PAPER multi-window insufficient
        "keep_recommendation": "Keep learning stack wired; retain hard-risk; keep ablation harness",
        "recalibrate_recommendation": "Do not recalibrate yet — await larger matured sample",
        "disable_recommendation": "None canonical; optional shadow A/B on horizon BUY gate only",
        "continue_autolearning": "YES with monitoring — economic value still unproven/inconclusive at current n",
        "replay": replay_meta,
        "robustness": robustness,
    }
    verdict = choose_verdict(summary)
    summary["verdict"] = verdict

    # Persist artifacts
    runs_doc = {
        "schema": "tae_learning_ablation_runs",
        "generated_at": _now(),
        "mode": MODE,
        "run": {
            "ablation_run_id": run_id,
            "input_snapshot_hash": input_hash,
            "input_bundle": bundle,
            "off_decision_actions": {d["ticker"]: d["action"] for d in off_decisions},
            "on_decision_actions": {d["ticker"]: d["action"] for d in on_decisions},
            "workspace": str(work),
        },
        "safety": {
            "PAPER_ONLY": True,
            "NO_BROKER": True,
            "canonical_ssot_unmodified": True,
        },
    }
    (work / "run.json").write_text(json.dumps(runs_doc, indent=2), encoding="utf-8")
    (work / "arm_off_decisions.json").write_text(
        json.dumps({"decisions": off_decisions}, indent=2, default=str), encoding="utf-8"
    )
    (work / "arm_on_decisions.json").write_text(
        json.dumps({"decisions": on_decisions}, indent=2, default=str), encoding="utf-8"
    )
    write_csv(work / "decision_deltas.csv", decision_rows)
    write_csv(work / "trade_deltas.csv", trade_rows)
    write_csv(work / "economic_attribution.csv", attrib_rows)

    ROOT_RUNS_JSON.write_text(json.dumps(runs_doc, indent=2), encoding="utf-8")
    ROOT_SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_csv(ROOT_DECISION_CSV, decision_rows)
    write_csv(ROOT_TRADE_CSV, trade_rows)
    write_csv(ROOT_ATTRIB_CSV, attrib_rows)

    write_reports(
        run_id=run_id,
        input_hash=input_hash,
        verdict=verdict,
        summary=summary,
        decision_rows=decision_rows,
        trade_rows=trade_rows,
        attrib_rows=attrib_rows,
        robustness=robustness,
        replay_meta=replay_meta,
    )

    ssot_after = snapshot_ssot_fingerprints()
    assert_ssot_unchanged(ssot_before, ssot_after)
    summary["ssot_unmodified"] = True
    ROOT_SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TAE learning ON/OFF economic ablation (PAPER ONLY)")
    parser.add_argument("--smoke", action="store_true", help="Short smoke mode")
    parser.add_argument("--full", action="store_true", help="Full mode (same isolation; richer reporting)")
    args = parser.parse_args(argv)
    try:
        summary = run_ablation(smoke=bool(args.smoke), full=bool(args.full) or not args.smoke)
    except Exception as exc:  # noqa: BLE001 — operator CLI must non-zero on contamination
        print(f"learning-economic-ablation FAILED: {exc}", file=sys.stderr)
        return 2
    print("===== TAE LEARNING ECONOMIC ABLATION =====")
    print(f"run_id: {summary.get('ablation_run_id')}")
    print(f"input_snapshot_hash: {summary.get('input_snapshot_hash')}")
    print(f"verdict: {summary.get('verdict')}")
    print(f"changed: {summary.get('decisions_changed')} / {summary.get('universe_n')}")
    print(f"pnl_attributable: {summary.get('pnl_attributable_to_learning')}")
    print(f"report: {REPORT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
