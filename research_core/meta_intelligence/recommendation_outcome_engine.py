"""
Recommendation Outcome Learning Engine — Phase X Sprint X.2C

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | LEARNING_ONLY

Evaluates historical Meta Evolution recommendations against accumulated
canonical evidence. Does not execute or modify strategy decisions.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.meta_intelligence.meta_intelligence_constants import (
    BASELINE_CANDIDATE_ID,
    PROTECTED_PATHS,
)
from research_core.meta_intelligence.recommendation_outcome_report import (
    REGISTRY_JSON_PATH,
    RecommendationOutcomeEntry,
    RecommendationOutcomeReport,
    RecommendationOutcomeStatus,
    RecommendationOutcomeVerdict,
    load_outcome_registry,
    persist_outcome_registry,
)

logger = logging.getLogger(__name__)

OUTCOME_CANONICAL_INPUTS: dict[str, Path] = {
    "meta_evolution": Path("tae_meta_evolution.json"),
    "meta_intelligence": Path("tae_meta_intelligence.json"),
    "candidate_strategy_registry": Path("tae_candidate_strategy_registry.json"),
    "continuous_strategy_ranking": Path("tae_continuous_strategy_ranking.json"),
    "parallel_paper_validation": Path("tae_parallel_paper_validation.json"),
    "paper_tracking_log": Path("tae_paper_tracking_log.json"),
    "strategic_performance_audit": Path("tae_strategic_performance_audit.json"),
    "daily_intelligence_report": Path("tae_daily_intelligence_report.json"),
    "runtime_foundation": Path("tae_runtime_foundation.json"),
}

MIN_REQUIRED_INPUTS = 7
FRESH_RECOMMENDATION_HOURS = 1.0


class RecommendationOutcomeEngine:
    """Learns from Meta Evolution recommendation outcomes — read-only."""

    def __init__(self, root: Path | str = Path(".")) -> None:
        self._root = Path(root)
        self._payloads: dict[str, dict[str, Any] | None] = {}
        self._sources_loaded: dict[str, bool] = {}
        self._warnings: list[str] = []
        self._context: dict[str, Any] = {}

    def analyze(self) -> RecommendationOutcomeReport:
        before_mtimes = self._snapshot_mtimes()
        self._load_all()
        self._build_context()
        after_mtimes = self._snapshot_mtimes()
        protected_ok = self._mtimes_unchanged(before_mtimes, after_mtimes)

        evolution = self._payloads.get("meta_evolution") or {}
        recommendations = evolution.get("recommendations") or []
        if not isinstance(recommendations, list):
            recommendations = []

        registry_path = self._root / REGISTRY_JSON_PATH
        registry = load_outcome_registry(registry_path)
        registry["evaluation_cycles"] = int(registry.get("evaluation_cycles") or 0) + 1
        entries_map: dict[str, dict[str, Any]] = dict(registry.get("entries") or {})

        now = datetime.now(timezone.utc)
        history: list[RecommendationOutcomeEntry] = []

        for rec in recommendations:
            if not isinstance(rec, dict):
                continue
            rec_key = self._registry_key(rec)
            existing = entries_map.get(rec_key)
            if existing is None:
                existing = {
                    "recommendation_id": rec.get("recommendation_id"),
                    "category": rec.get("category"),
                    "target_strategy_or_module": rec.get("target_strategy_or_module"),
                    "issued_at": evolution.get("generated_at") or now.isoformat(),
                    "original_confidence_score": rec.get("confidence_score", 0.0),
                    "evidence_sources": rec.get("evidence_sources") or [],
                    "baseline_metrics": self._capture_metrics(rec),
                    "evaluation_count": 0,
                }
            existing["evaluation_count"] = int(existing.get("evaluation_count") or 0) + 1
            current_metrics = self._capture_metrics(rec)
            outcome_entry = self._evaluate_recommendation(rec, existing, current_metrics, now)
            existing["last_evaluated_at"] = now.isoformat()
            existing["last_outcome"] = outcome_entry.outcome
            existing["last_quality"] = outcome_entry.recommendation_quality
            existing["current_metrics"] = current_metrics
            entries_map[rec_key] = existing
            history.append(outcome_entry)

        registry["entries"] = entries_map
        registry["last_evaluated_at"] = now.isoformat()
        persist_outcome_registry(registry_path, registry)

        loaded_count = sum(1 for loaded in self._sources_loaded.values() if loaded)
        stats = self._compute_statistics(history)
        category_accuracy = self._category_accuracy(history)
        learning_metrics = self._learning_metrics(history, stats)
        aging = self._recommendation_aging(history)
        false_count = sum(
            1 for entry in history if entry.outcome == RecommendationOutcomeStatus.FAILED.value
        )
        trend = self._improvement_trend(history, registry)
        verdict = self._determine_verdict(
            loaded_count,
            int(registry.get("evaluation_cycles") or 0),
            history,
        )

        if not protected_ok:
            self._warnings.append(
                "Protected file mtimes changed during outcome learning analysis"
            )

        avg_confidence = (
            sum(entry.original_confidence_score for entry in history) / len(history)
            if history
            else 0.0
        )

        return RecommendationOutcomeReport(
            verdict=verdict,
            recommendation_history=history,
            recommendation_statistics=stats,
            category_accuracy=category_accuracy,
            average_recommendation_confidence=avg_confidence,
            improvement_trend=trend,
            false_recommendation_count=false_count,
            recommendation_aging=aging,
            learning_metrics=learning_metrics,
            sources_loaded=dict(self._sources_loaded),
            sources_loaded_count=loaded_count,
            registry_evaluation_cycles=int(registry.get("evaluation_cycles") or 0),
            warnings=list(self._warnings),
            protected_files_unchanged=protected_ok,
        )

    def _load_all(self) -> None:
        for name, rel_path in OUTCOME_CANONICAL_INPUTS.items():
            payload = self._load_json(rel_path)
            self._payloads[name] = payload
            self._sources_loaded[name] = payload is not None
            if payload is None:
                self._warnings.append(f"Missing canonical input: {rel_path.name}")

    def _build_context(self) -> None:
        ranking = self._payloads.get("continuous_strategy_ranking") or {}
        registry = self._payloads.get("candidate_strategy_registry") or {}
        validation = self._payloads.get("parallel_paper_validation") or {}
        paper_tracking = self._payloads.get("paper_tracking_log") or {}
        performance = self._payloads.get("strategic_performance_audit") or {}
        governance = self._payloads.get("daily_intelligence_report") or {}
        runtime = self._payloads.get("runtime_foundation") or {}
        meta = self._payloads.get("meta_intelligence") or {}

        rankings = {
            item.get("candidate_id"): item
            for item in self._list_items(ranking, "rankings")
            if item.get("candidate_id")
        }
        validations = {
            item.get("candidate_id"): item
            for item in self._list_items(validation, "validations")
            if item.get("candidate_id")
        }
        tracking = {
            item.get("candidate_id"): item
            for item in self._list_items(paper_tracking, "entries")
            if item.get("candidate_id")
        }
        candidates = [
            item for item in self._list_items(registry, "candidates")
            if item.get("candidate_id") != BASELINE_CANDIDATE_ID
        ]

        trade_quality = performance.get("trade_quality") or {}
        gov_health = governance.get("ecosystem_health") or {}

        self._context = {
            "rankings": rankings,
            "validations": validations,
            "tracking": tracking,
            "candidate_count": len(candidates),
            "profit_factor": trade_quality.get("profit_factor")
            if isinstance(trade_quality, dict)
            else None,
            "critical_issues_count": len(governance.get("critical_issues") or []),
            "governance_overall": gov_health.get("overall_status")
            if isinstance(gov_health, dict)
            else None,
            "runtime_health": runtime.get("health_status"),
            "runtime_issue_count": len(runtime.get("health_issues") or []),
            "meta_confidence": (
                (meta.get("strategic_observations") or {})
                .get("overall_ecosystem_confidence", {})
                .get("composite_score")
            ),
        }

    def _capture_metrics(self, rec: dict[str, Any]) -> dict[str, Any]:
        target = str(rec.get("target_strategy_or_module", ""))
        ctx = self._context
        metrics: dict[str, Any] = {"target": target}

        if target in ctx.get("rankings", {}):
            rank_item = ctx["rankings"][target]
            metrics.update({
                "ranking_score": rank_item.get("ranking_score"),
                "validation_status": rank_item.get("validation_status"),
                "decision": rank_item.get("decision"),
                "trades": rank_item.get("trades"),
                "delta_vs_baseline_total_pnl": rank_item.get("delta_vs_baseline_total_pnl"),
            })
        if target in ctx.get("tracking", {}):
            track_item = ctx["tracking"][target]
            metrics.update({
                "tracking_status": track_item.get("tracking_status"),
                "current_trades": track_item.get("current_trades"),
                "trades_needed": track_item.get("trades_needed"),
            })
        if target == BASELINE_CANDIDATE_ID:
            metrics["profit_factor"] = ctx.get("profit_factor")
        if target == "governance/research_pipeline":
            metrics["critical_issues_count"] = ctx.get("critical_issues_count")
            metrics["governance_overall"] = ctx.get("governance_overall")
        if target == "simulation_lab/strategy_evolution":
            metrics["candidate_count"] = ctx.get("candidate_count")
        if target == "ecosystem":
            metrics["runtime_health"] = ctx.get("runtime_health")
        if target == "runtime/state_sources":
            metrics["runtime_issue_count"] = ctx.get("runtime_issue_count")
        if target == "canonical_reports":
            metrics["sources_loaded_count"] = sum(self._sources_loaded.values())

        return metrics

    def _evaluate_recommendation(
        self,
        rec: dict[str, Any],
        existing: dict[str, Any],
        current_metrics: dict[str, Any],
        now: datetime,
    ) -> RecommendationOutcomeEntry:
        category = str(rec.get("category", ""))
        target = str(rec.get("target_strategy_or_module", ""))
        issued_at = self._parse_dt(existing.get("issued_at"))
        age_days = max((now - issued_at).total_seconds() / 86400, 0.0)
        age_hours = age_days * 24
        baseline = existing.get("baseline_metrics") or {}
        eval_count = int(existing.get("evaluation_count") or 1)

        if age_hours < FRESH_RECOMMENDATION_HOURS and eval_count <= 1:
            outcome = RecommendationOutcomeStatus.NO_EVIDENCE_YET
            rationale = "Recommendation recently issued — insufficient elapsed time for outcome learning."
        elif not self._has_evaluable_metrics(baseline, current_metrics, category):
            outcome = RecommendationOutcomeStatus.INSUFFICIENT_DATA
            rationale = "Required canonical metrics unavailable for outcome evaluation."
        else:
            outcome, rationale = self._outcome_for_category(
                category, target, baseline, current_metrics, age_days, eval_count
            )

        evidence_strength = self._evidence_strength(rec, current_metrics)
        quality = self._recommendation_quality(outcome, evidence_strength, rec)
        learning_conf = self._learning_confidence(outcome, evidence_strength, eval_count, age_days)

        return RecommendationOutcomeEntry(
            recommendation_id=str(rec.get("recommendation_id", "")),
            category=category,
            target_strategy_or_module=target,
            outcome=outcome.value,
            original_confidence_score=float(rec.get("confidence_score") or 0.0),
            recommendation_quality=quality,
            evidence_strength=evidence_strength,
            learning_confidence=learning_conf,
            issued_at=existing.get("issued_at", now.isoformat()),
            last_evaluated_at=now.isoformat(),
            recommendation_age_days=age_days,
            baseline_metrics=baseline,
            current_metrics=current_metrics,
            outcome_rationale=rationale,
            evidence_sources=list(rec.get("evidence_sources") or []),
            evaluation_count=eval_count,
        )

    def _outcome_for_category(
        self,
        category: str,
        target: str,
        baseline: dict[str, Any],
        current: dict[str, Any],
        age_days: float,
        eval_count: int,
    ) -> tuple[RecommendationOutcomeStatus, str]:
        if category == "CONTINUE_PAPER_TRACKING":
            return self._outcome_continue_tracking(baseline, current, age_days)
        if category == "RETIRE_OR_FREEZE_CANDIDATE":
            return self._outcome_retire_freeze(baseline, current)
        if category == "INVESTIGATE_UNDERPERFORMANCE":
            return self._outcome_investigate(baseline, current, target)
        if category == "IMPROVE_DATA_QUALITY":
            return self._outcome_improve_data_quality(baseline, current, target)
        if category == "LAUNCH_NEW_EXPERIMENT":
            return self._outcome_launch_experiment(baseline, current, age_days)
        if category == "PROMOTE_CANDIDATE":
            return self._outcome_promote_candidate(baseline, current)
        if category == "NO_ACTION":
            return self._outcome_no_action(baseline, current)
        return (
            RecommendationOutcomeStatus.INSUFFICIENT_DATA,
            f"Unknown category {category} — cannot evaluate outcome.",
        )

    @staticmethod
    def _outcome_continue_tracking(
        baseline: dict[str, Any],
        current: dict[str, Any],
        age_days: float,
    ) -> tuple[RecommendationOutcomeStatus, str]:
        status = str(current.get("tracking_status", ""))
        base_trades = baseline.get("current_trades") or baseline.get("trades") or 0
        cur_trades = current.get("current_trades") or current.get("trades") or 0
        base_score = float(baseline.get("ranking_score") or 0)
        cur_score = float(current.get("ranking_score") or 0)

        if status == "BLOCKED":
            return (
                RecommendationOutcomeStatus.FAILED,
                "Tracking became BLOCKED — continuing paper tracking recommendation not validated.",
            )
        if cur_trades > base_trades and cur_score >= base_score * 0.95:
            return (
                RecommendationOutcomeStatus.SUCCESS,
                f"Paper tracking progressed ({base_trades}→{cur_trades} trades) with stable ranking score.",
            )
        if cur_trades > base_trades or cur_score >= base_score:
            return (
                RecommendationOutcomeStatus.PARTIAL_SUCCESS,
                "Paper tracking shows partial progress toward validation sample.",
            )
        if age_days < 1.0:
            return (
                RecommendationOutcomeStatus.NO_EVIDENCE_YET,
                "Tracking active but observation window too short for learning verdict.",
            )
        return (
            RecommendationOutcomeStatus.PARTIAL_SUCCESS,
            "Tracking continues without measurable trade-count progress yet.",
        )

    @staticmethod
    def _outcome_retire_freeze(
        baseline: dict[str, Any],
        current: dict[str, Any],
    ) -> tuple[RecommendationOutcomeStatus, str]:
        status = str(current.get("tracking_status", ""))
        base_score = float(baseline.get("ranking_score") or 0)
        cur_score = float(current.get("ranking_score") or 0)

        if status == "BLOCKED" and cur_score <= base_score:
            return (
                RecommendationOutcomeStatus.SUCCESS,
                "Candidate remains blocked with weak ranking — freeze/retire advice validated.",
            )
        if cur_score > base_score * 1.2:
            return (
                RecommendationOutcomeStatus.FAILED,
                "Ranking improved materially — premature freeze recommendation not validated.",
            )
        return (
            RecommendationOutcomeStatus.PARTIAL_SUCCESS,
            "Candidate still weak but not fully resolved — monitor for retirement decision.",
        )

    @staticmethod
    def _outcome_investigate(
        baseline: dict[str, Any],
        current: dict[str, Any],
        target: str,
    ) -> tuple[RecommendationOutcomeStatus, str]:
        if target == BASELINE_CANDIDATE_ID:
            base_pf = float(baseline.get("profit_factor") or 0)
            cur_pf = float(current.get("profit_factor") or 0)
            if cur_pf < 1.0:
                return (
                    RecommendationOutcomeStatus.SUCCESS,
                    f"Baseline profit factor still below 1.0 ({cur_pf:.4f}) — investigation warranted.",
                )
            if cur_pf > base_pf * 1.1:
                return (
                    RecommendationOutcomeStatus.PARTIAL_SUCCESS,
                    "Baseline profit factor improved — investigation may have prompted corrective review.",
                )
            return (
                RecommendationOutcomeStatus.PARTIAL_SUCCESS,
                "Baseline metrics mixed — investigation still reasonable.",
            )

        base_delta = float(baseline.get("delta_vs_baseline_total_pnl") or 0)
        cur_delta = float(current.get("delta_vs_baseline_total_pnl") or 0)
        if cur_delta < base_delta:
            return (
                RecommendationOutcomeStatus.SUCCESS,
                "Underperformance persisted or worsened — investigate recommendation validated.",
            )
        if cur_delta > 0:
            return (
                RecommendationOutcomeStatus.PARTIAL_SUCCESS,
                "Candidate improved vs baseline since recommendation — investigation partially validated.",
            )
        return (
            RecommendationOutcomeStatus.PARTIAL_SUCCESS,
            "Underperformance signal present — continue monitoring.",
        )

    @staticmethod
    def _outcome_improve_data_quality(
        baseline: dict[str, Any],
        current: dict[str, Any],
        target: str,
    ) -> tuple[RecommendationOutcomeStatus, str]:
        if target == "governance/research_pipeline":
            base_issues = int(baseline.get("critical_issues_count") or 99)
            cur_issues = int(current.get("critical_issues_count") or 99)
            if cur_issues < base_issues:
                return (
                    RecommendationOutcomeStatus.SUCCESS,
                    f"Critical issues reduced ({base_issues}→{cur_issues}) — data quality improving.",
                )
            if cur_issues == base_issues and current.get("governance_overall") == "HEALTHY":
                return (
                    RecommendationOutcomeStatus.PARTIAL_SUCCESS,
                    "Issue count stable with healthy governance — partial progress.",
                )
            return (
                RecommendationOutcomeStatus.PARTIAL_SUCCESS,
                "Data quality gaps remain — recommendation still relevant.",
            )

        base_issues = int(baseline.get("runtime_issue_count") or 0)
        cur_issues = int(current.get("runtime_issue_count") or 0)
        if cur_issues < base_issues:
            return (
                RecommendationOutcomeStatus.SUCCESS,
                f"Runtime issues reduced ({base_issues}→{cur_issues}).",
            )
        if cur_issues == 0:
            return (
                RecommendationOutcomeStatus.SUCCESS,
                "Runtime health clean — canonical reports sufficient.",
            )
        return (
            RecommendationOutcomeStatus.PARTIAL_SUCCESS,
            "Runtime issues persist — refresh canonical pipeline recommended.",
        )

    @staticmethod
    def _outcome_launch_experiment(
        baseline: dict[str, Any],
        current: dict[str, Any],
        age_days: float,
    ) -> tuple[RecommendationOutcomeStatus, str]:
        base_count = int(baseline.get("candidate_count") or 0)
        cur_count = int(current.get("candidate_count") or 0)
        if cur_count > base_count:
            return (
                RecommendationOutcomeStatus.SUCCESS,
                f"Candidate registry expanded ({base_count}→{cur_count}) — experiment breadth increased.",
            )
        if age_days < 2.0:
            return (
                RecommendationOutcomeStatus.NO_EVIDENCE_YET,
                "Too early to assess new experiment launch outcomes.",
            )
        return (
            RecommendationOutcomeStatus.PARTIAL_SUCCESS,
            "No new candidates yet — experiment launch may still be pending human review.",
        )

    @staticmethod
    def _outcome_promote_candidate(
        baseline: dict[str, Any],
        current: dict[str, Any],
    ) -> tuple[RecommendationOutcomeStatus, str]:
        cur_trades = int(current.get("current_trades") or current.get("trades") or 0)
        cur_score = float(current.get("ranking_score") or 0)
        if cur_trades >= 20 and cur_score >= 0.85:
            return (
                RecommendationOutcomeStatus.SUCCESS,
                "Candidate reached promotion sample threshold with strong score.",
            )
        if cur_score >= 0.8:
            return (
                RecommendationOutcomeStatus.PARTIAL_SUCCESS,
                "Candidate strong but sample threshold not yet met for promotion.",
            )
        return (
            RecommendationOutcomeStatus.NO_EVIDENCE_YET,
            "Promotion review pending — insufficient post-recommendation evidence.",
        )

    @staticmethod
    def _outcome_no_action(
        baseline: dict[str, Any],
        current: dict[str, Any],
    ) -> tuple[RecommendationOutcomeStatus, str]:
        if str(current.get("runtime_health", baseline.get("runtime_health"))) == "HEALTHY":
            return (
                RecommendationOutcomeStatus.SUCCESS,
                "Ecosystem remained stable — no action recommendation validated.",
            )
        return (
            RecommendationOutcomeStatus.PARTIAL_SUCCESS,
            "Ecosystem stable with minor signals — no action partially validated.",
        )

    @staticmethod
    def _evidence_strength(rec: dict[str, Any], current_metrics: dict[str, Any]) -> float:
        sources = rec.get("evidence_sources") or []
        source_score = min(len(sources) / 3.0, 1.0) if sources else 0.3
        metric_fields = sum(
            1 for value in current_metrics.values() if value is not None
        )
        metric_score = min(metric_fields / 5.0, 1.0)
        return round(source_score * 0.5 + metric_score * 0.5, 4)

    @staticmethod
    def _recommendation_quality(
        outcome: RecommendationOutcomeStatus,
        evidence_strength: float,
        rec: dict[str, Any],
    ) -> float:
        outcome_scores = {
            RecommendationOutcomeStatus.SUCCESS: 1.0,
            RecommendationOutcomeStatus.PARTIAL_SUCCESS: 0.65,
            RecommendationOutcomeStatus.NO_EVIDENCE_YET: 0.45,
            RecommendationOutcomeStatus.FAILED: 0.15,
            RecommendationOutcomeStatus.INSUFFICIENT_DATA: 0.25,
        }
        base = outcome_scores.get(outcome, 0.3)
        confidence = float(rec.get("confidence_score") or 0.5)
        return round(base * 0.6 + evidence_strength * 0.25 + confidence * 0.15, 4)

    @staticmethod
    def _learning_confidence(
        outcome: RecommendationOutcomeStatus,
        evidence_strength: float,
        eval_count: int,
        age_days: float,
    ) -> float:
        eval_factor = min(eval_count / 3.0, 1.0)
        age_factor = min(age_days / 7.0, 1.0)
        if outcome == RecommendationOutcomeStatus.NO_EVIDENCE_YET:
            age_factor *= 0.3
        return round(evidence_strength * 0.5 + eval_factor * 0.3 + age_factor * 0.2, 4)

    @staticmethod
    def _compute_statistics(history: list[RecommendationOutcomeEntry]) -> dict[str, Any]:
        outcome_counts: dict[str, int] = {}
        for entry in history:
            outcome_counts[entry.outcome] = outcome_counts.get(entry.outcome, 0) + 1
        qualities = [entry.recommendation_quality for entry in history]
        return {
            "total_evaluated": len(history),
            "outcome_counts": outcome_counts,
            "average_quality": round(sum(qualities) / len(qualities), 4) if qualities else 0.0,
            "average_learning_confidence": round(
                sum(entry.learning_confidence for entry in history) / len(history), 4
            )
            if history
            else 0.0,
        }

    @staticmethod
    def _category_accuracy(history: list[RecommendationOutcomeEntry]) -> dict[str, float]:
        by_category: dict[str, list[float]] = {}
        for entry in history:
            by_category.setdefault(entry.category, []).append(entry.recommendation_quality)
        return {
            category: round(sum(scores) / len(scores), 4)
            for category, scores in by_category.items()
            if scores
        }

    @staticmethod
    def _learning_metrics(
        history: list[RecommendationOutcomeEntry],
        stats: dict[str, Any],
    ) -> dict[str, Any]:
        if not history:
            return {
                "recommendation_quality": 0.0,
                "recommendation_accuracy": 0.0,
                "evidence_strength": 0.0,
                "learning_confidence": 0.0,
                "historical_recommendation_score": 0.0,
            }
        success_count = sum(
            1
            for entry in history
            if entry.outcome
            in {
                RecommendationOutcomeStatus.SUCCESS.value,
                RecommendationOutcomeStatus.PARTIAL_SUCCESS.value,
            }
        )
        accuracy = success_count / len(history)
        avg_quality = float(stats.get("average_quality") or 0)
        avg_evidence = sum(entry.evidence_strength for entry in history) / len(history)
        avg_learning = float(stats.get("average_learning_confidence") or 0)
        historical_score = round(avg_quality * 0.4 + accuracy * 0.35 + avg_learning * 0.25, 4)
        return {
            "recommendation_quality": round(avg_quality, 4),
            "recommendation_accuracy": round(accuracy, 4),
            "evidence_strength": round(avg_evidence, 4),
            "learning_confidence": round(avg_learning, 4),
            "historical_recommendation_score": historical_score,
        }

    @staticmethod
    def _recommendation_aging(history: list[RecommendationOutcomeEntry]) -> dict[str, Any]:
        if not history:
            return {"average_age_days": 0.0, "oldest_days": 0.0, "newest_days": 0.0}
        ages = [entry.recommendation_age_days for entry in history]
        return {
            "average_age_days": round(sum(ages) / len(ages), 2),
            "oldest_days": round(max(ages), 2),
            "newest_days": round(min(ages), 2),
        }

    @staticmethod
    def _improvement_trend(
        history: list[RecommendationOutcomeEntry],
        registry: dict[str, Any],
    ) -> str:
        cycles = int(registry.get("evaluation_cycles") or 0)
        if cycles <= 1:
            return "BASELINE_ESTABLISHED"
        avg_quality = (
            sum(entry.recommendation_quality for entry in history) / len(history)
            if history
            else 0.0
        )
        if avg_quality >= 0.75:
            return "IMPROVING"
        if avg_quality >= 0.5:
            return "STABLE"
        return "NEEDS_CALIBRATION"

    def _determine_verdict(
        self,
        loaded_count: int,
        cycles: int,
        history: list[RecommendationOutcomeEntry],
    ) -> RecommendationOutcomeVerdict:
        if not history or loaded_count < MIN_REQUIRED_INPUTS:
            return RecommendationOutcomeVerdict.RECOMMENDATION_OUTCOME_INSUFFICIENT_HISTORY

        no_evidence_ratio = sum(
            1
            for entry in history
            if entry.outcome == RecommendationOutcomeStatus.NO_EVIDENCE_YET.value
        ) / len(history)

        if cycles <= 1:
            if self._warnings or loaded_count < len(OUTCOME_CANONICAL_INPUTS):
                return RecommendationOutcomeVerdict.RECOMMENDATION_OUTCOME_READY_WITH_WARNINGS
            return RecommendationOutcomeVerdict.RECOMMENDATION_OUTCOME_READY_WITH_WARNINGS

        if self._warnings or loaded_count < len(OUTCOME_CANONICAL_INPUTS):
            return RecommendationOutcomeVerdict.RECOMMENDATION_OUTCOME_READY_WITH_WARNINGS

        if no_evidence_ratio >= 0.5:
            return RecommendationOutcomeVerdict.RECOMMENDATION_OUTCOME_READY_WITH_WARNINGS

        return RecommendationOutcomeVerdict.RECOMMENDATION_OUTCOME_READY

    @staticmethod
    def _registry_key(rec: dict[str, Any]) -> str:
        return "|".join([
            str(rec.get("recommendation_id", "")),
            str(rec.get("category", "")),
            str(rec.get("target_strategy_or_module", "")),
        ])

    @staticmethod
    def _has_evaluable_metrics(
        baseline: dict[str, Any],
        current: dict[str, Any],
        category: str,
    ) -> bool:
        combined = {**baseline, **current}
        if category in {
            "CONTINUE_PAPER_TRACKING",
            "RETIRE_OR_FREEZE_CANDIDATE",
            "PROMOTE_CANDIDATE",
            "INVESTIGATE_UNDERPERFORMANCE",
        }:
            return any(
                combined.get(key) is not None
                for key in (
                    "ranking_score",
                    "tracking_status",
                    "current_trades",
                    "trades",
                    "profit_factor",
                    "delta_vs_baseline_total_pnl",
                )
            )
        if category == "IMPROVE_DATA_QUALITY":
            return any(
                combined.get(key) is not None
                for key in ("critical_issues_count", "runtime_issue_count", "governance_overall")
            )
        if category == "LAUNCH_NEW_EXPERIMENT":
            return combined.get("candidate_count") is not None
        if category == "NO_ACTION":
            return combined.get("runtime_health") is not None
        return bool(combined)

    @staticmethod
    def _parse_dt(value: str | None) -> datetime:
        if not value:
            return datetime.now(timezone.utc)
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(timezone.utc)

    @staticmethod
    def _list_items(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
        items = payload.get(key, [])
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict)]

    def _load_json(self, path: Path) -> dict[str, Any] | None:
        full = self._root / path
        if not full.is_file():
            return None
        try:
            payload = json.loads(full.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read %s: %s", path, exc)
            return None
        return payload if isinstance(payload, dict) else None

    def _snapshot_mtimes(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for path in PROTECTED_PATHS:
            full = self._root / path
            if full.is_file():
                out[str(path)] = full.stat().st_mtime
        return out

    @staticmethod
    def _mtimes_unchanged(before: dict[str, float], after: dict[str, float]) -> bool:
        for key, mtime in before.items():
            if key not in after or after[key] != mtime:
                return False
        return True
