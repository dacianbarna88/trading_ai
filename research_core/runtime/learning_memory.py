"""
Runtime Learning Memory — Phase IX C2

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.runtime.ecosystem_state import EcosystemState
from research_core.runtime.runtime_health import HealthStatus, RuntimeHealth, RuntimeHealthReport
from research_core.strategy_evolution.candidate_report import SAFETY_BANNER

LEARNING_JSON_PATH = Path("tae_runtime_learning_memory.json")
LEARNING_TXT_PATH = Path("tae_runtime_learning_memory.txt")


@dataclass
class LearningMemorySnapshot:
    top_ranked_strategy: str | None
    top_ranking_score: float | None
    promotion_review_candidate: str | None
    paper_tracking_needs: list[dict[str, Any]]
    missing_connections: list[str]
    conflict_warnings: list[dict[str, Any]]
    evidence_items_count: int
    strategy_candidates_count: int
    lessons_learned: list[str]
    health_status: str
    health_issues: list[str]
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": SAFETY_BANNER,
            "top_ranked_strategy": self.top_ranked_strategy,
            "top_ranking_score": self.top_ranking_score,
            "promotion_review_candidate": self.promotion_review_candidate,
            "paper_tracking_needs": list(self.paper_tracking_needs),
            "missing_connections": list(self.missing_connections),
            "conflict_warnings": list(self.conflict_warnings),
            "evidence_items_count": self.evidence_items_count,
            "strategy_candidates_count": self.strategy_candidates_count,
            "lessons_learned": list(self.lessons_learned),
            "health_status": self.health_status,
            "health_issues": list(self.health_issues),
            "health_issue_count": len(self.health_issues),
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE RUNTIME LEARNING MEMORY =====",
            "",
            f"Siguranță: {SAFETY_BANNER}",
            f"Generat: {self.generated_at.isoformat()}",
            f"Health: {self.health_status}",
            f"Issues: {len(self.health_issues)}",
            "",
            f"Top ranked strategy: {self.top_ranked_strategy or 'N/A'}",
        ]
        if self.top_ranking_score is not None:
            lines.append(f"Top ranking score: {self.top_ranking_score:.4f}")
        lines.append(
            f"Promotion review candidate: {self.promotion_review_candidate or 'None'}"
        )
        lines.extend([
            f"Evidence items: {self.evidence_items_count}",
            f"Strategy candidates: {self.strategy_candidates_count}",
            "",
            "Paper tracking needs:",
        ])
        for need in self.paper_tracking_needs:
            lines.append(
                f"  {need.get('candidate_id')}: need={need.get('trades_needed')} "
                f"({need.get('tracking_status')})"
            )
        lines.extend(["", "Health issues:"])
        if self.health_issues:
            for issue in self.health_issues:
                lines.append(f"  - {issue}")
        else:
            lines.append("  none")
        lines.extend(["", "Lessons learned:"])
        for lesson in self.lessons_learned:
            lines.append(f"  - {lesson}")
        lines.append("")
        return "\n".join(lines)


class LearningMemory:
    def build(
        self,
        state: EcosystemState,
        health: RuntimeHealthReport,
    ) -> LearningMemorySnapshot:
        return LearningMemorySnapshot(
            top_ranked_strategy=state.top_ranked_strategy_id,
            top_ranking_score=state.top_ranked_strategy_score,
            promotion_review_candidate=state.promotion_review_candidate_id,
            paper_tracking_needs=list(state.paper_tracking_needs),
            missing_connections=list(state.missing_connections),
            conflict_warnings=list(state.conflict_warnings),
            evidence_items_count=state.evidence_items_count,
            strategy_candidates_count=state.strategy_candidates_count,
            lessons_learned=self._lessons_learned(state, health),
            health_status=health.overall_status,
            health_issues=list(health.issues),
        )

    @staticmethod
    def _lessons_learned(state: EcosystemState, health: RuntimeHealthReport) -> list[str]:
        lessons: list[str] = []
        if state.top_ranked_strategy_id:
            lessons.append(
                f"{state.top_ranked_strategy_id} is the current top-ranked paper strategy."
            )
        for need in state.paper_tracking_needs:
            cid = need.get("candidate_id")
            needed = need.get("trades_needed")
            if cid and needed:
                lessons.append(f"{cid} needs {needed} more trade(s) before promotion review.")
        if not state.promotion_review_candidate_id:
            lessons.append("No strategy is currently eligible for promotion review.")
        if state.missing_connections:
            lessons.append(
                f"Ecosystem has {len(state.missing_connections)} documented missing connections."
            )
        if state.conflict_warnings:
            lessons.append(
                f"{len(state.conflict_warnings)} conflict warnings require canonical precedence."
            )
        lessons.append(
            "Use Orchestrator as daily entry point; Evidence Engine and Strategy Evolution "
            "Daily Runner are canonical internal pipelines."
        )
        if health.overall_status != HealthStatus.HEALTHY.value:
            if RuntimeHealth.integration_backlog_only(health.issues):
                lessons.append(
                    f"Runtime health is {health.overall_status} due to "
                    f"{len(health.issues)} known integration backlog item(s)."
                )
            else:
                lessons.append(
                    f"Runtime health is {health.overall_status} — review stale/missing outputs."
                )
        return lessons

    def persist(self, snapshot: LearningMemorySnapshot) -> tuple[Path, Path]:
        LEARNING_JSON_PATH.write_text(
            json.dumps(snapshot.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        LEARNING_TXT_PATH.write_text(snapshot.format_text() + "\n", encoding="utf-8")
        return LEARNING_JSON_PATH, LEARNING_TXT_PATH
