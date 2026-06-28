"""
Ecosystem State — Phase IX C2

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Central read-only state snapshot from canonical JSON outputs.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

STATE_SOURCES: dict[str, str] = {
    "ecosystem": "tae_ecosystem_orchestrator.json",
    "interconnection": "tae_systemic_interconnection_map.json",
    "evidence": "tae_evidence_engine_report.json",
    "strategy_evolution": "tae_strategy_evolution_daily_runner.json",
    "promotion": "tae_strategy_promotion_gate.json",
    "paper_tracking": "tae_paper_tracking_log.json",
    "strategic_performance": "tae_strategic_performance_audit.json",
    "accounting_integrity": "tae_accounting_integrity_audit.json",
    "performance_pipeline": "tae_performance_pipeline_report.json",
    "registry": "tae_candidate_strategy_registry.json",
    "ranking": "tae_continuous_strategy_ranking.json",
    "validation": "tae_parallel_paper_validation.json",
    "inventory": "tae_ecosystem_inventory_audit.json",
}


@dataclass
class EcosystemState:
    sections: dict[str, dict[str, Any] | None]
    sources_loaded: dict[str, bool]
    verdicts: dict[str, str | None]
    top_ranked_strategy_id: str | None = None
    top_ranked_strategy_score: float | None = None
    promotion_review_candidate_id: str | None = None
    paper_tracking_needs: list[dict[str, Any]] = field(default_factory=list)
    missing_connections: list[str] = field(default_factory=list)
    conflict_warnings: list[dict[str, Any]] = field(default_factory=list)
    evidence_items_count: int = 0
    strategy_candidates_count: int = 0
    performance_pipeline_reference: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "sections": {
                key: section if section is not None else None
                for key, section in self.sections.items()
            },
            "sources_loaded": dict(self.sources_loaded),
            "verdicts": dict(self.verdicts),
            "top_ranked_strategy_id": self.top_ranked_strategy_id,
            "top_ranked_strategy_score": self.top_ranked_strategy_score,
            "promotion_review_candidate_id": self.promotion_review_candidate_id,
            "paper_tracking_needs": list(self.paper_tracking_needs),
            "missing_connections": list(self.missing_connections),
            "conflict_warnings": list(self.conflict_warnings),
            "evidence_items_count": self.evidence_items_count,
            "strategy_candidates_count": self.strategy_candidates_count,
            "performance_pipeline_reference": self.performance_pipeline_reference,
            "health": self.sections.get("health"),
            "broker_readiness": self.sections.get("broker_readiness"),
        }


class EcosystemStateLoader:
    def __init__(self, root: Path | str = Path(".")) -> None:
        self._root = Path(root)

    def load(self) -> EcosystemState:
        payloads: dict[str, dict[str, Any] | None] = {}
        sources_loaded: dict[str, bool] = {}

        for section, filename in STATE_SOURCES.items():
            path = self._root / filename
            payload = self._load_json(path)
            payloads[section] = payload
            sources_loaded[filename] = payload is not None

        sections: dict[str, dict[str, Any] | None] = {
            key: payloads.get(key) for key in STATE_SOURCES
        }
        sections["health"] = None
        sections["broker_readiness"] = {
            "status": "NOT_APPLICABLE",
            "reason": "NO_BROKER | NO_EXECUTION — paper-only runtime",
        }

        orchestrator = payloads.get("ecosystem") or {}
        daily_runner = payloads.get("strategy_evolution") or {}
        promotion = payloads.get("promotion") or {}
        paper_tracking = payloads.get("paper_tracking") or {}
        evidence = payloads.get("evidence") or {}
        registry = payloads.get("registry") or {}
        interconnection = payloads.get("interconnection") or {}
        inventory = payloads.get("inventory") or {}
        strategic = payloads.get("strategic_performance") or {}
        accounting_integrity = payloads.get("accounting_integrity") or {}
        performance_pipeline = payloads.get("performance_pipeline") or {}

        try:
            from research_core.performance.performance_pipeline_integration import (
                pipeline_reference,
            )

            performance_pipeline_reference = pipeline_reference(self._root)
        except ImportError:
            performance_pipeline_reference = None

        top_id = (
            orchestrator.get("top_ranked_strategy_id")
            or daily_runner.get("top_ranked_strategy_id")
        )
        top_score = (
            orchestrator.get("top_ranked_strategy_score")
            or daily_runner.get("top_ranked_strategy_score")
        )
        review_candidate = (
            promotion.get("review_candidate_id")
            or orchestrator.get("promotion_review_candidate_id")
            or daily_runner.get("promotion_review_candidate_id")
        )

        paper_needs = self._paper_tracking_needs(orchestrator, paper_tracking)
        missing = self._merge_missing(inventory, orchestrator, interconnection)
        missing = self._filter_resolved_performance_missing(missing, daily_runner)
        conflicts = interconnection.get("conflict_warnings", [])
        if not isinstance(conflicts, list):
            conflicts = []

        evidence_items = evidence.get("evidence_items", [])
        candidates = registry.get("candidates", [])

        verdicts = {
            "ecosystem": orchestrator.get("verdict"),
            "interconnection": interconnection.get("verdict"),
            "evidence": evidence.get("verdict"),
            "strategy_evolution": daily_runner.get("verdict"),
            "promotion": promotion.get("verdict"),
            "paper_tracking": paper_tracking.get("verdict"),
            "registry": registry.get("verdict"),
            "ranking": (payloads.get("ranking") or {}).get("verdict"),
            "validation": (payloads.get("validation") or {}).get("verdict"),
            "inventory": inventory.get("verdict"),
            "strategic_performance": (
                "STRATEGIC_PERFORMANCE_AUDIT_AVAILABLE"
                if strategic.get("schema") == "tae_strategic_performance_audit"
                else None
            ),
            "accounting_integrity": (
                "ACCOUNTING_INTEGRITY_AUDIT_AVAILABLE"
                if accounting_integrity.get("schema") == "tae_accounting_integrity_audit"
                else None
            ),
            "performance_pipeline": performance_pipeline.get("verdict"),
        }

        return EcosystemState(
            sections=sections,
            sources_loaded=sources_loaded,
            verdicts=verdicts,
            top_ranked_strategy_id=str(top_id) if top_id else None,
            top_ranked_strategy_score=float(top_score) if top_score is not None else None,
            promotion_review_candidate_id=str(review_candidate) if review_candidate else None,
            paper_tracking_needs=paper_needs,
            missing_connections=missing,
            conflict_warnings=[c for c in conflicts if isinstance(c, dict)],
            evidence_items_count=len(evidence_items) if isinstance(evidence_items, list) else 0,
            strategy_candidates_count=len(candidates) if isinstance(candidates, list) else 0,
            performance_pipeline_reference=performance_pipeline_reference,
        )

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any] | None:
        if not path.is_file():
            logger.warning("State source not found: %s", path)
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read %s: %s", path, exc)
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _paper_tracking_needs(
        orchestrator: dict[str, Any],
        paper_tracking: dict[str, Any],
    ) -> list[dict[str, Any]]:
        summary = orchestrator.get("paper_tracking_summary", {})
        entries = summary.get("entries") if isinstance(summary, dict) else None
        if isinstance(entries, list) and entries:
            return [e for e in entries if isinstance(e, dict)]
        tracking_entries = paper_tracking.get("entries", [])
        if not isinstance(tracking_entries, list):
            return []
        return [
            {
                "candidate_id": e.get("candidate_id"),
                "tracking_status": e.get("tracking_status"),
                "current_trades": e.get("current_trades"),
                "trades_needed": e.get("trades_needed"),
                "tracking_note": e.get("tracking_note"),
            }
            for e in tracking_entries
            if isinstance(e, dict) and e.get("tracking_status") != "BASELINE_REFERENCE"
        ]

    @staticmethod
    def _merge_missing(*payloads: dict[str, Any]) -> list[str]:
        missing: list[str] = []
        for payload in payloads:
            items = payload.get("missing_connections", [])
            if isinstance(items, list):
                for item in items:
                    text = str(item)
                    if text not in missing:
                        missing.append(text)
        return missing

    def _filter_resolved_performance_missing(
        self,
        missing: list[str],
        daily_runner: dict[str, Any],
    ) -> list[str]:
        try:
            from research_core.performance.performance_pipeline_integration import (
                MISSING_CONNECTION_PERFORMANCE_DAILY_RUNNER,
                is_performance_pipeline_resolved,
            )
        except ImportError:
            return missing
        if not is_performance_pipeline_resolved(self._root, daily_runner or None):
            return missing
        return [item for item in missing if item != MISSING_CONNECTION_PERFORMANCE_DAILY_RUNNER]
