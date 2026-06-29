"""
Historical Results Analysis — Phase X Sprint X.5

ANALYSIS_ONLY | RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE

Read-only analysis of completed historical execution results.
"""

from __future__ import annotations

import json
import logging
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from research_core.strategy_simulation.historical_results_analysis_report import (
    DISCOVERY_INPUT_PATH,
    EXECUTION_INPUT_PATH,
    HistoricalResultsAnalysisReport,
    HistoricalResultsAnalysisVerdict,
)
from research_core.strategy_simulation.performance_metrics import METRIC_FIELDS

logger = logging.getLogger(__name__)

RANK_METRICS = (
    "profit_pct",
    "sharpe",
    "sortino",
    "max_drawdown",
    "profit_factor",
    "expectancy",
    "recovery_factor",
    "trade_count",
)

HORIZONS = ("2Y", "5Y", "10Y", "20Y")
MARKETS = ("US", "EU", "UK", "ASIA")

LOWER_IS_BETTER = {"max_drawdown"}

OUTLIER_METRICS = ("profit_pct", "sharpe", "max_drawdown")
ROBUST_SCORE_WEIGHTS = {
    "avg_sharpe": 0.35,
    "market_coverage": 0.25,
    "horizon_strength": 0.25,
    "sharpe_20y": 0.15,
}


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * pct / 100.0
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _distribution_stats(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "p10": None,
            "p25": None,
            "p75": None,
            "p90": None,
            "min": None,
            "max": None,
        }
    return {
        "count": len(values),
        "mean": round(statistics.mean(values), 4),
        "median": round(statistics.median(values), 4),
        "p10": round(_percentile(values, 10) or 0.0, 4),
        "p25": round(_percentile(values, 25) or 0.0, 4),
        "p75": round(_percentile(values, 75) or 0.0, 4),
        "p90": round(_percentile(values, 90) or 0.0, 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    n = len(xs)

    def ranks(values: list[float]) -> list[float]:
        indexed = sorted(enumerate(values), key=lambda item: item[1])
        out = [0.0] * n
        index = 0
        while index < n:
            start = index
            value = indexed[index][1]
            while index < n and indexed[index][1] == value:
                index += 1
            avg_rank = (start + index - 1) / 2.0 + 1.0
            for position in range(start, index):
                out[indexed[position][0]] = avg_rank
        return out

    rx = ranks(xs)
    ry = ranks(ys)
    mean_x = statistics.mean(rx)
    mean_y = statistics.mean(ry)
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(rx, ry))
    den_x = sum((x - mean_x) ** 2 for x in rx) ** 0.5
    den_y = sum((y - mean_y) ** 2 for y in ry) ** 0.5
    if den_x == 0 or den_y == 0:
        return None
    return round(num / (den_x * den_y), 4)


class HistoricalResultsAnalysisEngine:
    """Analyzes historical execution results — read-only, no execution."""

    def __init__(self, root: Path | str = Path(".")) -> None:
        self._root = Path(root)
        self._warnings: list[str] = []

    def analyze(self) -> HistoricalResultsAnalysisReport:
        execution = self._load_json(EXECUTION_INPUT_PATH)
        discovery = self._load_json(DISCOVERY_INPUT_PATH)

        if execution is None:
            return HistoricalResultsAnalysisReport(
                verdict=HistoricalResultsAnalysisVerdict.HISTORICAL_RESULTS_ANALYSIS_INPUT_MISSING,
                jobs_total=0,
                jobs_completed=0,
                jobs_blocked=0,
                jobs_failed=0,
                top_20_global_results=[],
                top_10_per_horizon={},
                top_10_per_market={},
                global_rankings={},
                robust_strategy_shortlist=[],
                weak_strategy_shortlist=[],
                blocked_jobs_summary={},
                strategy_families={},
                research_conclusions=["Historical execution input missing."],
                recommended_next_action="Run historical execution to completion before analysis.",
                statistical_appendix=None,
                warnings=list(self._warnings),
            )

        results = execution.get("execution_results") or []
        if not isinstance(results, list):
            self._warnings.append("execution_results missing or invalid")
            results = []

        completed = [item for item in results if item.get("execution_status") == "COMPLETED"]
        blocked = [item for item in results if item.get("execution_status") == "BLOCKED"]
        failed = [item for item in results if item.get("execution_status") == "FAILED"]

        strategy_meta = self._build_strategy_meta(discovery)

        enriched_completed = [self._enrich_result(item, strategy_meta) for item in completed]
        global_rankings = self._build_global_rankings(enriched_completed)
        top_20 = self._top_by_composite(enriched_completed, 20)
        top_10_horizon = self._top_per_group(enriched_completed, "time_horizon", HORIZONS, 10)
        top_10_market = self._top_per_group(enriched_completed, "market", MARKETS, 10)
        robust = self._robust_strategies(enriched_completed)
        weak = self._weak_strategies(enriched_completed)
        blocked_summary = self._blocked_summary(blocked)
        families = self._strategy_families(enriched_completed, robust, strategy_meta)
        conclusions = self._research_conclusions(
            execution, enriched_completed, blocked, robust, weak, blocked_summary, families
        )
        next_action = self._recommended_next_action(robust, weak, blocked_summary)
        statistical_appendix = self._statistical_validation(enriched_completed, robust)

        verdict = (
            HistoricalResultsAnalysisVerdict.HISTORICAL_RESULTS_ANALYSIS_READY_WITH_WARNINGS
            if self._warnings
            else HistoricalResultsAnalysisVerdict.HISTORICAL_RESULTS_ANALYSIS_READY
        )

        return HistoricalResultsAnalysisReport(
            verdict=verdict,
            jobs_total=int(execution.get("jobs_total", len(results))),
            jobs_completed=len(completed),
            jobs_blocked=len(blocked),
            jobs_failed=len(failed),
            top_20_global_results=top_20,
            top_10_per_horizon=top_10_horizon,
            top_10_per_market=top_10_market,
            global_rankings=global_rankings,
            robust_strategy_shortlist=robust,
            weak_strategy_shortlist=weak,
            blocked_jobs_summary=blocked_summary,
            strategy_families=families,
            research_conclusions=conclusions,
            recommended_next_action=next_action,
            statistical_appendix=statistical_appendix,
            warnings=list(self._warnings),
        )

    def _load_json(self, rel_path: Path) -> dict[str, Any] | None:
        path = self._root / rel_path
        if not path.is_file():
            self._warnings.append(f"Missing input: {rel_path.name}")
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self._warnings.append(f"Could not read {rel_path.name}: {exc}")
            return None
        return payload if isinstance(payload, dict) else None

    def _build_strategy_meta(self, discovery: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
        if not discovery:
            self._warnings.append("Discovery input missing — strategy family metadata limited.")
            return {}

        registry = discovery.get("discovery_registry")
        if not isinstance(registry, list):
            return {}

        mapping: dict[str, dict[str, Any]] = {}
        for item in registry:
            if isinstance(item, dict):
                sid = str(item.get("discovery_id", "")).strip()
                if sid:
                    mapping[sid] = {
                        "entry_rule": str(item.get("entry", "")),
                        "exit_rule": str(item.get("exit", "")),
                        "market_filter": str(item.get("market", "")),
                        "holding_period": int(item.get("holding", 0) or 0),
                        "risk_profile": str(item.get("risk", "")),
                    }
        return mapping

    def _enrich_result(
        self,
        item: dict[str, Any],
        strategy_meta: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        metrics = item.get("metrics") or {}
        meta = strategy_meta.get(str(item.get("strategy_id", "")), {})
        row = {
            "research_job_id": item.get("research_job_id"),
            "strategy_id": item.get("strategy_id"),
            "simulation_id": item.get("simulation_id"),
            "market": item.get("market"),
            "time_horizon": item.get("time_horizon"),
            "trade_count": item.get("trade_count"),
            "entry_rule": meta.get("entry_rule"),
            "exit_rule": meta.get("exit_rule"),
            "market_filter": meta.get("market_filter"),
            "holding_period": meta.get("holding_period"),
            "risk_profile": meta.get("risk_profile"),
        }
        for field in METRIC_FIELDS:
            value = metrics.get(field)
            row[field] = float(value) if value is not None else None
        row["composite_score"] = self._composite_score(row)
        return row

    @staticmethod
    def _composite_score(row: dict[str, Any]) -> float:
        sharpe = float(row.get("sharpe") or 0.0)
        sortino = float(row.get("sortino") or 0.0)
        pf = float(row.get("profit_factor") or 0.0)
        pf_norm = min(pf, 5.0) / 5.0
        return round(sharpe * 0.45 + sortino * 0.35 + pf_norm * 0.20, 4)

    def _build_global_rankings(self, completed: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        rankings: dict[str, list[dict[str, Any]]] = {}
        for metric in RANK_METRICS:
            reverse = metric not in LOWER_IS_BETTER
            sorted_rows = sorted(
                completed,
                key=lambda row: float(row.get(metric) or (float("inf") if not reverse else -float("inf"))),
                reverse=reverse,
            )
            rankings[metric] = [self._slim_row(row, metric) for row in sorted_rows[:20]]
        return rankings

    def _top_by_composite(self, completed: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
        sorted_rows = sorted(completed, key=lambda row: row.get("composite_score", 0.0), reverse=True)
        return [self._slim_row(row) for row in sorted_rows[:count]]

    def _top_per_group(
        self,
        completed: list[dict[str, Any]],
        field: str,
        values: tuple[str, ...],
        count: int,
    ) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for value in values:
            subset = [row for row in completed if row.get(field) == value]
            subset.sort(key=lambda row: float(row.get("sharpe") or -999), reverse=True)
            grouped[value] = [self._slim_row(row) for row in subset[:count]]
        return grouped

    @staticmethod
    def _slim_row(row: dict[str, Any], highlight_metric: str | None = None) -> dict[str, Any]:
        slim = {
            "research_job_id": row.get("research_job_id"),
            "strategy_id": row.get("strategy_id"),
            "market": row.get("market"),
            "time_horizon": row.get("time_horizon"),
            "composite_score": row.get("composite_score"),
            "entry_rule": row.get("entry_rule"),
            "exit_rule": row.get("exit_rule"),
        }
        for metric in RANK_METRICS:
            slim[metric] = row.get(metric)
        if highlight_metric:
            slim["rank_metric"] = highlight_metric
        return slim

    def _robust_strategies(self, completed: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_strategy: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in completed:
            by_strategy[str(row.get("strategy_id", ""))].append(row)

        shortlist: list[dict[str, Any]] = []
        for strategy_id, rows in by_strategy.items():
            if len(rows) < 8:
                continue

            sharpes = [float(r.get("sharpe") or 0) for r in rows]
            profits = [float(r.get("profit_pct") or 0) for r in rows]
            avg_sharpe = statistics.mean(sharpes)
            avg_profit = statistics.mean(profits)

            markets_positive = len({r.get("market") for r in rows if float(r.get("profit_pct") or 0) > 0})
            horizons_strong = len({r.get("time_horizon") for r in rows if float(r.get("sharpe") or 0) >= 0.5})
            markets_total = len({r.get("market") for r in rows})
            horizons_total = len({r.get("time_horizon") for r in rows})

            y20_rows = [r for r in rows if r.get("time_horizon") == "20Y"]
            sharpe_20y = (
                round(statistics.mean([float(r.get("sharpe") or 0) for r in y20_rows]), 4) if y20_rows else None
            )

            if markets_positive < 2 or horizons_strong < 2:
                continue
            if avg_sharpe < 0.4:
                continue
            if sharpe_20y is not None and sharpe_20y < 0.3:
                continue

            score = round(
                avg_sharpe * 0.35
                + (markets_positive / max(markets_total, 1)) * 0.25
                + (horizons_strong / max(horizons_total, 1)) * 0.25
                + (sharpe_20y or 0) * 0.15,
                4,
            )

            shortlist.append(
                {
                    "strategy_id": strategy_id,
                    "robustness_score": score,
                    "avg_sharpe": round(avg_sharpe, 4),
                    "avg_profit_pct": round(avg_profit, 4),
                    "markets_positive": markets_positive,
                    "markets_total": markets_total,
                    "horizons_strong": horizons_strong,
                    "horizons_total": horizons_total,
                    "sharpe_20y": sharpe_20y,
                    "completed_jobs": len(rows),
                    "entry_rule": rows[0].get("entry_rule"),
                    "exit_rule": rows[0].get("exit_rule"),
                }
            )

        shortlist.sort(key=lambda item: item["robustness_score"], reverse=True)
        return shortlist[:25]

    def _weak_strategies(self, completed: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_strategy: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in completed:
            by_strategy[str(row.get("strategy_id", ""))].append(row)

        weak: list[dict[str, Any]] = []
        for strategy_id, rows in by_strategy.items():
            if len(rows) < 4:
                continue

            sharpes = [float(r.get("sharpe") or 0) for r in rows]
            profits = [float(r.get("profit_pct") or 0) for r in rows]
            drawdowns = [float(r.get("max_drawdown") or 0) for r in rows]
            win_rates = [float(r.get("win_rate") or 0) for r in rows]

            avg_sharpe = statistics.mean(sharpes)
            avg_profit = statistics.mean(profits)
            avg_dd = statistics.mean(drawdowns)
            avg_win = statistics.mean(win_rates)
            sharpe_std = statistics.pstdev(sharpes) if len(sharpes) > 1 else 0.0

            negative_markets = len({r.get("market") for r in rows if float(r.get("profit_pct") or 0) < 0})

            is_weak = (
                avg_sharpe < 0.25
                or avg_profit < 0
                or avg_dd > 45
                or avg_win < 45
                or (sharpe_std > 1.0 and negative_markets >= 2)
            )
            if not is_weak:
                continue

            weak.append(
                {
                    "strategy_id": strategy_id,
                    "weakness_score": round(
                        (1.0 - min(max(avg_sharpe, -1), 1)) * 0.4
                        + min(avg_dd / 100.0, 1.0) * 0.3
                        + (1.0 - min(avg_win / 100.0, 1.0)) * 0.3,
                        4,
                    ),
                    "avg_sharpe": round(avg_sharpe, 4),
                    "avg_profit_pct": round(avg_profit, 4),
                    "avg_max_drawdown": round(avg_dd, 4),
                    "avg_win_rate": round(avg_win, 4),
                    "sharpe_std": round(sharpe_std, 4),
                    "negative_markets": negative_markets,
                    "completed_jobs": len(rows),
                    "entry_rule": rows[0].get("entry_rule"),
                    "exit_rule": rows[0].get("exit_rule"),
                }
            )

        weak.sort(key=lambda item: item["weakness_score"], reverse=True)
        return weak[:25]

    def _blocked_summary(self, blocked: list[dict[str, Any]]) -> dict[str, Any]:
        by_market: Counter[str] = Counter()
        by_horizon: Counter[str] = Counter()
        by_strategy: Counter[str] = Counter()
        by_reason: Counter[str] = Counter()

        for item in blocked:
            by_market[str(item.get("market", "UNKNOWN"))] += 1
            by_horizon[str(item.get("time_horizon", "UNKNOWN"))] += 1
            by_strategy[str(item.get("strategy_id", "UNKNOWN"))] += 1
            reason = str(item.get("block_reason") or "Unknown")
            by_reason[reason] += 1

        return {
            "total_blocked": len(blocked),
            "by_market": dict(by_market),
            "by_horizon": dict(by_horizon),
            "by_strategy": dict(by_strategy.most_common(20)),
            "by_block_reason": dict(by_reason),
        }

    def _strategy_families(
        self,
        completed: list[dict[str, Any]],
        robust: list[dict[str, Any]],
        strategy_meta: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        robust_ids = {item["strategy_id"] for item in robust[:15]}
        winner_rows = [row for row in completed if row.get("strategy_id") in robust_ids]
        if not winner_rows:
            winner_rows = sorted(completed, key=lambda r: r.get("composite_score", 0), reverse=True)[:100]

        def feature_stats(field: str) -> dict[str, dict[str, float | int]]:
            winner_values = [str(row.get(field) or "UNKNOWN") for row in winner_rows]
            all_values = [str(row.get(field) or "UNKNOWN") for row in completed]
            winner_counts = Counter(winner_values)
            all_counts = Counter(all_values)
            stats: dict[str, dict[str, float | int]] = {}
            total_winners = len(winner_rows)
            for name, win_count in winner_counts.items():
                total_in_population = all_counts.get(name, 0)
                stats[name] = {
                    "winner_count": win_count,
                    "total_in_winners": total_winners,
                    "population_count": total_in_population,
                    "winner_share": round(win_count / total_winners, 4) if total_winners else 0.0,
                    "population_share": round(total_in_population / len(completed), 4) if completed else 0.0,
                }
            return stats

        return {
            "winner_strategy_count": len(robust_ids) or min(15, len({r.get("strategy_id") for r in completed})),
            "entry": feature_stats("entry_rule"),
            "exit": feature_stats("exit_rule"),
            "market_filter": feature_stats("market_filter"),
            "holding_period": feature_stats("holding_period"),
            "risk_profile": feature_stats("risk_profile"),
            "strategy_meta_loaded": len(strategy_meta),
        }

    def _research_conclusions(
        self,
        execution: dict[str, Any],
        completed: list[dict[str, Any]],
        blocked: list[dict[str, Any]],
        robust: list[dict[str, Any]],
        weak: list[dict[str, Any]],
        blocked_summary: dict[str, Any],
        families: dict[str, Any],
    ) -> list[str]:
        conclusions: list[str] = []

        total = int(execution.get("jobs_total", 0))
        conclusions.append(
            f"Historical execution complete: {len(completed)}/{total} jobs produced metrics, "
            f"{len(blocked)} blocked, 0 failed."
        )

        if completed:
            avg_sharpe = statistics.mean(float(r.get("sharpe") or 0) for r in completed)
            avg_profit = statistics.mean(float(r.get("profit_pct") or 0) for r in completed)
            conclusions.append(
                f"Completed job averages: Sharpe {avg_sharpe:.4f}, profit_pct {avg_profit:.2f}."
            )

        if robust:
            top = robust[0]
            conclusions.append(
                f"Strongest robust candidate: {top['strategy_id']} "
                f"(score {top['robustness_score']}, 20Y Sharpe {top.get('sharpe_20y')})."
            )
        else:
            conclusions.append("No strategies met robustness criteria across markets and horizons.")

        if weak:
            conclusions.append(
                f"{len(weak)} strategies flagged as weak; worst cluster includes {weak[0]['strategy_id']}."
            )

        top_reason = next(iter((blocked_summary.get("by_block_reason") or {}).keys()), None)
        if top_reason:
            count = blocked_summary["by_block_reason"][top_reason]
            conclusions.append(
                f"Primary block reason ({count} jobs): {top_reason}"
            )

        entry_leaders = families.get("entry") or {}
        if entry_leaders:
            best_entry = max(entry_leaders.items(), key=lambda x: x[1].get("winner_share", 0))
            conclusions.append(
                f"Entry feature most common among winners: {best_entry[0]} "
                f"(winner_share {best_entry[1].get('winner_share')})."
            )

        y20 = [r for r in completed if r.get("time_horizon") == "20Y"]
        if y20:
            y20_sharpe = statistics.mean(float(r.get("sharpe") or 0) for r in y20)
            conclusions.append(f"20Y horizon average Sharpe: {y20_sharpe:.4f} across {len(y20)} completed jobs.")

        return conclusions

    def _recommended_next_action(
        self,
        robust: list[dict[str, Any]],
        weak: list[dict[str, Any]],
        blocked_summary: dict[str, Any],
    ) -> str:
        if robust:
            ids = ", ".join(item["strategy_id"] for item in robust[:5])
            return (
                f"Promote robust shortlist ({ids}) to paper-tracking review. "
                f"Retire or freeze weak strategies ({len(weak)} flagged). "
                f"Investigate {blocked_summary.get('total_blocked', 0)} blocked jobs — "
                "consider ASIA/low-trade cohort data expansion before re-run."
            )
        return (
            "No robust strategies identified — expand historical data coverage for blocked cohorts "
            "and re-run discovery bias review before paper promotion."
        )

    def _statistical_validation(
        self,
        completed: list[dict[str, Any]],
        robust: list[dict[str, Any]],
    ) -> dict[str, Any]:
        distributions: dict[str, dict[str, float | int | None]] = {}
        outliers: dict[str, dict[str, Any]] = {}
        for metric in OUTLIER_METRICS:
            values = [float(row.get(metric) or 0) for row in completed]
            distributions[metric] = _distribution_stats(values)
            outliers[metric] = self._detect_outliers(completed, metric, values)

        profit_values = [float(row.get("profit_pct") or 0) for row in completed]
        overall_mean = statistics.mean(profit_values) if profit_values else 0.0
        overall_median = statistics.median(profit_values) if profit_values else 0.0

        y20_rows = [row for row in completed if row.get("time_horizon") == "20Y"]
        non_y20_rows = [row for row in completed if row.get("time_horizon") != "20Y"]
        y20_profits = [float(row.get("profit_pct") or 0) for row in y20_rows]
        non_y20_profits = [float(row.get("profit_pct") or 0) for row in non_y20_rows]

        y20_mean = statistics.mean(y20_profits) if y20_profits else 0.0
        non_y20_mean = statistics.mean(non_y20_profits) if non_y20_profits else 0.0
        y20_median = statistics.median(y20_profits) if y20_profits else 0.0
        non_y20_median = statistics.median(non_y20_profits) if non_y20_profits else 0.0

        mean_outlier_driven = (
            overall_mean > 5 * max(overall_median, 0.01)
            and y20_mean > 5 * max(non_y20_mean, 0.01)
        )

        robust_independence = self._robust_ranking_independence(robust)

        return {
            "sample_size": len(completed),
            "distributions": distributions,
            "outliers": outliers,
            "profit_pct_central_tendency": {
                "arithmetic_mean": round(overall_mean, 4),
                "median": round(overall_median, 4),
                "reported_mean_matches": abs(overall_mean - 723.25) < 0.01,
                "mean_outlier_driven": mean_outlier_driven,
                "by_horizon": {
                    "20Y": {
                        "count": len(y20_profits),
                        "arithmetic_mean": round(y20_mean, 4),
                        "median": round(y20_median, 4),
                    },
                    "non_20Y": {
                        "count": len(non_y20_profits),
                        "arithmetic_mean": round(non_y20_mean, 4),
                        "median": round(non_y20_median, 4),
                    },
                },
            },
            "central_tendency_recommendation": (
                "Use median (and percentiles) as the primary summary for profit_pct in future reports; "
                "retain arithmetic mean only as a secondary, horizon-segmented statistic."
                if mean_outlier_driven
                else "Arithmetic mean and median are both representative; either may be used with percentiles."
            ),
            "robust_ranking_independence": robust_independence,
        }

    def _detect_outliers(
        self,
        completed: list[dict[str, Any]],
        metric: str,
        values: list[float],
    ) -> dict[str, Any]:
        if not values:
            return {"method": "IQR", "lower_fence": None, "upper_fence": None, "outlier_count": 0, "examples": []}

        q1 = _percentile(values, 25) or 0.0
        q3 = _percentile(values, 75) or 0.0
        iqr = q3 - q1
        lower_fence = q1 - 1.5 * iqr
        upper_fence = q3 + 1.5 * iqr

        outlier_rows: list[dict[str, Any]] = []
        for row, value in zip(completed, values):
            if value < lower_fence or value > upper_fence:
                outlier_rows.append(
                    {
                        "strategy_id": row.get("strategy_id"),
                        "market": row.get("market"),
                        "time_horizon": row.get("time_horizon"),
                        "value": round(value, 4),
                    }
                )

        outlier_rows.sort(key=lambda item: abs(float(item["value"])), reverse=True)
        return {
            "method": "IQR (1.5×)",
            "q1": round(q1, 4),
            "q3": round(q3, 4),
            "iqr": round(iqr, 4),
            "lower_fence": round(lower_fence, 4),
            "upper_fence": round(upper_fence, 4),
            "outlier_count": len(outlier_rows),
            "examples": outlier_rows[:10],
        }

    def _robust_ranking_independence(self, robust: list[dict[str, Any]]) -> dict[str, Any]:
        if not robust:
            return {
                "verified": False,
                "reason": "No robust strategies available for independence check.",
                "weights": ROBUST_SCORE_WEIGHTS,
                "rank_correlations": {},
                "dominant_component": None,
                "single_metric_dependent": False,
            }

        final_scores = [float(item.get("robustness_score") or 0) for item in robust]
        components = {
            "avg_sharpe": [float(item.get("avg_sharpe") or 0) for item in robust],
            "market_coverage": [
                float(item.get("markets_positive") or 0) / max(float(item.get("markets_total") or 1), 1)
                for item in robust
            ],
            "horizon_strength": [
                float(item.get("horizons_strong") or 0) / max(float(item.get("horizons_total") or 1), 1)
                for item in robust
            ],
            "sharpe_20y": [float(item.get("sharpe_20y") or 0) for item in robust],
        }

        rank_correlations: dict[str, float | None] = {}
        for name, values in components.items():
            rank_correlations[name] = _spearman(final_scores, values)

        abs_correlations = {
            name: abs(value) for name, value in rank_correlations.items() if value is not None
        }
        dominant = max(abs_correlations, key=abs_correlations.get) if abs_correlations else None
        dominant_rho = abs_correlations.get(dominant, 0.0) if dominant else 0.0
        single_metric_dependent = dominant_rho >= 0.95

        weighted_contributions: list[dict[str, float | str]] = []
        for item in robust[:10]:
            avg_sharpe = float(item.get("avg_sharpe") or 0)
            market_cov = float(item.get("markets_positive") or 0) / max(
                float(item.get("markets_total") or 1), 1
            )
            horizon_str = float(item.get("horizons_strong") or 0) / max(
                float(item.get("horizons_total") or 1), 1
            )
            sharpe_20y = float(item.get("sharpe_20y") or 0)
            parts = {
                "avg_sharpe": avg_sharpe * ROBUST_SCORE_WEIGHTS["avg_sharpe"],
                "market_coverage": market_cov * ROBUST_SCORE_WEIGHTS["market_coverage"],
                "horizon_strength": horizon_str * ROBUST_SCORE_WEIGHTS["horizon_strength"],
                "sharpe_20y": sharpe_20y * ROBUST_SCORE_WEIGHTS["sharpe_20y"],
            }
            total = sum(parts.values()) or 1.0
            weighted_contributions.append(
                {
                    "strategy_id": str(item.get("strategy_id")),
                    "largest_share_component": max(parts, key=parts.get),
                    "largest_share_pct": round(max(parts.values()) / total * 100, 2),
                }
            )

        return {
            "verified": not single_metric_dependent,
            "weights": ROBUST_SCORE_WEIGHTS,
            "rank_correlations_with_final_score": rank_correlations,
            "dominant_component": dominant,
            "dominant_abs_correlation": round(dominant_rho, 4),
            "single_metric_dependent": single_metric_dependent,
            "top10_largest_component_shares": weighted_contributions,
        }
