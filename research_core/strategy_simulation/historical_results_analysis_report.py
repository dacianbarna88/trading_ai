"""
Historical Results Analysis report — Phase X Sprint X.5

ANALYSIS_ONLY | RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

DEFAULT_JSON_PATH = Path("tae_historical_results_analysis.json")
DEFAULT_TXT_PATH = Path("tae_historical_results_analysis.txt")
EXECUTION_INPUT_PATH = Path("tae_historical_execution.json")
EXECUTION_TXT_PATH = Path("tae_historical_execution.txt")
DISCOVERY_INPUT_PATH = Path("tae_strategy_discovery.json")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_historical_results_analysis"
ANALYSIS_SAFETY_BANNER = (
    "ANALYSIS_ONLY | RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE"
)


class HistoricalResultsAnalysisVerdict(str, Enum):
    HISTORICAL_RESULTS_ANALYSIS_READY = "HISTORICAL_RESULTS_ANALYSIS_READY"
    HISTORICAL_RESULTS_ANALYSIS_READY_WITH_WARNINGS = (
        "HISTORICAL_RESULTS_ANALYSIS_READY_WITH_WARNINGS"
    )
    HISTORICAL_RESULTS_ANALYSIS_INPUT_MISSING = "HISTORICAL_RESULTS_ANALYSIS_INPUT_MISSING"


@dataclass
class HistoricalResultsAnalysisReport:
    verdict: HistoricalResultsAnalysisVerdict
    jobs_total: int
    jobs_completed: int
    jobs_blocked: int
    jobs_failed: int
    top_20_global_results: list[dict[str, Any]]
    top_10_per_horizon: dict[str, list[dict[str, Any]]]
    top_10_per_market: dict[str, list[dict[str, Any]]]
    global_rankings: dict[str, list[dict[str, Any]]]
    robust_strategy_shortlist: list[dict[str, Any]]
    weak_strategy_shortlist: list[dict[str, Any]]
    blocked_jobs_summary: dict[str, Any]
    strategy_families: dict[str, Any]
    research_conclusions: list[str]
    recommended_next_action: str
    statistical_appendix: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)
    safety_mode: str = ANALYSIS_SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "verdict": self.verdict.value,
            "jobs_total": self.jobs_total,
            "jobs_completed": self.jobs_completed,
            "jobs_blocked": self.jobs_blocked,
            "jobs_failed": self.jobs_failed,
            "top_20_global_results": list(self.top_20_global_results),
            "top_10_per_horizon": {
                horizon: list(items) for horizon, items in self.top_10_per_horizon.items()
            },
            "top_10_per_market": {
                market: list(items) for market, items in self.top_10_per_market.items()
            },
            "global_rankings": {
                metric: list(items) for metric, items in self.global_rankings.items()
            },
            "robust_strategy_shortlist": list(self.robust_strategy_shortlist),
            "weak_strategy_shortlist": list(self.weak_strategy_shortlist),
            "blocked_jobs_summary": dict(self.blocked_jobs_summary),
            "strategy_families": dict(self.strategy_families),
            "research_conclusions": list(self.research_conclusions),
            "recommended_next_action": self.recommended_next_action,
            "warnings": list(self.warnings),
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE HISTORICAL RESULTS ANALYSIS — SPRINT X.5 =====",
            "",
            f"Safety banner: {self.safety_mode}",
            f"Verdict: {self.verdict.value}",
            f"Generated: {self.generated_at.isoformat()}",
            "",
            "===== EXECUTION SUMMARY =====",
            f"  Jobs total: {self.jobs_total}",
            f"  Completed: {self.jobs_completed}",
            f"  Blocked: {self.jobs_blocked}",
            f"  Failed: {self.jobs_failed}",
            "",
            "===== TOP 20 GLOBAL RESULTS (composite score) =====",
        ]

        for index, item in enumerate(self.top_20_global_results, start=1):
            lines.append(
                f"  {index:2d}. [{item.get('research_job_id')}] {item.get('strategy_id')} "
                f"{item.get('market')}/{item.get('time_horizon')} "
                f"profit={item.get('profit_pct')} sharpe={item.get('sharpe')} "
                f"dd={item.get('max_drawdown')}"
            )

        lines.extend(["", "===== TOP 10 PER HORIZON (by Sharpe) ====="])
        for horizon, items in sorted(self.top_10_per_horizon.items()):
            lines.append(f"  --- {horizon} ---")
            for item in items[:10]:
                lines.append(
                    f"    {item.get('strategy_id')} {item.get('market')} "
                    f"sharpe={item.get('sharpe')} profit={item.get('profit_pct')}"
                )

        lines.extend(["", "===== TOP 10 PER MARKET (by Sharpe) ====="])
        for market, items in sorted(self.top_10_per_market.items()):
            lines.append(f"  --- {market} ---")
            for item in items[:10]:
                lines.append(
                    f"    {item.get('strategy_id')} {item.get('time_horizon')} "
                    f"sharpe={item.get('sharpe')} profit={item.get('profit_pct')}"
                )

        lines.extend(["", "===== ROBUST STRATEGY SHORTLIST ====="])
        for item in self.robust_strategy_shortlist[:15]:
            lines.append(
                f"  {item.get('strategy_id')} score={item.get('robustness_score')} "
                f"markets={item.get('markets_positive')}/{item.get('markets_total')} "
                f"horizons={item.get('horizons_strong')}/{item.get('horizons_total')} "
                f"20Y_sharpe={item.get('sharpe_20y')}"
            )

        lines.extend(["", "===== WEAK STRATEGY SHORTLIST ====="])
        for item in self.weak_strategy_shortlist[:15]:
            lines.append(
                f"  {item.get('strategy_id')} avg_sharpe={item.get('avg_sharpe')} "
                f"avg_profit={item.get('avg_profit_pct')} avg_dd={item.get('avg_max_drawdown')}"
            )

        lines.extend(["", "===== BLOCKED JOBS SUMMARY ====="])
        blocked = self.blocked_jobs_summary
        lines.append(f"  Total blocked: {blocked.get('total_blocked', 0)}")
        for label, key in (
            ("By market", "by_market"),
            ("By horizon", "by_horizon"),
            ("By block reason", "by_block_reason"),
        ):
            lines.append(f"  {label}:")
            for name, count in sorted((blocked.get(key) or {}).items()):
                lines.append(f"    {name}: {count}")

        lines.extend(["", "===== STRATEGY FAMILIES (winners vs all) ====="])
        families = self.strategy_families
        for feature_type in ("entry", "exit", "market_filter", "holding_period", "risk_profile"):
            section = families.get(feature_type, {})
            lines.append(f"  {feature_type}:")
            for name, stats in sorted(section.items(), key=lambda x: -x[1].get("winner_share", 0))[:5]:
                lines.append(
                    f"    {name}: winner_share={stats.get('winner_share')} "
                    f"count={stats.get('winner_count')}/{stats.get('total_in_winners')}"
                )

        lines.extend(["", "===== RESEARCH CONCLUSIONS ====="])
        for conclusion in self.research_conclusions:
            lines.append(f"  • {conclusion}")

        lines.extend(["", "===== RECOMMENDED NEXT ACTION =====", f"  {self.recommended_next_action}"])

        if self.warnings:
            lines.extend(["", "===== WARNINGS ====="])
            for warning in self.warnings:
                lines.append(f"  • {warning}")

        if self.statistical_appendix:
            lines.extend(self._format_statistical_appendix(self.statistical_appendix))

        return "\n".join(lines)

    @staticmethod
    def _format_statistical_appendix(appendix: dict[str, Any]) -> list[str]:
        lines = [
            "",
            "===== STATISTICAL APPENDIX — FINAL VALIDATION =====",
            f"  Sample size (completed jobs): {appendix.get('sample_size', 0)}",
            "",
            "  --- profit_pct distribution ---",
        ]

        def append_distribution(label: str, stats: dict[str, Any]) -> None:
            lines.append(f"  {label}:")
            for key in ("count", "mean", "median", "p10", "p25", "p75", "p90", "min", "max"):
                lines.append(f"    {key}: {stats.get(key)}")

        distributions = appendix.get("distributions") or {}
        for metric in ("profit_pct", "sharpe", "max_drawdown"):
            stats = distributions.get(metric) or {}
            if metric == "profit_pct":
                append_distribution("profit_pct", stats)
            else:
                lines.extend(["", f"  --- {metric} distribution ---"])
                append_distribution(metric, stats)

        lines.extend(["", "  --- Outlier detection (IQR 1.5×) ---"])
        for metric in ("profit_pct", "sharpe", "max_drawdown"):
            detail = (appendix.get("outliers") or {}).get(metric) or {}
            lines.append(
                f"  {metric}: {detail.get('outlier_count', 0)} outliers "
                f"(fence [{detail.get('lower_fence')}, {detail.get('upper_fence')}])"
            )
            for example in detail.get("examples") or []:
                lines.append(
                    f"    {example.get('strategy_id')} {example.get('market')}/"
                    f"{example.get('time_horizon')} value={example.get('value')}"
                )

        central = appendix.get("profit_pct_central_tendency") or {}
        by_horizon = central.get("by_horizon") or {}
        y20 = by_horizon.get("20Y") or {}
        non_y20 = by_horizon.get("non_20Y") or {}

        lines.extend(
            [
                "",
                "  --- profit_pct central tendency validation ---",
                f"  Arithmetic mean (all completed): {central.get('arithmetic_mean')}",
                f"  Median (all completed): {central.get('median')}",
                f"  Reported mean 723.25 matches: {central.get('reported_mean_matches')}",
                f"  Mean heavily outlier-driven: {central.get('mean_outlier_driven')}",
                f"  20Y cohort (n={y20.get('count')}): mean={y20.get('arithmetic_mean')} median={y20.get('median')}",
                f"  Non-20Y cohort (n={non_y20.get('count')}): mean={non_y20.get('arithmetic_mean')} "
                f"median={non_y20.get('median')}",
                "",
                "  --- Central tendency recommendation ---",
                f"  {appendix.get('central_tendency_recommendation')}",
            ]
        )

        independence = appendix.get("robust_ranking_independence") or {}
        lines.extend(
            [
                "",
                "  --- Robust ranking independence ---",
                f"  Verified multi-metric (not single-metric dependent): {independence.get('verified')}",
                "  Score weights:",
            ]
        )
        for component, weight in (independence.get("weights") or {}).items():
            lines.append(f"    {component}: {weight}")
        lines.append("  Spearman rank correlation with final robustness_score:")
        for component, rho in (independence.get("rank_correlations_with_final_score") or {}).items():
            lines.append(f"    {component}: {rho}")
        lines.append(
            f"  Dominant component: {independence.get('dominant_component')} "
            f"(|rho|={independence.get('dominant_abs_correlation')})"
        )
        lines.append(f"  Single-metric dependent (|rho|>=0.95): {independence.get('single_metric_dependent')}")
        for item in independence.get("top10_largest_component_shares") or []:
            lines.append(
                f"    {item.get('strategy_id')}: largest share "
                f"{item.get('largest_share_component')} ({item.get('largest_share_pct')}%)"
            )

        return lines


class HistoricalResultsAnalysisReportStore:
    def __init__(
        self,
        json_path: Path | None = None,
        txt_path: Path | None = None,
    ) -> None:
        self._json_path = json_path or DEFAULT_JSON_PATH
        self._txt_path = txt_path or DEFAULT_TXT_PATH

    def persist(self, report: HistoricalResultsAnalysisReport) -> tuple[Path, Path]:
        self._json_path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        self._txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return self._json_path, self._txt_path
