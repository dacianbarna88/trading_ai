#!/usr/bin/env python3
"""
TAE Exit Strategy Comparison — SMALL_ADAPTER v3 (READ_ONLY / PAPER_ONLY).

Cohorts: OPEN_ONLY | CLOSED_ONLY | ALL (default).
Does NOT modify live_bot, core/trailing, portfolio.csv, or promote live.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from core.trailing import (
    STOP_LOSS_PCT,
    TRAILING_ACTIVATE_PCT,
    TRAILING_DISTANCE_PCT,
    evaluate_position_exit,
    initial_trailing_state,
)
from tae_exit_strategy_bar_replay import (
    STRATEGY_ARMS,
    actual_closed_benchmark,
    apply_realistic_cost_to_metrics,
    compare_to_actual,
    load_replay_lots,
    reconstruct_fifo_lots,
    reconcile_fifo_quantities,
    run_bar_replay,
    write_forward_observations,
)
from tae_profit_protection_validation import (
    HISTORY_CSV,
    STRATEGIES,
    aggregate_strategy,
    enrich_observations,
    load_history,
)

SCHEMA = "tae_exit_strategy_comparison"
SCHEMA_VERSION = "v3"
MODE = "READ_ONLY"
SOURCE_COMMIT = "f7ed09e"

OUTPUT_JSON = Path("tae_exit_strategy_comparison.json")
OUTPUT_MD = Path("TAE_EXIT_STRATEGY_COMPARISON.md")

EXPERIMENT_JSON = Path("runtime_outputs/learning_to_profit/experiment_results.json")
DECISION_VALIDATION_JSON = Path("runtime_outputs/paper_decisions/decision_validation_results.json")
E3_FORWARD_JSON = Path("tae_e3_forward_paper.json")
REPLAY_JSON = Path("tae_decision_replay.json")

PROTECTION_HYPOTHESIS_TYPES = frozenset({"PROFIT_PROTECTION", "WINNER_LIFECYCLE"})

ALLOWED_VERDICTS = frozenset({
    "DATA_INSUFFICIENT_FOR_VALID_COMPARISON",
    "CLOSED_COHORT_REPLAY_COMPLETED",
    "ATR_ADAPTIVE_RESEARCH_LEADER",
    "TREND_FOLLOWER_RESEARCH_LEADER",
    "HYBRID_RESEARCH_LEADER",
    "BASELINE_REMAINS_PREFERRED",
    "NO_STRATEGY_ECONOMICALLY_PROVEN",
})

LEADER_MAP = {
    "BASELINE_FIXED": "BASELINE_REMAINS_PREFERRED",
    "ATR_ADAPTIVE": "ATR_ADAPTIVE_RESEARCH_LEADER",
    "TREND_FOLLOWER": "TREND_FOLLOWER_RESEARCH_LEADER",
    "HYBRID_ATR_TREND": "HYBRID_RESEARCH_LEADER",
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return SOURCE_COMMIT


def simulate_baseline_fixed_pnl(row: pd.Series) -> float:
    shares = _f(row.get("shares"))
    avg = _f(row.get("avg_price"))
    high = _f(row.get("high"))
    low = _f(row.get("low"))
    current = _f(row.get("current"))
    if not shares or not avg or not high or not low or not current:
        return float("nan")
    stop_price = avg * (1.0 + STOP_LOSS_PCT / 100.0)
    if low <= stop_price:
        return round((stop_price - avg) * shares, 2)
    state = initial_trailing_state(avg)
    after_high = evaluate_position_exit(
        avg, high, state,
        stop_loss_pct=STOP_LOSS_PCT,
        activate_pct=TRAILING_ACTIVATE_PCT,
        trail_distance_pct=TRAILING_DISTANCE_PCT,
        min_locked_profit_pct=2.0,
    )
    if after_high.action == "SELL_STOP_LOSS":
        return round((stop_price - avg) * shares, 2)
    after_current = evaluate_position_exit(
        avg, current, after_high.state,
        stop_loss_pct=STOP_LOSS_PCT,
        activate_pct=TRAILING_ACTIVATE_PCT,
        trail_distance_pct=TRAILING_DISTANCE_PCT,
        min_locked_profit_pct=2.0,
    )
    if after_current.action == "SELL_STOP_LOSS":
        return round((stop_price - avg) * shares, 2)
    if after_current.action == "SELL_TRAILING":
        return round(((after_current.state.trailing_stop or current) - avg) * shares, 2)
    return round((current - avg) * shares, 2)


def enrich_with_baseline_fixed(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out["baseline_fixed"] = out.apply(simulate_baseline_fixed_pnl, axis=1)
    return out


def build_fade_snapshot_layer() -> dict[str, Any]:
    df = load_history()
    enriched = enrich_observations(enrich_with_baseline_fixed(df))
    strategies = []
    for strategy_id, col in list(STRATEGIES) + [("BASELINE_FIXED", "baseline_fixed")]:
        base = aggregate_strategy(enriched, strategy_id, col)
        strategies.append({**base, "layer": "fade_snapshot"})
    return {
        "layer": "fade_snapshot",
        "source": str(HISTORY_CSV),
        "observations": len(enriched),
        "baseline_fixed_net_pnl": next(
            (s.get("total_value") for s in strategies if s["strategy_id"] == "BASELINE_FIXED"), None
        ),
        "strategies": strategies,
        "note": "Legacy fade snapshot layer retained for regression; separate from lot bar-replay.",
    }


def strategy_definitions() -> dict[str, Any]:
    return {
        "BASELINE_FIXED": {"stop": "-3%", "activation": "+5%", "trail": "3%", "floor": "+2%", "hard_tp": False},
        "ATR_ADAPTIVE": {
            "initial_stop_pct": "clamp(max(3,1.5*ATR%),3,7)",
            "activation": "max(5%,1.5R)",
            "trail_distance": "clamp(2*ATR%,3,8)",
            "floor": "+2%",
        },
        "TREND_FOLLOWER": {"stop": "-3%", "exit": "EMA20<EMA50 for 2 bars", "hard_tp": False},
        "HYBRID_ATR_TREND": {"priority": ["initial_stop", "trailing", "confirmed_trend", "HOLD"]},
    }


def _strip_trades(result: dict[str, Any]) -> dict[str, Any]:
    out = {k: v for k, v in result.items() if k != "_trades_by_arm"}
    # Drop heavy trade lists from nested strategies for top-level JSON size; keep rankings/metrics
    slim_strategies = []
    for s in out.get("strategies") or []:
        slim_strategies.append({
            "strategy_id": s["strategy_id"],
            "metrics": s.get("metrics"),
            "trade_count": len(s.get("trades") or []),
        })
    out["strategies"] = slim_strategies
    return out


def _leader(result: dict[str, Any]) -> str | None:
    ranks = result.get("strategy_rankings") or []
    return ranks[0]["strategy_id"] if ranks else None


def choose_overall_verdict(
    open_r: dict[str, Any],
    closed_r: dict[str, Any],
    all_r: dict[str, Any],
) -> tuple[str, str, dict[str, str | None]]:
    leaders = {
        "open_only": _leader(open_r),
        "closed_only": _leader(closed_r),
        "all_lots": _leader(all_r),
    }
    closed_n = int(closed_r.get("positions") or 0)
    if closed_n < 5 and int(all_r.get("positions") or 0) < 5:
        return (
            "DATA_INSUFFICIENT_FOR_VALID_COMPARISON",
            "Too few eligible bar-replay lots after history filtering.",
            leaders,
        )
    unique = {v for v in leaders.values() if v}
    if len(unique) > 1:
        return (
            "NO_STRATEGY_ECONOMICALLY_PROVEN",
            (
                f"Research leaders differ across cohorts: {leaders}. "
                "Instability implies no single economically proven exit strategy. "
                "RESEARCH LEADER != ECONOMICALLY PROVEN != LIVE PROMOTION."
            ),
            leaders,
        )
    leader = leaders["all_lots"] or leaders["closed_only"] or leaders["open_only"]
    if leader and closed_n >= 5:
        # Prefer closed-informed leader map when consistent
        return (
            LEADER_MAP.get(leader, "CLOSED_COHORT_REPLAY_COMPLETED"),
            (
                f"Consistent research leader={leader} across reported cohorts. "
                "Historical only — not economically proven; forward PAPER still required."
            ),
            leaders,
        )
    return (
        "CLOSED_COHORT_REPLAY_COMPLETED",
        "Closed cohort replay completed; review rankings before any economic claim.",
        leaders,
    )


def build_linked_paper() -> dict[str, Any]:
    validation = load_json(DECISION_VALIDATION_JSON) or {}
    results = validation.get("results") or []
    return {
        "certainty": "linked_paper",
        "observations": len(results),
        "note": "Separate certainty layer; not merged into historical lot PnL.",
    }


def build_forward_paper() -> dict[str, Any]:
    experiments_doc = load_json(EXPERIMENT_JSON) or {}
    experiments = experiments_doc.get("experiments") or []
    protection = [e for e in experiments if str(e.get("hypothesis_type", "")).upper() in PROTECTION_HYPOTHESIS_TYPES]
    return {
        "certainty": "forward_paper",
        "observations": len(protection),
        "forward_observations_file": "tae_exit_strategy_forward_observations.csv",
        "status": "FORWARD_PAPER_RECONCILIATION_PENDING",
        "note": "Shadow observation file may be refreshed READ_ONLY; not reconciled realized fills.",
    }


def build_report(
    *,
    bars_by_ticker=None,
    run_cohorts: tuple[str, ...] = ("OPEN_ONLY", "CLOSED_ONLY", "ALL"),
) -> dict[str, Any]:
    all_lots = reconstruct_fifo_lots()
    open_lots = [l for l in all_lots if l.status == "OPEN"]
    closed_lots = [l for l in all_lots if l.status == "CLOSED"]
    reconcile = reconcile_fifo_quantities()

    cohort_results: dict[str, dict[str, Any]] = {}
    trades_cache: dict[str, Any] = {}
    for cohort in run_cohorts:
        key = cohort.lower() if cohort != "ALL" else "all_lots"
        if cohort == "OPEN_ONLY":
            key = "open_only"
        elif cohort == "CLOSED_ONLY":
            key = "closed_only"
        result = run_bar_replay(cohort=cohort, bars_by_ticker=bars_by_ticker)
        trades_cache[key] = result.pop("_trades_by_arm", {})
        cohort_results[key] = _strip_trades(result)

    # Ensure keys exist
    open_r = cohort_results.get("open_only") or {}
    closed_r = cohort_results.get("closed_only") or {}
    all_r = cohort_results.get("all_lots") or {}

    actual = actual_closed_benchmark(load_replay_lots("CLOSED_ONLY"))
    actual_vs = {}
    for arm in STRATEGY_ARMS:
        trades = (trades_cache.get("closed_only") or {}).get(arm) or []
        actual_vs[arm] = compare_to_actual(trades, actual)

    # Cost sensitivity on ALL cohort
    cost_scenarios = {
        "SCENARIO_ZERO_COST": {
            "commission": 0.0,
            "entry_slippage_bps": 0.0,
            "exit_slippage_bps": 0.0,
            "rankings": all_r.get("strategy_rankings") or [],
            "leader": _leader(all_r),
        },
        "SCENARIO_REALISTIC_COST": {
            "commission": 0.0,
            "entry_slippage_bps": 5.0,
            "exit_slippage_bps": 5.0,
            "label": "sensitivity_only_not_broker_truth",
            "rankings": [],
            "leader": None,
        },
    }
    realistic_rankings = []
    for arm in STRATEGY_ARMS:
        trades = (trades_cache.get("all_lots") or {}).get(arm) or []
        m = apply_realistic_cost_to_metrics(trades)
        realistic_rankings.append({"strategy_id": arm, "net_pnl": m.get("net_pnl"), "profit_factor": m.get("profit_factor"),
                                   "expectancy": m.get("expectancy"), "max_drawdown": m.get("max_drawdown"),
                                   "profit_capture_rate": m.get("profit_capture_rate")})
    realistic_rankings = sorted(realistic_rankings, key=lambda s: (s.get("net_pnl") or 0.0, s.get("expectancy") or 0.0), reverse=True)
    cost_scenarios["SCENARIO_REALISTIC_COST"]["rankings"] = realistic_rankings
    cost_scenarios["SCENARIO_REALISTIC_COST"]["leader"] = realistic_rankings[0]["strategy_id"] if realistic_rankings else None

    # Forward observations from ALL trades if present
    if trades_cache.get("all_lots"):
        write_forward_observations(trades_cache["all_lots"])

    verdict, rationale, leaders = choose_overall_verdict(open_r, closed_r, all_r)
    assert verdict in ALLOWED_VERDICTS

    # Lot inventory is always full-universe; cohort run may be partial (--cohort open).
    selected_open = len(load_replay_lots("OPEN_ONLY"))
    selected_closed = len(load_replay_lots("CLOSED_ONLY"))
    selected_all = len(load_replay_lots("ALL"))
    eligible_open = int(open_r.get("positions") or 0) if open_r else 0
    eligible_closed = int(closed_r.get("positions") or 0) if closed_r else 0
    eligible_all = int(all_r.get("positions") or 0) if all_r else 0
    excl: dict[str, int] = {}
    for key in ("open_only", "closed_only", "all_lots"):
        reasons = ((cohort_results.get(key) or {}).get("data_quality") or {}).get("exclusion_reasons") or {}
        for rk, rv in reasons.items():
            excl[rk] = excl.get(rk, 0) + int(rv)

    report = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now(),
        "source_commit": git_head(),
        "mode": MODE,
        "live_trading_impact": "NONE",
        "promotion_eligibility": False,
        "cohort_definition": {
            "default": "ALL",
            "open_only": "FIFO residual OPEN lots (legacy survivor cohort)",
            "closed_only": "FIFO CLOSED lots; actual exits are benchmarks only",
            "all": "OPEN + CLOSED FIFO lots",
            "cohorts_executed": list(run_cohorts),
            "open_sample_was_survivor_biased": True,
            "survivor_bias_status": (
                "REDUCED_BY_INCLUDING_CLOSED_LOTS"
                if selected_closed > 0 and "CLOSED_ONLY" in run_cohorts
                else "OPEN_SAMPLE_WAS_SURVIVOR_BIASED"
            ),
        },
        "lot_reconstruction": {
            "total_buy_lots": len(all_lots),
            "open_lots": len(open_lots),
            "closed_lots": len(closed_lots),
            "selected_open_before_history": selected_open,
            "selected_closed_before_history": selected_closed,
            "selected_all_before_history": selected_all,
            "eligible_open": eligible_open if "OPEN_ONLY" in run_cohorts else selected_open,
            "eligible_closed": eligible_closed if "CLOSED_ONLY" in run_cohorts else selected_closed,
            "eligible_all": eligible_all if "ALL" in run_cohorts else selected_all,
            "excluded": sum(excl.values()),
            "exclusion_reasons": excl,
            "fifo_reconcile_ok": reconcile.get("ok"),
            "coverage_selected_all_over_total": round(selected_all / len(all_lots), 4) if all_lots else None,
            "coverage_eligible_all_over_total": (
                round(eligible_all / len(all_lots), 4)
                if all_lots and "ALL" in run_cohorts
                else round(selected_all / len(all_lots), 4) if all_lots else None
            ),
        },
        "methodology": all_r.get("methodology") or {},
        "strategy_definitions": strategy_definitions(),
        "cost_scenarios": cost_scenarios,
        "historical_counterfactual": {
            "fade_snapshot_layer": build_fade_snapshot_layer(),
            "open_only": open_r,
            "closed_only": closed_r,
            "all_lots": all_r,
        },
        "linked_paper": build_linked_paper(),
        "forward_paper": build_forward_paper(),
        "actual_closed_benchmark": actual,
        "actual_vs_counterfactual": actual_vs,
        "strategy_rankings": {
            "open_only": open_r.get("strategy_rankings") or [],
            "closed_only": closed_r.get("strategy_rankings") or [],
            "all_lots": all_r.get("strategy_rankings") or [],
            "realistic_cost": realistic_rankings,
        },
        "ticker_breakdown": all_r.get("ticker_breakdown") or {},
        "region_breakdown": all_r.get("region_breakdown") or {},
        "volatility_breakdown": all_r.get("volatility_breakdown") or {},
        "trend_regime_breakdown": all_r.get("trend_regime_breakdown") or {},
        "exit_reason_breakdown": all_r.get("exit_reason_breakdown") or {},
        "limitations": [
            "OPEN_ONLY cohort is survivor-biased if used alone.",
            "Including CLOSED lots reduces but does not eliminate path-dependency bias.",
            "Counterfactual exits after actual sell assume shares still held — research only.",
            "Same-bar stop/trail uses conservative gap/open rule.",
            "Realistic cost scenario is sensitivity only, not broker truth.",
            "Forward PAPER reconciliation pending.",
            "Historical research leader is not live promotion eligibility.",
        ],
        "data_quality": {
            "open_only": open_r.get("data_quality"),
            "closed_only": closed_r.get("data_quality"),
            "all_lots": all_r.get("data_quality"),
        },
        "verdict": verdict,
        "verdict_rationale": rationale,
        "research_leaders": leaders,
        "economic_verdict": "NO_STRATEGY_ECONOMICALLY_PROVEN",
        "next_action": (
            "Review CLOSED_ONLY and ALL_LOTS rankings; accumulate tagged forward PAPER; "
            "do not promote live."
        ),
        "safety": {
            "live_bot_modified": False,
            "core_trailing_modified": False,
            "portfolio_modified": False,
            "orders_executed": False,
            "no_live_promotion": True,
        },
    }
    return report


def _fmt_row(s: dict[str, Any]) -> str:
    m = s.get("metrics") or s
    pf = m.get("profit_factor")
    pf_s = "∞" if pf == float("inf") else pf
    return (
        f"| {s.get('strategy_id', m.get('strategy_id'))} | {m.get('net_pnl')} | {pf_s} | "
        f"{m.get('expectancy')} | {m.get('max_drawdown')} | {m.get('profit_capture_rate')} | "
        f"{m.get('closed_trades', m.get('sample_size'))} |"
    )


def render_markdown(report: dict[str, Any]) -> str:
    lr = report.get("lot_reconstruction") or {}
    hist = report.get("historical_counterfactual") or {}
    lines = [
        "# TAE Exit Strategy Comparison",
        "",
        f"**Generated:** {report['generated_at']}  ",
        f"**Schema:** {report['schema_version']} | **Mode:** {MODE} | **Source:** `{report.get('source_commit')}`",
        "",
        "## 1. Universe / lot reconstruction",
        "",
        f"- TOTAL BUY lots: **{lr.get('total_buy_lots')}**",
        f"- OPEN lots: **{lr.get('open_lots')}** | CLOSED lots: **{lr.get('closed_lots')}**",
        f"- Eligible OPEN/CLOSED/ALL: **{lr.get('eligible_open')}** / **{lr.get('eligible_closed')}** / **{lr.get('eligible_all')}**",
        f"- Excluded: **{lr.get('excluded')}** reasons={lr.get('exclusion_reasons')}",
        f"- Coverage eligible_all/total: **{lr.get('coverage_eligible_all_over_total')}**",
        f"- FIFO reconcile ok: **{lr.get('fifo_reconcile_ok')}**",
        "",
        f"**OPEN SAMPLE WAS SURVIVOR-BIASED** — status after extension: `{report['cohort_definition'].get('survivor_bias_status')}`",
        "",
        "## Verdict",
        "",
        f"- Research verdict: `{report['verdict']}`",
        f"- Research leaders: `{report.get('research_leaders')}`",
        f"- Economic: `{report['economic_verdict']}`",
        f"- promotion_eligibility: **{report['promotion_eligibility']}**",
        f"- {report.get('verdict_rationale')}",
        "",
        "> RESEARCH LEADER != ECONOMICALLY PROVEN != LIVE PROMOTION",
        "",
        "## 4. OPEN_ONLY",
        "",
        "| Strategy | Net PnL | PF | Exp | MaxDD | Capture | Closed |",
        "|----------|---------|----|-----|-------|---------|--------|",
    ]
    for s in (hist.get("open_only") or {}).get("strategies") or []:
        lines.append(_fmt_row(s))
    lines.extend(["", "## 5. CLOSED_ONLY", "",
                  "| Strategy | Net PnL | PF | Exp | MaxDD | Capture | Closed |",
                  "|----------|---------|----|-----|-------|---------|--------|"])
    for s in (hist.get("closed_only") or {}).get("strategies") or []:
        lines.append(_fmt_row(s))
    lines.extend(["", "## 6. ALL_LOTS", "",
                  "| Strategy | Net PnL | PF | Exp | MaxDD | Capture | Closed |",
                  "|----------|---------|----|-----|-------|---------|--------|"])
    for s in (hist.get("all_lots") or {}).get("strategies") or []:
        lines.append(_fmt_row(s))

    actual = report.get("actual_closed_benchmark") or {}
    lines.extend([
        "",
        "## 7. Actual closed benchmark",
        "",
        f"- n={actual.get('sample_size')} net_pnl={actual.get('actual_net_pnl')} "
        f"pf={actual.get('actual_profit_factor')} win_rate={actual.get('actual_win_rate')} "
        f"exp={actual.get('actual_expectancy')} mdd={actual.get('actual_max_drawdown')}",
        f"- exit reasons: {actual.get('actual_exit_reason_breakdown')}",
        "",
        "## 8. A/B/C/D vs actual (CLOSED_ONLY)",
        "",
    ])
    for arm, d in (report.get("actual_vs_counterfactual") or {}).items():
        lines.append(
            f"- **{arm}**: Δpnl={d.get('delta_vs_actual_pnl')} earlier={d.get('earlier_exit_count_vs_actual')} "
            f"later={d.get('later_exit_count_vs_actual')} same_day={d.get('same_day_exit_count')} "
            f"avoided_losses={d.get('avoided_actual_losses')} reduced_winners={d.get('reduced_actual_winners')}"
        )

    zero = (report.get("cost_scenarios") or {}).get("SCENARIO_ZERO_COST") or {}
    real = (report.get("cost_scenarios") or {}).get("SCENARIO_REALISTIC_COST") or {}
    lines.extend([
        "",
        "## 9. Zero-cost vs realistic-cost",
        "",
        f"- Zero-cost leader: `{zero.get('leader')}`",
        f"- Realistic-cost (±5bps) leader: `{real.get('leader')}` (sensitivity only)",
        "",
        "## Limitations",
        "",
    ])
    for lim in report.get("limitations") or []:
        lines.append(f"- {lim}")
    lines.extend([
        "",
        f"**Next action:** {report.get('next_action')}",
        "",
        "## Safety",
        "",
        "- live_bot.py / core/trailing.py / portfolio.csv — not modified",
        "- No orders; promotion_eligibility false",
        "",
    ])
    return "\n".join(lines)


def print_terminal_summary(report: dict[str, Any]) -> None:
    lr = report.get("lot_reconstruction") or {}
    print("=== TAE Exit Strategy Comparison v3 ===")
    print(f"total_buy_lots={lr.get('total_buy_lots')} eligible_open={lr.get('eligible_open')} "
          f"eligible_closed={lr.get('eligible_closed')} eligible_all={lr.get('eligible_all')} "
          f"excluded={lr.get('excluded')} coverage={lr.get('coverage_eligible_all_over_total')}")
    for label in ("closed_only", "all_lots"):
        print(f"-- {label} --")
        for s in ((report.get("historical_counterfactual") or {}).get(label) or {}).get("strategies") or []:
            m = s.get("metrics") or {}
            print(f"  {s['strategy_id']}: pnl={m.get('net_pnl')} pf={m.get('profit_factor')} "
                  f"exp={m.get('expectancy')} mdd={m.get('max_drawdown')}")
    actual = report.get("actual_closed_benchmark") or {}
    print(f"actual_benchmark_pnl={actual.get('actual_net_pnl')}")
    print(f"research_leaders={report.get('research_leaders')}")
    print(f"zero_cost_leader={(report.get('cost_scenarios') or {}).get('SCENARIO_ZERO_COST', {}).get('leader')}")
    print(f"realistic_cost_leader={(report.get('cost_scenarios') or {}).get('SCENARIO_REALISTIC_COST', {}).get('leader')}")
    print(f"verdict={report.get('verdict')} promotion_eligibility={report.get('promotion_eligibility')}")
    print(f"next_action={report.get('next_action')}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--cohort", default="all", choices=["open", "closed", "all", "OPEN_ONLY", "CLOSED_ONLY", "ALL"])
    args, _unknown = parser.parse_known_args(argv)
    cohort = str(args.cohort).upper()
    if cohort == "OPEN":
        cohorts = ("OPEN_ONLY",)
    elif cohort == "CLOSED":
        cohorts = ("CLOSED_ONLY",)
    else:
        # Default: generate all three cohorts for apples-to-apples reporting
        cohorts = ("OPEN_ONLY", "CLOSED_ONLY", "ALL")

    report = build_report(run_cohorts=cohorts)
    # If user asked single cohort, still OK — missing keys empty
    OUTPUT_JSON.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    OUTPUT_MD.write_text(render_markdown(report), encoding="utf-8")
    print(f"Wrote {OUTPUT_JSON}")
    print(f"Wrote {OUTPUT_MD}")
    print_terminal_summary(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
