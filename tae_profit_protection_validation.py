#!/usr/bin/env python3
"""
TAE Historical Profit Protection Validator — X.PROTECT-2.

SHADOW_ONLY / PAPER_ONLY / NO_BROKER.
Validates whether shadow protection strategies would have added value historically.
Does NOT modify live_bot, portfolio, or signals.
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from tae_profit_protection_shadow import confidence_from_observations

HISTORY_CSV = Path("runtime_outputs/tae_intraday_fade_history.csv")
SHADOW_JSON = Path("tae_profit_protection_shadow.json")
DISCOVERY_JSON = Path("tae_intraday_discovery_engine.json")
KNOWLEDGE_JSON = Path("tae_knowledge_base.json")
PORTFOLIO_FILE = Path("portfolio.csv")

OUTPUT_JSON = Path("tae_profit_protection_validation.json")
OUTPUT_MD = Path("tae_profit_protection_validation.md")

STRATEGIES: list[tuple[str, str]] = [
    ("HOLD", "hold_pnl"),
    ("shadow_sell_20", "shadow_sell_20"),
    ("shadow_sell_30", "shadow_sell_30"),
    ("shadow_trailing_1", "shadow_trailing_1"),
    ("shadow_trailing_1_5", "shadow_trailing_1_5"),
]

SHADOW_STRATEGY_IDS = frozenset(
    {"shadow_sell_20", "shadow_sell_30", "shadow_trailing_1", "shadow_trailing_1_5"}
)

FADE_CLASSIFICATIONS = frozenset(
    {
        "WATCH_INTRADAY_FADE",
        "SIGNIFICANT_INTRADAY_FADE",
        "POTENTIAL_PARTIAL_TAKE_PROFIT",
    }
)

SHADOW_RECOMMENDATIONS = frozenset(
    {
        "INSUFFICIENT_DATA",
        "CONTINUE_OBSERVATION",
        "TEST_TRAILING_SHADOW",
        "TEST_PARTIAL_SELL_SHADOW",
        "DO_NOT_PROMOTE_TO_ADVISORY_YET",
        "AVOID_PROTECTION_FOR_NOW",
    }
)

FORBIDDEN_RECOMMENDATIONS = frozenset({"BUY", "SELL", "STOP", "TAKE_PROFIT"})

GATE_DEFINITIONS: list[tuple[str, str]] = [
    ("G1", "observations >= 30"),
    ("G2", "best strategy total_value > 0"),
    ("G3", "best strategy win_rate >= 0.60"),
    ("G4", "risk_of_cutting_winners <= 0.35"),
    ("G5", "best strategy beats HOLD by positive margin"),
    ("G6", "no single ticker contributes >50% of best strategy total"),
]


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def load_history(path: Path = HISTORY_CSV) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
    except (OSError, pd.errors.EmptyDataError):
        return pd.DataFrame()
    if df.empty:
        return df
    df = df.copy()
    df["ticker"] = df["ticker"].astype(str).str.upper()
    if "classification" in df.columns:
        df = df[df["classification"] != "DATA_UNAVAILABLE"]
    return df


def compute_hold_pnl(row: pd.Series) -> float:
    shares = pd.to_numeric(row.get("shares"), errors="coerce")
    avg = pd.to_numeric(row.get("avg_price"), errors="coerce")
    current = pd.to_numeric(row.get("current"), errors="coerce")
    if pd.isna(shares) or pd.isna(avg) or pd.isna(current):
        return float("nan")
    return round(float((current - avg) * shares), 2)


def enrich_observations(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out["hold_pnl"] = out.apply(compute_hold_pnl, axis=1)
    for _, col in STRATEGIES:
        if col == "hold_pnl":
            continue
        out[col] = pd.to_numeric(out.get(col), errors="coerce")
    out = out.dropna(subset=["hold_pnl"])
    return out


def dataset_health(df: pd.DataFrame) -> dict[str, Any]:
    observations = len(df)
    unique_days = int(df["date"].nunique()) if not df.empty and "date" in df.columns else 0
    unique_tickers = int(df["ticker"].nunique()) if not df.empty and "ticker" in df.columns else 0
    confidence = confidence_from_observations(observations)
    minimum_sample_warning = observations < 30
    if df.empty:
        data_quality = "MISSING"
    elif observations < 5:
        data_quality = "POOR"
    elif minimum_sample_warning:
        data_quality = "LIMITED"
    else:
        data_quality = "GOOD"
    date_range: list[str | None] = [None, None]
    if not df.empty and "date" in df.columns:
        dates = sorted(df["date"].astype(str).unique())
        date_range = [dates[0], dates[-1]]
    return {
        "observations": observations,
        "unique_days": unique_days,
        "unique_tickers": unique_tickers,
        "date_range": date_range,
        "data_quality": data_quality,
        "minimum_sample_warning": minimum_sample_warning,
        "confidence": confidence,
    }


def _compare_strategy(values: pd.Series, hold: pd.Series, *, epsilon: float = 0.01) -> dict[str, int]:
    win = loss = neutral = 0
    for strat_val, hold_val in zip(values, hold, strict=False):
        if pd.isna(strat_val) or pd.isna(hold_val):
            continue
        delta = float(strat_val) - float(hold_val)
        if delta > epsilon:
            win += 1
        elif delta < -epsilon:
            loss += 1
        else:
            neutral += 1
    return {"win_count": win, "loss_count": loss, "neutral_count": neutral}


def aggregate_strategy(df: pd.DataFrame, strategy_id: str, value_col: str) -> dict[str, Any]:
    if df.empty or value_col not in df.columns:
        return {
            "strategy_id": strategy_id,
            "total_value": 0.0,
            "avg_value": 0.0,
            "median_value": 0.0,
            "win_count": 0,
            "loss_count": 0,
            "neutral_count": 0,
            "win_rate": 0.0,
            "best_count": 0,
            "worst_count": 0,
            "max_gain": 0.0,
            "max_loss": 0.0,
            "std_dev": 0.0,
            "protection_efficiency": 0.0,
            "risk_of_cutting_winners": 0,
            "risk_of_cutting_winners_rate": 0.0,
            "delta_vs_hold_total": 0.0,
        }

    values = df[value_col]
    hold = df["hold_pnl"]
    cmp = _compare_strategy(values, hold)
    comparisons = cmp["win_count"] + cmp["loss_count"] + cmp["neutral_count"]
    win_rate = round(cmp["win_count"] / comparisons, 4) if comparisons else 0.0

    best_count = worst_count = 0
    strategy_cols = [col for _, col in STRATEGIES if col in df.columns]
    for _, row in df.iterrows():
        row_vals = {col: row[col] for col in strategy_cols if pd.notna(row.get(col))}
        if not row_vals:
            continue
        best_col = max(row_vals, key=lambda c: float(row_vals[c]))
        worst_col = min(row_vals, key=lambda c: float(row_vals[c]))
        if best_col == value_col:
            best_count += 1
        if worst_col == value_col:
            worst_count += 1

    total_missed = float(pd.to_numeric(df.get("missed_opportunity_usd"), errors="coerce").fillna(0).sum())
    total_value = round(float(values.sum()), 2)
    hold_total = round(float(hold.sum()), 2)
    protection_efficiency = round(total_value / total_missed, 4) if total_missed > 0 else 0.0

    std_dev = round(float(values.std(ddof=0)), 4) if len(values) > 1 else 0.0

    return {
        "strategy_id": strategy_id,
        "total_value": total_value,
        "avg_value": round(float(values.mean()), 2),
        "median_value": round(float(values.median()), 2),
        "win_count": cmp["win_count"],
        "loss_count": cmp["loss_count"],
        "neutral_count": cmp["neutral_count"],
        "win_rate": win_rate,
        "best_count": best_count,
        "worst_count": worst_count,
        "max_gain": round(float(values.max()), 2),
        "max_loss": round(float(values.min()), 2),
        "std_dev": std_dev if not math.isnan(std_dev) else 0.0,
        "protection_efficiency": protection_efficiency,
        "risk_of_cutting_winners": cmp["loss_count"],
        "risk_of_cutting_winners_rate": round(cmp["loss_count"] / comparisons, 4) if comparisons else 0.0,
        "delta_vs_hold_total": round(total_value - hold_total, 2),
    }


def select_best_strategy(strategy_stats: list[dict[str, Any]]) -> dict[str, Any]:
    shadow_stats = [s for s in strategy_stats if s["strategy_id"] in SHADOW_STRATEGY_IDS]
    if not shadow_stats:
        return {}
    ranked = sorted(
        shadow_stats,
        key=lambda s: (s["total_value"], s["win_rate"], -s["risk_of_cutting_winners_rate"]),
        reverse=True,
    )
    return ranked[0]


def ticker_recommendation(
    *,
    observations: int,
    best_strategy: str | None,
    best_delta: float,
    confidence: str,
) -> str:
    if observations < 3:
        return "INSUFFICIENT_DATA"
    if best_strategy is None or best_delta <= 0:
        return "AVOID_PROTECTION_FOR_NOW"
    if confidence == "LOW":
        return "CONTINUE_OBSERVATION"
    if "trailing" in (best_strategy or ""):
        return "TEST_TRAILING_SHADOW"
    if "sell" in (best_strategy or ""):
        return "TEST_PARTIAL_SELL_SHADOW"
    return "CONTINUE_OBSERVATION"


def aggregate_tickers(df: pd.DataFrame, strategy_stats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if df.empty:
        return []
    best_overall = select_best_strategy(strategy_stats)
    best_id = best_overall.get("strategy_id", "shadow_trailing_1")
    best_col = dict(STRATEGIES).get(best_id, best_id)
    if best_col not in df.columns:
        best_col = "shadow_trailing_1"

    rows: list[dict[str, Any]] = []
    for ticker, group in df.groupby("ticker"):
        obs = len(group)
        missed = round(float(pd.to_numeric(group["missed_opportunity_usd"], errors="coerce").fillna(0).sum()), 2)
        fade_count = int(group["classification"].isin(FADE_CLASSIFICATIONS).sum()) if "classification" in group else 0
        strat = aggregate_strategy(group, best_id, best_col)
        conf = confidence_from_observations(obs)
        delta = strat["delta_vs_hold_total"]
        rows.append(
            {
                "ticker": ticker,
                "observations": obs,
                "total_missed_opportunity": missed,
                "best_strategy": best_id,
                "best_strategy_value": strat["total_value"],
                "best_strategy_win_rate": strat["win_rate"],
                "repeated_fade_count": fade_count,
                "confidence": conf,
                "recommendation": ticker_recommendation(
                    observations=obs,
                    best_strategy=best_id,
                    best_delta=delta,
                    confidence=conf,
                ),
            }
        )
    return sorted(rows, key=lambda r: r["total_missed_opportunity"], reverse=True)


def aggregate_classifications(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty or "classification" not in df.columns:
        return []
    rows: list[dict[str, Any]] = []
    for classification, group in df.groupby("classification"):
        stats = [aggregate_strategy(group, sid, col) for sid, col in STRATEGIES if col in group.columns]
        best = select_best_strategy(stats)
        hold_stats = next((s for s in stats if s["strategy_id"] == "HOLD"), {})
        rows.append(
            {
                "classification": classification,
                "count": len(group),
                "avg_missed_opportunity": round(
                    float(pd.to_numeric(group["missed_opportunity_usd"], errors="coerce").fillna(0).mean()), 2
                ),
                "best_strategy": best.get("strategy_id"),
                "best_strategy_total": best.get("total_value", 0.0),
                "hold_total": hold_stats.get("total_value", 0.0),
                "win_rate": best.get("win_rate", 0.0),
                "confidence": confidence_from_observations(len(group)),
            }
        )
    return sorted(rows, key=lambda r: r["count"], reverse=True)


def aggregate_daily(df: pd.DataFrame, best_strategy: dict[str, Any]) -> list[dict[str, Any]]:
    if df.empty:
        return []
    best_id = best_strategy.get("strategy_id", "shadow_trailing_1")
    best_col = dict(STRATEGIES).get(best_id, best_id)
    rows: list[dict[str, Any]] = []
    group_cols = ["date", "run_id"] if "run_id" in df.columns else ["date"]
    for keys, group in df.groupby(group_cols):
        if isinstance(keys, tuple):
            date, run_id = keys[0], keys[1] if len(keys) > 1 else ""
        else:
            date, run_id = keys, ""
        missed = round(float(pd.to_numeric(group["missed_opportunity_usd"], errors="coerce").fillna(0).sum()), 2)
        hold_val = round(float(group["hold_pnl"].sum()), 2)
        strat_val = round(float(group[best_col].sum()), 2) if best_col in group.columns else 0.0
        verdict = "SHADOW_OUTPERFORMS_HOLD" if strat_val > hold_val else "HOLD_BETTER_OR_EQUAL"
        rows.append(
            {
                "date": date,
                "run_id": run_id,
                "total_missed_opportunity": missed,
                "best_strategy": best_id,
                "best_strategy_value": strat_val,
                "hold_value": hold_val,
                "delta_vs_hold": round(strat_val - hold_val, 2),
                "verdict": verdict,
            }
        )
    return sorted(rows, key=lambda r: (r["date"], r.get("run_id", "")))


def evaluate_gates(
    df: pd.DataFrame,
    health: dict[str, Any],
    best_strategy: dict[str, Any],
    hold_strategy: dict[str, Any],
    ticker_breakdown: list[dict[str, Any]],
) -> dict[str, Any]:
    observations = health["observations"]
    best_id = best_strategy.get("strategy_id", "")
    best_col = dict(STRATEGIES).get(best_id, best_id)

    g1 = observations >= 30
    g2 = best_strategy.get("total_value", 0) > 0
    g3 = best_strategy.get("win_rate", 0) >= 0.60
    g4 = best_strategy.get("risk_of_cutting_winners_rate", 1.0) <= 0.35
    g5 = best_strategy.get("delta_vs_hold_total", 0) > 0
    g6 = True
    if not df.empty and best_col in df.columns and best_strategy.get("total_value", 0) != 0:
        ticker_totals = df.groupby("ticker")[best_col].sum()
        max_share = float(ticker_totals.max()) / abs(float(best_strategy["total_value"]))
        g6 = max_share <= 0.50

    gate_results = {
        "G1": g1,
        "G2": g2,
        "G3": g3,
        "G4": g4,
        "G5": g5,
        "G6": g6,
    }
    failed = [name for name, ok in gate_results.items() if not ok]
    all_pass = not failed and observations >= 30

    if health["minimum_sample_warning"]:
        advisory_readiness = "NOT_READY"
    elif all_pass:
        advisory_readiness = "READY_FOR_SHADOW_ADVISORY"
    elif len(failed) <= 2 and g2 and g5:
        advisory_readiness = "WATCH"
    else:
        advisory_readiness = "NOT_READY"

    return {
        "gates": gate_results,
        "gate_definitions": {name: desc for name, desc in GATE_DEFINITIONS},
        "gates_passed": all_pass,
        "failed_gates": failed,
        "advisory_readiness": advisory_readiness,
        "hold_total": hold_strategy.get("total_value", 0.0),
        "best_strategy_id": best_id,
    }


def build_recommendations(
    health: dict[str, Any],
    gates: dict[str, Any],
    best_strategy: dict[str, Any],
) -> list[str]:
    recs: list[str] = []
    if health["minimum_sample_warning"] or health["observations"] == 0:
        recs.append("INSUFFICIENT_DATA")
    if gates["advisory_readiness"] != "READY_FOR_SHADOW_ADVISORY":
        recs.append("DO_NOT_PROMOTE_TO_ADVISORY_YET")
    if health["observations"] > 0 and gates["advisory_readiness"] == "NOT_READY":
        recs.append("CONTINUE_OBSERVATION")
    best_id = best_strategy.get("strategy_id", "")
    if best_id and best_strategy.get("delta_vs_hold_total", 0) > 0:
        if "trailing" in best_id:
            recs.append("TEST_TRAILING_SHADOW")
        elif "sell" in best_id:
            recs.append("TEST_PARTIAL_SELL_SHADOW")
    if not recs:
        recs.append("CONTINUE_OBSERVATION")
    deduped: list[str] = []
    for r in recs:
        if r not in deduped and r in SHADOW_RECOMMENDATIONS:
            deduped.append(r)
    assert not (set(deduped) & FORBIDDEN_RECOMMENDATIONS)
    return deduped


def build_validation_report(
    *,
    history_path: Path = HISTORY_CSV,
    shadow_json: Path = SHADOW_JSON,
    discovery_json: Path = DISCOVERY_JSON,
    knowledge_json: Path = KNOWLEDGE_JSON,
) -> dict[str, Any]:
    raw = load_history(history_path)
    df = enrich_observations(raw)
    health = dataset_health(df)

    strategy_stats = [aggregate_strategy(df, sid, col) for sid, col in STRATEGIES if col in df.columns or sid == "HOLD"]
    hold_stats = next((s for s in strategy_stats if s["strategy_id"] == "HOLD"), aggregate_strategy(df, "HOLD", "hold_pnl"))
    best_strategy = select_best_strategy(strategy_stats)

    ticker_breakdown = aggregate_tickers(df, strategy_stats)
    classification_breakdown = aggregate_classifications(df)
    daily_breakdown = aggregate_daily(df, best_strategy)
    gates = evaluate_gates(df, health, best_strategy, hold_stats, ticker_breakdown)
    recommendations = build_recommendations(health, gates, best_strategy)

    ranking = sorted(
        [s for s in strategy_stats if s["strategy_id"] in SHADOW_STRATEGY_IDS | {"HOLD"}],
        key=lambda s: s["total_value"],
        reverse=True,
    )

    verdict = "INSUFFICIENT_DATA"
    if health["observations"] == 0:
        verdict = "NO_HISTORY"
    elif gates["advisory_readiness"] == "READY_FOR_SHADOW_ADVISORY":
        verdict = "SHADOW_VALIDATION_PASSED"
    elif best_strategy.get("delta_vs_hold_total", 0) > 0:
        verdict = "PROMISING_BUT_NOT_READY"
    else:
        verdict = "HOLD_PREFERRED"

    optional_context = {
        "shadow_snapshot_loaded": load_json(shadow_json) is not None,
        "discovery_loaded": load_json(discovery_json) is not None,
        "knowledge_loaded": load_json(knowledge_json) is not None,
    }

    return {
        "schema": "tae_profit_protection_validation",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "SHADOW_ONLY",
        "live_trading_impact": "NONE",
        "dataset_health": health,
        "strategy_validation": strategy_stats,
        "strategy_ranking": ranking,
        "best_strategy": best_strategy,
        "hold_baseline": hold_stats,
        "ticker_breakdown": ticker_breakdown,
        "classification_breakdown": classification_breakdown,
        "daily_breakdown": daily_breakdown,
        "gates": gates,
        "recommendations": recommendations,
        "optional_context": optional_context,
        "verdict": verdict,
        "next_step": (
            "Continue observation until >=30 observations; then re-run validation."
            if health["minimum_sample_warning"]
            else "Proceed to X.COOLDOWN-1 if BUY→STOP→BUY churn observed in portfolio."
        ),
        "evidence_for_knowledge_base": [
            {
                "source": "tae_profit_protection_validation.json",
                "pattern_type": "BEST_SHADOW_HISTORICAL",
                "subject": best_strategy.get("strategy_id", "unknown"),
                "observations": health["observations"],
                "confidence": health["confidence"],
                "recommendation": recommendations[0] if recommendations else "CONTINUE_OBSERVATION",
                "safety_mode": "SHADOW_ONLY",
            }
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    health = report["dataset_health"]
    gates = report["gates"]
    best = report.get("best_strategy") or {}
    hold = report.get("hold_baseline") or {}
    lines = [
        "# TAE Profit Protection Historical Validation (X.PROTECT-2)",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Mode:** {report['mode']} | **Verdict:** {report['verdict']}",
        "",
        "## Dataset health",
        f"- Observations: **{health['observations']}**",
        f"- Unique days: {health['unique_days']} | Tickers: {health['unique_tickers']}",
        f"- Date range: {health['date_range']}",
        f"- Data quality: {health['data_quality']}",
        f"- Confidence: **{health['confidence']}**",
        f"- Minimum sample warning: {health['minimum_sample_warning']}",
        "",
        "## Strategy ranking",
        "",
        "| Strategy | Total | Δ vs HOLD | Win rate | Cut winners rate |",
        "|----------|-------|-----------|----------|------------------|",
    ]
    for s in report.get("strategy_ranking", []):
        lines.append(
            f"| {s['strategy_id']} | {s['total_value']} | {s['delta_vs_hold_total']} | "
            f"{s['win_rate']:.0%} | {s['risk_of_cutting_winners_rate']:.0%} |"
        )
    lines.extend(
        [
            "",
            "## Best strategy",
            f"- **{best.get('strategy_id', 'n/a')}** — total {best.get('total_value', 0)} USD",
            f"- HOLD baseline: {hold.get('total_value', 0)} USD",
            f"- Protection efficiency: {best.get('protection_efficiency', 0)}",
            "",
            "## Gates G1–G6",
            f"- **Advisory readiness:** {gates['advisory_readiness']}",
            f"- Gates passed: {gates['gates_passed']}",
            f"- Failed: {', '.join(gates['failed_gates']) or 'none'}",
            "",
        ]
    )
    for name, ok in gates["gates"].items():
        desc = gates["gate_definitions"].get(name, "")
        lines.append(f"- **{name}** ({desc}): {'PASS' if ok else 'FAIL'}")
    lines.extend(["", "## Ticker findings", ""])
    for t in report.get("ticker_breakdown", [])[:10]:
        lines.append(
            f"- **{t['ticker']}** — obs={t['observations']}, missed={t['total_missed_opportunity']} USD, "
            f"best={t['best_strategy']}, rec={t['recommendation']}"
        )
    lines.extend(["", "## Daily findings", ""])
    for d in report.get("daily_breakdown", []):
        lines.append(
            f"- **{d['date']}** ({d.get('run_id', '')}) — missed={d['total_missed_opportunity']}, "
            f"best={d['best_strategy_value']}, hold={d['hold_value']}, {d['verdict']}"
        )
    lines.extend(
        [
            "",
            "## Recommendations (SHADOW_ONLY)",
            "",
        ]
    )
    for r in report.get("recommendations", []):
        lines.append(f"- {r}")
    lines.extend(
        [
            "",
            "## Final verdict",
            f"- {report['verdict']}",
            f"- Next step: {report['next_step']}",
            "",
            "*No live BUY/SELL. Research validation only.*",
        ]
    )
    return "\n".join(lines) + "\n"


def write_outputs(report: dict[str, Any]) -> tuple[Path, Path]:
    OUTPUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    OUTPUT_MD.write_text(render_markdown(report), encoding="utf-8")
    return OUTPUT_JSON, OUTPUT_MD


def print_summary(report: dict[str, Any]) -> None:
    health = report["dataset_health"]
    gates = report["gates"]
    best = report.get("best_strategy") or {}
    print("===== TAE PROFIT PROTECTION VALIDATION (X.PROTECT-2) =====")
    print("Mode: SHADOW_ONLY | Verdict:", report["verdict"])
    print("Observations:", health["observations"], "| Confidence:", health["confidence"])
    print("Best strategy:", best.get("strategy_id"), "| Total:", best.get("total_value"))
    print("Advisory readiness:", gates["advisory_readiness"], "| Gates passed:", gates["gates_passed"])
    print("Recommendations:", ", ".join(report.get("recommendations", [])))


def main() -> int:
    report = build_validation_report()
    write_outputs(report)
    print_summary(report)
    print("Wrote:", OUTPUT_JSON, OUTPUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
