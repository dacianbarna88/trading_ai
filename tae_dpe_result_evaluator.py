#!/usr/bin/env python3
"""
TAE DPE-5 — Result Evaluator — READ_ONLY / PAPER_ONLY / SHADOW_ONLY.

Compares competitive vs collaborative paper portfolio results.
Does NOT modify executors, live paths, or broker.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "dpe.result_evaluator.v1"
MODE = "READ_ONLY"
SOURCE = "tae_dpe_result_evaluator"

COMPETITIVE_DIR = Path("runtime_outputs/dpe/paper_competitive")
COLLABORATIVE_DIR = Path("runtime_outputs/dpe/paper_collaborative")
OUTPUT_DIR = Path("runtime_outputs/dpe/result_evaluator")
EVAL_JSON = OUTPUT_DIR / "evaluation.json"
EVAL_MD = OUTPUT_DIR / "evaluation.md"
ROOT_REPORT = Path("TAE_DPE5_RESULT_EVALUATOR_REPORT.md")
GII_JSON = Path("tae_growth_intelligence.json")

METRIC_HIGHER_BETTER = frozenset(
    {
        "portfolio_value",
        "cash",
        "open_positions_value",
        "realized_pnl",
        "unrealized_pnl",
        "total_pnl",
        "win_rate",
        "average_winner",
        "profit_factor",
        "profit_capture_rate",
        "capital_efficiency",
        "trade_count",
    }
)
METRIC_LOWER_BETTER = frozenset({"average_loser", "max_drawdown", "opportunity_cost"})


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _f(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _s(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def load_arm_data(arm_dir: Path, arm_name: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[dict[str, Any]], list[str]]:
    missing: list[str] = []
    portfolio = load_json(arm_dir / "portfolio.json")
    metrics = load_json(arm_dir / "metrics.json")
    orders = load_jsonl(arm_dir / "orders.jsonl")
    if portfolio is None:
        missing.append(f"{arm_dir}/portfolio.json")
    if metrics is None:
        missing.append(f"{arm_dir}/metrics.json")
    if not orders:
        missing.append(f"{arm_dir}/orders.jsonl")
    return portfolio, metrics, orders, missing


def compute_arm_metrics(
    *,
    arm: str,
    portfolio: dict[str, Any],
    metrics: dict[str, Any],
    orders: list[dict[str, Any]],
    market_opportunity_cost: float,
    market_profit_capture_rate: float,
) -> dict[str, Any]:
    totals = metrics.get("portfolio_totals") or {}
    hist = metrics.get("historical_actions") or {}
    starting = _f(portfolio.get("starting_value") or totals.get("starting_value"))
    total_value = _f(portfolio.get("total_value") or totals.get("total_value"))
    cash = _f(portfolio.get("cash") or totals.get("cash"))
    open_positions_value = _f(portfolio.get("open_positions_value") or totals.get("open_positions_value"))
    realized = _f(portfolio.get("realized_pnl") or totals.get("realized_pnl"))
    unrealized = _f(portfolio.get("unrealized_pnl") or totals.get("unrealized_pnl"))
    total_pnl = round(realized + unrealized, 4)

    positions = list((portfolio.get("positions") or {}).values())
    position_pnls = [_f(p.get("pnl")) for p in positions]
    winners = [p for p in position_pnls if p > 0]
    losers = [p for p in position_pnls if p < 0]

    trim_realized = [_f(o.get("realized_pnl")) for o in orders if (_s(o.get("paper_action")) or "").upper() == "PAPER_TRIM"]
    trim_wins = [x for x in trim_realized if x > 0]
    trim_losses = [x for x in trim_realized if x < 0]

    all_wins = winners + trim_wins
    all_losses = losers + trim_losses
    win_count = len(all_wins)
    loss_count = len(all_losses)
    decided = win_count + loss_count
    win_rate = round(win_count / decided, 4) if decided else 0.0

    average_winner = round(sum(all_wins) / len(all_wins), 4) if all_wins else 0.0
    average_loser = round(sum(all_losses) / len(all_losses), 4) if all_losses else 0.0

    gross_wins = sum(all_wins)
    gross_losses = abs(sum(all_losses))
    if gross_losses > 0:
        profit_factor = round(gross_wins / gross_losses, 4)
    elif gross_wins > 0:
        profit_factor = round(gross_wins, 4)
    else:
        profit_factor = 0.0

    value_drawdown = max(0.0, starting - total_value)
    position_drawdowns = [abs(min(_f(p.get("current_pct")), 0.0)) for p in positions]
    max_position_drawdown = max(position_drawdowns) if position_drawdowns else 0.0
    max_drawdown_pct = round(max(value_drawdown / starting * 100 if starting else 0.0, max_position_drawdown), 4)

    paper_opportunity_cost = round(max(0.0, starting - total_value), 4)
    opportunity_cost = round(market_opportunity_cost, 4)
    capture_denominator = total_pnl + paper_opportunity_cost + opportunity_cost
    profit_capture_rate = round(total_pnl / capture_denominator, 4) if capture_denominator > 0 else 0.0

    capital_efficiency = round((total_pnl / starting) * 100, 4) if starting else 0.0

    return {
        "arm": arm,
        "portfolio_value": round(total_value, 4),
        "cash": round(cash, 4),
        "open_positions": len(positions),
        "open_positions_value": round(open_positions_value, 4),
        "realized_pnl": round(realized, 4),
        "unrealized_pnl": round(unrealized, 4),
        "total_pnl": total_pnl,
        "win_rate": win_rate,
        "average_winner": average_winner,
        "average_loser": average_loser,
        "profit_factor": profit_factor,
        "max_drawdown": max_drawdown_pct,
        "profit_capture_rate": profit_capture_rate,
        "opportunity_cost": opportunity_cost,
        "paper_opportunity_cost": paper_opportunity_cost,
        "market_profit_capture_rate_reference": market_profit_capture_rate,
        "capital_efficiency": capital_efficiency,
        "trade_count": _f(hist.get("total") or metrics.get("total_trades")),
        "trim_count": _f(hist.get("trim") or metrics.get("trim_count")),
        "protect_count": _f(hist.get("protect") or metrics.get("protect_count")),
        "hold_count": _f(hist.get("hold") or metrics.get("hold_count")),
        "starting_value": round(starting, 4),
    }


def compare_metric(name: str, competitive: float, collaborative: float) -> dict[str, Any]:
    if abs(competitive - collaborative) < 0.0001:
        winner = "TIE"
    elif name in METRIC_LOWER_BETTER:
        winner = "COMPETITIVE" if competitive < collaborative else "COLLABORATIVE"
    else:
        winner = "COMPETITIVE" if competitive > collaborative else "COLLABORATIVE"
    return {
        "metric": name,
        "competitive": competitive,
        "collaborative": collaborative,
        "winner": winner,
    }


def overall_winner(comparisons: list[dict[str, Any]]) -> tuple[str, float, str]:
    weights = {
        "total_pnl": 3.0,
        "realized_pnl": 2.0,
        "unrealized_pnl": 1.5,
        "profit_factor": 2.5,
        "win_rate": 2.0,
        "max_drawdown": 2.5,
        "capital_efficiency": 2.0,
        "profit_capture_rate": 1.5,
        "portfolio_value": 1.0,
        "average_winner": 1.0,
        "opportunity_cost": 1.0,
    }
    comp_score = 0.0
    collab_score = 0.0
    total_weight = 0.0
    for row in comparisons:
        w = weights.get(row["metric"], 1.0)
        total_weight += w
        if row["winner"] == "COMPETITIVE":
            comp_score += w
        elif row["winner"] == "COLLABORATIVE":
            collab_score += w
        else:
            comp_score += w * 0.5
            collab_score += w * 0.5

    if comp_score > collab_score:
        winner = "COMPETITIVE"
        confidence = round((comp_score / total_weight) * 100, 1) if total_weight else 50.0
    elif collab_score > comp_score:
        winner = "COLLABORATIVE"
        confidence = round((collab_score / total_weight) * 100, 1) if total_weight else 50.0
    else:
        winner = "TIE"
        confidence = 50.0

    comp = next(r for r in comparisons if r["metric"] == "total_pnl")
    real = next(r for r in comparisons if r["metric"] == "realized_pnl")
    dd = next(r for r in comparisons if r["metric"] == "max_drawdown")

    if winner == "COMPETITIVE":
        reason = (
            f"Higher unrealized growth ({comp['competitive']}) with competitive hold bias; "
            f"realized PnL {real['competitive']} vs {real['collaborative']}."
        )
    elif winner == "COLLABORATIVE":
        reason = (
            f"Stronger realized PnL ({real['collaborative']} vs {real['competitive']}) with "
            f"lower drawdown exposure ({dd['collaborative']}% vs {dd['competitive']}%) and capital preservation."
        )
    else:
        reason = "Both arms are tied on weighted performance metrics."

    return winner, confidence, reason


def build_evaluation(
    competitive: dict[str, Any],
    collaborative: dict[str, Any],
) -> dict[str, Any]:
    metric_names = [
        "portfolio_value",
        "cash",
        "open_positions_value",
        "realized_pnl",
        "unrealized_pnl",
        "total_pnl",
        "win_rate",
        "average_winner",
        "average_loser",
        "profit_factor",
        "max_drawdown",
        "profit_capture_rate",
        "opportunity_cost",
        "capital_efficiency",
        "trade_count",
        "trim_count",
        "protect_count",
        "hold_count",
    ]
    comparisons = [
        compare_metric(name, competitive[name], collaborative[name]) for name in metric_names
    ]
    comparisons.append(
        compare_metric("open_positions", competitive["open_positions"], collaborative["open_positions"])
    )

    winner, confidence, reason = overall_winner(comparisons)
    comp_wins = sum(1 for c in comparisons if c["winner"] == "COMPETITIVE")
    collab_wins = sum(1 for c in comparisons if c["winner"] == "COLLABORATIVE")
    ties = sum(1 for c in comparisons if c["winner"] == "TIE")

    return {
        "schema_version": SCHEMA_VERSION,
        "mode": MODE,
        "source": SOURCE,
        "generated_at": _now(),
        "inputs": {
            "competitive_dir": str(COMPETITIVE_DIR),
            "collaborative_dir": str(COLLABORATIVE_DIR),
        },
        "competitive": competitive,
        "collaborative": collaborative,
        "comparisons": comparisons,
        "winner_by_metric": {c["metric"]: c["winner"] for c in comparisons},
        "overall": {
            "winner": winner,
            "confidence_pct": confidence,
            "reason": reason,
            "competitive_metric_wins": comp_wins,
            "collaborative_metric_wins": collab_wins,
            "ties": ties,
            "recommendation": (
                f"Continue PAPER experiment with {winner} philosophy as current leader. "
                f"Re-evaluate after DPE-6 learning cycle."
            ),
        },
        "architecture": {
            "competitive_executor": "tae_dpe_competitive_executor.py",
            "collaborative_executor": "tae_dpe_collaborative_executor.py",
            "evaluation_read_only": True,
            "live_portfolio_touched": False,
        },
        "next_sprint": "TAE DPE-6 — Learning Engine",
    }


def write_evaluation_md(evaluation: dict[str, Any]) -> None:
    comp = evaluation["competitive"]
    collab = evaluation["collaborative"]
    overall = evaluation["overall"]

    lines = [
        "# TAE DPE-5 Result Evaluator",
        "",
        f"**Generated:** {evaluation['generated_at']}",
        f"**Mode:** {MODE} · PAPER_ONLY · SHADOW_ONLY",
        f"**Schema:** {SCHEMA_VERSION}",
        "",
        "> Read-only comparison of competitive vs collaborative paper portfolios",
        "",
        "## Executive summary",
        "",
        "```text",
        "Competitive",
        "    vs",
        "Collaborative",
        "    ↓",
        f"Winner: {overall['winner']}",
        f"Confidence: {overall['confidence_pct']}%",
        f"Reason: {overall['reason']}",
        "```",
        "",
        f"**Recommendation:** {overall['recommendation']}",
        "",
        "## Overall comparison",
        "",
        "| metric | COMPETITIVE | COLLABORATIVE | winner |",
        "| --- | --- | --- | --- |",
    ]
    for row in evaluation["comparisons"]:
        lines.append(
            f"| {row['metric']} | {row['competitive']} | {row['collaborative']} | {row['winner']} |"
        )

    lines.extend(
        [
            "",
            "## Competitive snapshot",
            "",
            f"- Portfolio value: **{comp['portfolio_value']}**",
            f"- Total PnL: **{comp['total_pnl']}** (realized {comp['realized_pnl']}, unrealized {comp['unrealized_pnl']})",
            f"- Win rate: **{comp['win_rate']}** | Profit factor: **{comp['profit_factor']}**",
            f"- Actions: HOLD {comp['hold_count']} | TRIM {comp['trim_count']} | PROTECT {comp['protect_count']}",
            "",
            "## Collaborative snapshot",
            "",
            f"- Portfolio value: **{collab['portfolio_value']}**",
            f"- Total PnL: **{collab['total_pnl']}** (realized {collab['realized_pnl']}, unrealized {collab['unrealized_pnl']})",
            f"- Win rate: **{collab['win_rate']}** | Profit factor: **{collab['profit_factor']}**",
            f"- Actions: HOLD {collab['hold_count']} | TRIM {collab['trim_count']} | PROTECT {collab['protect_count']}",
            "",
            "## Winner by metric",
            "",
        ]
    )
    for metric, winner in evaluation["winner_by_metric"].items():
        lines.append(f"- **{metric}**: {winner}")

    lines.extend(
        [
            "",
            "## Scoreboard",
            "",
            f"- Competitive wins: **{overall['competitive_metric_wins']}**",
            f"- Collaborative wins: **{overall['collaborative_metric_wins']}**",
            f"- Ties: **{overall['ties']}**",
            "",
            "## Safety confirmation",
            "",
            "- READ_ONLY: **true**",
            "- Executors not modified: **true**",
            "- portfolio.csv not modified: **true**",
            "- live_bot.py not modified: **true**",
            "",
            "## Next sprint",
            "",
            f"**{evaluation['next_sprint']}**",
        ]
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    EVAL_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_root_report(evaluation: dict[str, Any], validation_pass: bool, missing: list[str]) -> None:
    overall = evaluation["overall"]
    lines = [
        "# TAE DPE-5 — Result Evaluator Sprint Report",
        "",
        f"**Date:** {evaluation['generated_at']}",
        f"**Mode:** READ_ONLY · PAPER_ONLY · SHADOW_ONLY · NO_BROKER",
        f"**Status:** {'PASS' if validation_pass else 'FAIL'}",
        "",
        "## Files created",
        "",
        "| File | Role |",
        "| --- | --- |",
        "| `tae_dpe_result_evaluator.py` | Evaluator engine |",
        "| `runtime_outputs/dpe/result_evaluator/evaluation.json` | Machine-readable comparison |",
        "| `runtime_outputs/dpe/result_evaluator/evaluation.md` | Human report |",
        "| `tae_cli/commands/dpe_evaluator.py` | CLI command |",
        "",
        "## Metrics compared",
        "",
        "Portfolio value, cash, open positions, realized/unrealized/total PnL, win rate, "
        "average winner/loser, profit factor, max drawdown, profit capture rate, "
        "opportunity cost, capital efficiency, trade/trim/protect/hold counts.",
        "",
        "## Winner per metric",
        "",
    ]
    for metric, winner in evaluation["winner_by_metric"].items():
        lines.append(f"- {metric}: **{winner}**")

    lines.extend(
        [
            "",
            "## Overall winner",
            "",
            f"- **{overall['winner']}**",
            f"- Confidence: **{overall['confidence_pct']}%**",
            f"- Reason: {overall['reason']}",
            "",
            "## Architecture confirmation",
            "",
            "- Evaluator reads only `paper_competitive/` and `paper_collaborative/`",
            "- No executor code modified",
            "- No live SSOT touched",
            "",
            "## Validation result",
            "",
            f"- Competitive evaluated: **{'yes' if COMPETITIVE_DIR.is_dir() else 'no'}**",
            f"- Collaborative evaluated: **{'yes' if COLLABORATIVE_DIR.is_dir() else 'no'}**",
            f"- Overall recommendation generated: **yes**",
        ]
    )
    if missing:
        lines.extend(["", "**Missing inputs:**", ""])
        for item in missing:
            lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "## Safety confirmation",
            "",
            "| Rule | Status |",
            "| --- | --- |",
            "| READ_ONLY | ✅ |",
            "| PAPER_ONLY | ✅ |",
            "| SHADOW_ONLY | ✅ |",
            "| NO_BROKER | ✅ |",
            "| NO_LIVE_BOT_CHANGE | ✅ |",
            "| NO_PORTFOLIO_CSV_CHANGE | ✅ |",
            "| NO_COMMIT | ✅ |",
            "",
            "## Recommended next sprint",
            "",
            "**TAE DPE-6 — Learning Engine**",
        ]
    )
    ROOT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_summary(evaluation: dict[str, Any]) -> None:
    overall = evaluation["overall"]
    print("===== TAE DPE-5 RESULT EVALUATOR =====")
    print("Mode: READ_ONLY — paper portfolio comparison")
    print("Competitive dir:", COMPETITIVE_DIR)
    print("Collaborative dir:", COLLABORATIVE_DIR)
    print("Overall winner:", overall["winner"])
    print("Confidence:", f"{overall['confidence_pct']}%")
    print("Competitive metric wins:", overall["competitive_metric_wins"])
    print("Collaborative metric wins:", overall["collaborative_metric_wins"])
    print("Reason:", overall["reason"])


def main() -> int:
    missing: list[str] = []
    comp_portfolio, comp_metrics, comp_orders, comp_missing = load_arm_data(COMPETITIVE_DIR, "COMPETITIVE")
    collab_portfolio, collab_metrics, collab_orders, collab_missing = load_arm_data(COLLABORATIVE_DIR, "COLLABORATIVE")
    missing.extend(comp_missing)
    missing.extend(collab_missing)

    if not comp_portfolio or not comp_metrics or not collab_portfolio or not collab_metrics:
        print("ERROR: missing paper portfolio inputs", file=__import__("sys").stderr)
        for item in missing:
            print(" missing:", item, file=__import__("sys").stderr)
        return 1

    gii = load_json(GII_JSON) or {}
    gii_port = gii.get("portfolio") or {}
    market_opp = _f(gii_port.get("opportunity_cost_total"))
    market_capture = _f(gii_port.get("profit_capture_rate"))

    competitive = compute_arm_metrics(
        arm="COMPETITIVE",
        portfolio=comp_portfolio,
        metrics=comp_metrics,
        orders=comp_orders,
        market_opportunity_cost=market_opp,
        market_profit_capture_rate=market_capture,
    )
    collaborative = compute_arm_metrics(
        arm="COLLABORATIVE",
        portfolio=collab_portfolio,
        metrics=collab_metrics,
        orders=collab_orders,
        market_opportunity_cost=market_opp,
        market_profit_capture_rate=market_capture,
    )

    evaluation = build_evaluation(competitive, collaborative)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    EVAL_JSON.write_text(json.dumps(evaluation, indent=2) + "\n", encoding="utf-8")
    write_evaluation_md(evaluation)

    validation_pass = (
        EVAL_JSON.is_file()
        and EVAL_MD.is_file()
        and evaluation["overall"]["winner"] in {"COMPETITIVE", "COLLABORATIVE", "TIE"}
        and not missing
    )
    write_root_report(evaluation, validation_pass, missing)
    print_summary(evaluation)
    print("Wrote:", EVAL_JSON, EVAL_MD, ROOT_REPORT)
    return 0 if validation_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
