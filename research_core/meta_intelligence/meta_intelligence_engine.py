"""
Meta Intelligence Engine — Phase X Sprint X.2A

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Read-only observer above the Full Ecosystem Run. Consumes canonical JSON
reports only — does not replace or modify any existing decision engine.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from research_core.meta_intelligence.meta_intelligence_constants import (
    BASELINE_CANDIDATE_ID,
    CANONICAL_INPUTS,
    MIN_REQUIRED_INPUTS,
    PROTECTED_PATHS,
)
from research_core.meta_intelligence.meta_intelligence_report import (
    MetaIntelligenceReport,
    MetaIntelligenceVerdict,
)

logger = logging.getLogger(__name__)


class MetaIntelligenceEngine:
    """Observes canonical ecosystem reports and produces strategic observations."""

    def __init__(self, root: Path | str = Path(".")) -> None:
        self._root = Path(root)
        self._payloads: dict[str, dict[str, Any] | None] = {}
        self._sources_loaded: dict[str, bool] = {}
        self._warnings: list[str] = []

    def analyze(self) -> MetaIntelligenceReport:
        before_mtimes = self._snapshot_mtimes()
        self._load_all()
        after_mtimes = self._snapshot_mtimes()
        protected_ok = self._mtimes_unchanged(before_mtimes, after_mtimes)

        loaded_count = sum(1 for loaded in self._sources_loaded.values() if loaded)
        observations = self._build_observations()
        verdict = self._determine_verdict(loaded_count, observations)

        if not protected_ok:
            self._warnings.append("Protected file mtimes changed during meta intelligence analysis")

        return MetaIntelligenceReport(
            verdict=verdict,
            sources_loaded=dict(self._sources_loaded),
            sources_loaded_count=loaded_count,
            strategic_observations=observations,
            canonical_inputs_read=[
                name for name, loaded in self._sources_loaded.items() if loaded
            ],
            warnings=list(self._warnings),
            protected_files_unchanged=protected_ok,
        )

    def _load_all(self) -> None:
        for name, rel_path in CANONICAL_INPUTS.items():
            payload = self._load_json(rel_path)
            self._payloads[name] = payload
            self._sources_loaded[name] = payload is not None
            if payload is None:
                self._warnings.append(f"Missing canonical input: {rel_path.name}")

    def _build_observations(self) -> dict[str, Any]:
        runtime = self._payloads.get("runtime_foundation") or {}
        orchestrator = self._payloads.get("ecosystem_orchestrator") or {}
        daily_runner = self._payloads.get("strategy_evolution_daily_runner") or {}
        registry = self._payloads.get("candidate_strategy_registry") or {}
        ranking = self._payloads.get("continuous_strategy_ranking") or {}
        performance = self._payloads.get("strategic_performance_audit") or {}
        paper_tracking = self._payloads.get("paper_tracking_log") or {}
        governance = self._payloads.get("daily_intelligence_report") or {}

        rankings = self._list_items(ranking, "rankings")
        candidates = self._list_items(registry, "candidates")
        tracking_entries = self._list_items(paper_tracking, "entries")

        highest = self._highest_quality_strategy(rankings, daily_runner)
        weakest = self._weakest_strategy(rankings)
        promotion = self._promotion_candidates(
            tracking_entries, rankings, daily_runner
        )
        retirement = self._retirement_candidates(rankings, candidates, tracking_entries)

        return {
            "overall_ecosystem_confidence": self._overall_confidence(
                runtime, orchestrator, daily_runner, governance, rankings
            ),
            "highest_quality_strategy": highest,
            "weakest_strategy": weakest,
            "promotion_candidates": promotion,
            "retirement_candidates": retirement,
            "paper_validation_summary": self._paper_validation_summary(
                paper_tracking, tracking_entries, daily_runner
            ),
            "runtime_health_summary": self._runtime_health_summary(runtime),
            "governance_summary": self._governance_summary(governance),
            "system_maturity": self._system_maturity(
                runtime, orchestrator, daily_runner, performance
            ),
            "orchestrator_verdict": orchestrator.get("verdict"),
            "daily_runner_verdict": daily_runner.get("verdict"),
            "top_ranked_strategy_id": daily_runner.get("top_ranked_strategy_id")
            or ranking.get("pipeline_reference", {}).get("top_ranked_strategy_id")
            if isinstance(ranking.get("pipeline_reference"), dict)
            else daily_runner.get("top_ranked_strategy_id"),
            "top_ranked_strategy_score": daily_runner.get("top_ranked_strategy_score"),
            "promotion_review_candidate_id": daily_runner.get(
                "promotion_review_candidate_id"
            ),
        }

    def _overall_confidence(
        self,
        runtime: dict[str, Any],
        orchestrator: dict[str, Any],
        daily_runner: dict[str, Any],
        governance: dict[str, Any],
        ranking: dict[str, Any],
    ) -> dict[str, Any]:
        scores: list[float] = []
        factors: dict[str, float] = {}

        runtime_health = str(runtime.get("health_status", ""))
        if runtime_health == "HEALTHY":
            factors["runtime_health"] = 1.0
            scores.append(1.0)
        elif runtime_health:
            factors["runtime_health"] = 0.6
            scores.append(0.6)

        orch_verdict = str(orchestrator.get("verdict", ""))
        if "READY" in orch_verdict and "PARTIAL" not in orch_verdict:
            factors["orchestrator"] = 1.0
            scores.append(1.0)
        elif orch_verdict:
            factors["orchestrator"] = 0.5
            scores.append(0.5)

        runner_verdict = str(daily_runner.get("verdict", ""))
        if "READY" in runner_verdict and "PARTIAL" not in runner_verdict:
            factors["strategy_evolution"] = 1.0
            scores.append(1.0)
        elif runner_verdict:
            factors["strategy_evolution"] = 0.5
            scores.append(0.5)

        gov_health = governance.get("ecosystem_health") or {}
        if isinstance(gov_health, dict):
            overall = str(gov_health.get("overall_status", ""))
            if overall == "HEALTHY":
                factors["governance"] = 1.0
                scores.append(1.0)
            elif overall in {"WARNING", "ATTENTION"}:
                factors["governance"] = 0.5
                scores.append(0.5)

        top_score = daily_runner.get("top_ranked_strategy_score")
        if isinstance(top_score, (int, float)):
            factors["top_strategy_score"] = round(float(top_score), 4)
            scores.append(min(float(top_score), 1.0))

        loaded_ratio = sum(self._sources_loaded.values()) / max(len(CANONICAL_INPUTS), 1)
        factors["input_coverage"] = round(loaded_ratio, 4)
        scores.append(loaded_ratio)

        composite = round(sum(scores) / len(scores), 4) if scores else 0.0
        label = "HIGH" if composite >= 0.85 else "MODERATE" if composite >= 0.6 else "LOW"

        return {
            "composite_score": composite,
            "confidence_label": label,
            "factors": factors,
        }

    @staticmethod
    def _highest_quality_strategy(
        rankings: list[dict[str, Any]],
        daily_runner: dict[str, Any],
    ) -> dict[str, Any] | None:
        top_id = daily_runner.get("top_ranked_strategy_id")
        for item in rankings:
            if not isinstance(item, dict):
                continue
            if item.get("candidate_id") == top_id or item.get("rank") == 1:
                if item.get("candidate_id") == BASELINE_CANDIDATE_ID:
                    continue
                return {
                    "candidate_id": item.get("candidate_id"),
                    "ranking_score": item.get("ranking_score"),
                    "decision": item.get("decision"),
                    "validation_status": item.get("validation_status"),
                    "trades": item.get("trades"),
                }
        for item in rankings:
            if isinstance(item, dict) and item.get("candidate_id") != BASELINE_CANDIDATE_ID:
                return {
                    "candidate_id": item.get("candidate_id"),
                    "ranking_score": item.get("ranking_score"),
                    "decision": item.get("decision"),
                    "validation_status": item.get("validation_status"),
                    "trades": item.get("trades"),
                }
        return None

    @staticmethod
    def _weakest_strategy(rankings: list[dict[str, Any]]) -> dict[str, Any] | None:
        candidates = [
            item
            for item in rankings
            if isinstance(item, dict) and item.get("candidate_id") != BASELINE_CANDIDATE_ID
        ]
        if not candidates:
            return None
        weakest = min(
            candidates,
            key=lambda item: float(item.get("ranking_score") or 0),
        )
        return {
            "candidate_id": weakest.get("candidate_id"),
            "ranking_score": weakest.get("ranking_score"),
            "decision": weakest.get("decision"),
            "validation_status": weakest.get("validation_status"),
            "trades": weakest.get("trades"),
        }

    @staticmethod
    def _promotion_candidates(
        tracking_entries: list[dict[str, Any]],
        rankings: list[dict[str, Any]],
        daily_runner: dict[str, Any],
    ) -> list[dict[str, Any]]:
        review_id = daily_runner.get("promotion_review_candidate_id")
        ranking_by_id = {
            item.get("candidate_id"): item
            for item in rankings
            if isinstance(item, dict) and item.get("candidate_id")
        }
        results: list[dict[str, Any]] = []

        if review_id:
            rank_item = ranking_by_id.get(review_id, {})
            results.append({
                "candidate_id": review_id,
                "reason": "promotion_review_candidate_id set in daily runner",
                "ranking_score": rank_item.get("ranking_score"),
                "decision": rank_item.get("decision"),
            })

        for entry in tracking_entries:
            if not isinstance(entry, dict):
                continue
            cid = entry.get("candidate_id")
            if cid == BASELINE_CANDIDATE_ID:
                continue
            status = str(entry.get("tracking_status", ""))
            if status == "TRACKING_ACTIVE":
                rank_item = ranking_by_id.get(cid, {})
                results.append({
                    "candidate_id": cid,
                    "reason": "active paper tracking toward validation sample",
                    "current_trades": entry.get("current_trades"),
                    "trades_needed": entry.get("trades_needed"),
                    "ranking_score": rank_item.get("ranking_score"),
                    "decision": rank_item.get("decision"),
                })

        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for item in results:
            cid = str(item.get("candidate_id", ""))
            if cid and cid not in seen:
                seen.add(cid)
                unique.append(item)
        return unique

    @staticmethod
    def _retirement_candidates(
        rankings: list[dict[str, Any]],
        candidates: list[dict[str, Any]],
        tracking_entries: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        blocked_ids = {
            str(entry.get("candidate_id"))
            for entry in tracking_entries
            if isinstance(entry, dict)
            and str(entry.get("tracking_status", "")) == "BLOCKED"
        }
        results: list[dict[str, Any]] = []

        for item in rankings:
            if not isinstance(item, dict):
                continue
            cid = item.get("candidate_id")
            if cid == BASELINE_CANDIDATE_ID:
                continue
            decision = str(item.get("decision", ""))
            validation = str(item.get("validation_status", ""))
            score = float(item.get("ranking_score") or 0)
            delta = float(item.get("delta_vs_baseline_total_pnl") or 0)

            if cid in blocked_ids:
                results.append({
                    "candidate_id": cid,
                    "reason": "paper tracking BLOCKED — insufficient sample",
                    "ranking_score": score,
                })
            elif decision == "INSUFFICIENT_SAMPLE" and delta < 0:
                results.append({
                    "candidate_id": cid,
                    "reason": "insufficient sample with negative baseline delta",
                    "ranking_score": score,
                })
            elif score < 0.3 and validation != "PAPER_TRACKING":
                results.append({
                    "candidate_id": cid,
                    "reason": "low ranking score — monitor for retirement",
                    "ranking_score": score,
                })

        for item in candidates:
            if not isinstance(item, dict):
                continue
            cid = item.get("candidate_id")
            if cid == BASELINE_CANDIDATE_ID:
                continue
            readiness = str(item.get("promotion_readiness", ""))
            if readiness == "NOT_READY" and cid not in {r["candidate_id"] for r in results}:
                metrics = item.get("metrics") or {}
                if isinstance(metrics, dict):
                    pf = float(metrics.get("profit_factor") or 0)
                    if pf < 1.0:
                        results.append({
                            "candidate_id": cid,
                            "reason": "NOT_READY with profit factor below 1.0",
                            "profit_factor": pf,
                        })

        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for item in results:
            cid = str(item.get("candidate_id", ""))
            if cid and cid not in seen:
                seen.add(cid)
                unique.append(item)
        return unique

    @staticmethod
    def _paper_validation_summary(
        paper_tracking: dict[str, Any],
        entries: list[dict[str, Any]],
        daily_runner: dict[str, Any],
    ) -> dict[str, Any]:
        active = sum(
            1
            for entry in entries
            if isinstance(entry, dict)
            and entry.get("tracking_status") == "TRACKING_ACTIVE"
        )
        blocked = sum(
            1
            for entry in entries
            if isinstance(entry, dict)
            and entry.get("tracking_status") == "BLOCKED"
        )
        needs = daily_runner.get("paper_tracking_needs") or []
        if not isinstance(needs, list):
            needs = []
        return {
            "verdict": paper_tracking.get("verdict"),
            "tracking_entries": len(entries),
            "tracking_active": active,
            "tracking_blocked": blocked,
            "paper_tracking_needs": len(needs),
        }

    @staticmethod
    def _runtime_health_summary(runtime: dict[str, Any]) -> dict[str, Any]:
        issues = runtime.get("health_issues") or []
        if not isinstance(issues, list):
            issues = []
        return {
            "verdict": runtime.get("verdict"),
            "health_status": runtime.get("health_status"),
            "health_issue_count": len(issues),
            "health_issues": issues[:5],
            "state_sources_loaded": sum(
                1
                for loaded in (runtime.get("loaded_state_sources") or {}).values()
                if loaded
            )
            if isinstance(runtime.get("loaded_state_sources"), dict)
            else None,
        }

    @staticmethod
    def _governance_summary(governance: dict[str, Any]) -> dict[str, Any]:
        eco = governance.get("ecosystem_health") or {}
        modern = governance.get("governance_modern_inputs") or {}
        return {
            "report_date": governance.get("report_date"),
            "overall_status": eco.get("overall_status") if isinstance(eco, dict) else None,
            "critical_issues_count": len(governance.get("critical_issues") or []),
            "modern_inputs_registered": modern.get("governance_modern_inputs_registered")
            if isinstance(modern, dict)
            else None,
            "strategy_evolution_source": modern.get("governance_strategy_evolution_source")
            if isinstance(modern, dict)
            else None,
        }

    def _system_maturity(
        self,
        runtime: dict[str, Any],
        orchestrator: dict[str, Any],
        daily_runner: dict[str, Any],
        performance: dict[str, Any],
    ) -> dict[str, Any]:
        loaded = sum(self._sources_loaded.values())
        total = len(CANONICAL_INPUTS)
        coverage = loaded / total if total else 0.0

        ready_flags = [
            "READY" in str(runtime.get("verdict", "")),
            "READY" in str(orchestrator.get("verdict", "")),
            "READY" in str(daily_runner.get("verdict", "")),
            performance.get("schema") == "tae_strategic_performance_audit",
        ]
        ready_count = sum(1 for flag in ready_flags if flag)

        if coverage >= 0.95 and ready_count >= 4:
            level = "MATURE"
        elif coverage >= 0.75 and ready_count >= 3:
            level = "OPERATIONAL"
        else:
            level = "EMERGING"

        return {
            "maturity_level": level,
            "input_coverage_pct": round(coverage * 100, 1),
            "pipeline_ready_signals": ready_count,
            "meta_layer_role": "OBSERVER_ONLY",
        }

    def _determine_verdict(
        self,
        loaded_count: int,
        observations: dict[str, Any],
    ) -> MetaIntelligenceVerdict:
        if loaded_count < MIN_REQUIRED_INPUTS:
            return MetaIntelligenceVerdict.META_INTELLIGENCE_INSUFFICIENT_DATA

        if self._warnings or loaded_count < len(CANONICAL_INPUTS):
            return MetaIntelligenceVerdict.META_INTELLIGENCE_READY_WITH_WARNINGS

        confidence = observations.get("overall_ecosystem_confidence") or {}
        if confidence.get("confidence_label") == "LOW":
            return MetaIntelligenceVerdict.META_INTELLIGENCE_READY_WITH_WARNINGS

        return MetaIntelligenceVerdict.META_INTELLIGENCE_READY

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
