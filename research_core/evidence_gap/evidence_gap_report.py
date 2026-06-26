"""
Evidence gap report model — Phase VI Sprint B3

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Research roadmap from evidence history — planning only, no implementation.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.evidence_history.evidence_record import ImplementationReadiness

logger = logging.getLogger(__name__)

DEFAULT_GAP_JSON_PATH = Path("tae_evidence_gap_report.json")
DEFAULT_GAP_TXT_PATH = Path("tae_evidence_gap_report.txt")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_evidence_gap_report"


class GapCategory(str, Enum):
    REGIONAL_VALIDATION = "REGIONAL_VALIDATION"
    REGIME_VALIDATION = "REGIME_VALIDATION"
    HORIZON_VALIDATION = "HORIZON_VALIDATION"
    EXPERIMENT_REPEAT = "EXPERIMENT_REPEAT"
    LEARNING_CONFIRMATION = "LEARNING_CONFIRMATION"
    PATCH_REVIEW = "PATCH_REVIEW"
    SANDBOX_PREPARATION = "SANDBOX_PREPARATION"


@dataclass
class MissingEvidenceItem:
    gap_id: str
    category: GapCategory
    label: str
    description: str
    estimated_information_gain: float = 0.0
    blocks_readiness: bool = True

    def __post_init__(self) -> None:
        if isinstance(self.category, str):
            self.category = GapCategory(self.category)

    @property
    def fingerprint(self) -> str:
        return f"{self.category.value}:{self.label}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "gap_id": self.gap_id,
            "category": self.category.value,
            "label": self.label,
            "description": self.description,
            "estimated_information_gain": round(self.estimated_information_gain, 2),
            "blocks_readiness": self.blocks_readiness,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MissingEvidenceItem | None:
        try:
            cat = str(data.get("category", GapCategory.REGIONAL_VALIDATION.value))
            try:
                category = GapCategory(cat)
            except ValueError:
                category = GapCategory.REGIONAL_VALIDATION
            return cls(
                gap_id=str(data.get("gap_id", "")),
                category=category,
                label=str(data.get("label", "")),
                description=str(data.get("description", "")),
                estimated_information_gain=float(data.get("estimated_information_gain", 0)),
                blocks_readiness=bool(data.get("blocks_readiness", True)),
            )
        except (TypeError, ValueError):
            return None


@dataclass
class ResearchAction:
    action_id: str
    category: GapCategory
    action: str
    priority_rank: int
    estimated_effort: str = "MEDIUM"
    expected_information_gain: float = 0.0

    def __post_init__(self) -> None:
        if isinstance(self.category, str):
            self.category = GapCategory(self.category)

    @property
    def fingerprint(self) -> str:
        return f"{self.category.value}:{self.action}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "category": self.category.value,
            "action": self.action,
            "priority_rank": self.priority_rank,
            "estimated_effort": self.estimated_effort,
            "expected_information_gain": round(self.expected_information_gain, 2),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResearchAction | None:
        try:
            cat = str(data.get("category", GapCategory.REGIONAL_VALIDATION.value))
            try:
                category = GapCategory(cat)
            except ValueError:
                category = GapCategory.REGIONAL_VALIDATION
            return cls(
                action_id=str(data.get("action_id", "")),
                category=category,
                action=str(data.get("action", "")),
                priority_rank=int(data.get("priority_rank", 0)),
                estimated_effort=str(data.get("estimated_effort", "MEDIUM")),
                expected_information_gain=float(data.get("expected_information_gain", 0)),
            )
        except (TypeError, ValueError):
            return None


@dataclass
class CandidateGapAnalysis:
    candidate_id: str
    title: str
    current_score: float
    current_readiness: ImplementationReadiness
    current_confidence: float
    missing_evidence: list[MissingEvidenceItem]
    research_actions: list[ResearchAction]
    estimated_information_gain: float
    estimated_confidence_after_completion: float
    estimated_readiness_after_completion: ImplementationReadiness
    blocking_items: list[str]
    recommended_next_step: str
    priority: int
    human_review_required: bool
    implementation_allowed: bool = False
    safety_mode: str = RESEARCH_SAFETY_BANNER
    remaining_work_summary: str = ""
    last_analyzed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if isinstance(self.current_readiness, str):
            self.current_readiness = ImplementationReadiness(self.current_readiness)
        if isinstance(self.estimated_readiness_after_completion, str):
            self.estimated_readiness_after_completion = ImplementationReadiness(
                self.estimated_readiness_after_completion
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "title": self.title,
            "current_score": round(self.current_score, 2),
            "current_readiness": self.current_readiness.value,
            "current_confidence": round(self.current_confidence, 2),
            "missing_evidence": [g.to_dict() for g in self.missing_evidence],
            "research_actions": [a.to_dict() for a in self.research_actions],
            "estimated_information_gain": round(self.estimated_information_gain, 2),
            "estimated_confidence_after_completion": round(
                self.estimated_confidence_after_completion, 2
            ),
            "estimated_readiness_after_completion": (
                self.estimated_readiness_after_completion.value
            ),
            "blocking_items": list(self.blocking_items),
            "recommended_next_step": self.recommended_next_step,
            "priority": self.priority,
            "human_review_required": self.human_review_required,
            "implementation_allowed": self.implementation_allowed,
            "remaining_work_summary": self.remaining_work_summary,
            "safety_mode": self.safety_mode,
            "last_analyzed": self.last_analyzed.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CandidateGapAnalysis | None:
        try:
            gaps: list[MissingEvidenceItem] = []
            for item in data.get("missing_evidence", []):
                if isinstance(item, dict):
                    gap = MissingEvidenceItem.from_dict(item)
                    if gap is not None:
                        gaps.append(gap)

            actions: list[ResearchAction] = []
            for item in data.get("research_actions", []):
                if isinstance(item, dict):
                    action = ResearchAction.from_dict(item)
                    if action is not None:
                        actions.append(action)

            readiness = str(data.get("current_readiness", ImplementationReadiness.NOT_READY.value))
            try:
                current_readiness = ImplementationReadiness(readiness)
            except ValueError:
                current_readiness = ImplementationReadiness.NOT_READY

            est_readiness = str(
                data.get(
                    "estimated_readiness_after_completion",
                    ImplementationReadiness.NOT_READY.value,
                )
            )
            try:
                estimated_readiness_after_completion = ImplementationReadiness(est_readiness)
            except ValueError:
                estimated_readiness_after_completion = ImplementationReadiness.NOT_READY

            analyzed = data.get("last_analyzed")
            if analyzed:
                dt = datetime.fromisoformat(str(analyzed).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = datetime.now(timezone.utc)

            blockers = data.get("blocking_items", [])
            if not isinstance(blockers, list):
                blockers = []

            return cls(
                candidate_id=str(data["candidate_id"]),
                title=str(data.get("title", "")),
                current_score=float(data.get("current_score", 0)),
                current_readiness=current_readiness,
                current_confidence=float(data.get("current_confidence", 0)),
                missing_evidence=gaps,
                research_actions=actions,
                estimated_information_gain=float(data.get("estimated_information_gain", 0)),
                estimated_confidence_after_completion=float(
                    data.get("estimated_confidence_after_completion", 0)
                ),
                estimated_readiness_after_completion=estimated_readiness_after_completion,
                blocking_items=[str(b) for b in blockers],
                recommended_next_step=str(data.get("recommended_next_step", "")),
                priority=int(data.get("priority", 99)),
                human_review_required=bool(data.get("human_review_required", True)),
                implementation_allowed=bool(data.get("implementation_allowed", False)),
                remaining_work_summary=str(data.get("remaining_work_summary", "")),
                safety_mode=str(data.get("safety_mode", RESEARCH_SAFETY_BANNER)),
                last_analyzed=dt,
            )
        except (KeyError, TypeError, ValueError):
            return None


@dataclass
class EvidenceGapReport:
    candidates_analyzed: int
    total_gaps: int
    analyses: list[CandidateGapAnalysis]
    highest_information_gain_candidate_id: str
    highest_information_gain: float
    most_blocked_candidate_id: str
    most_blocked_gap_count: int
    easiest_unblock_candidate_id: str
    candidates_ready_after_closure: int
    recommended_research_order: list[str]
    top_blocked_candidate_id: str
    sources_loaded: dict[str, bool] = field(default_factory=dict)
    gaps_created: int = 0
    gaps_updated: int = 0
    safety_mode: str = RESEARCH_SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "candidates_analyzed": self.candidates_analyzed,
            "total_gaps": self.total_gaps,
            "gaps_created": self.gaps_created,
            "gaps_updated": self.gaps_updated,
            "highest_information_gain_candidate_id": self.highest_information_gain_candidate_id,
            "highest_information_gain": round(self.highest_information_gain, 2),
            "most_blocked_candidate_id": self.most_blocked_candidate_id,
            "most_blocked_gap_count": self.most_blocked_gap_count,
            "easiest_unblock_candidate_id": self.easiest_unblock_candidate_id,
            "candidates_ready_after_closure": self.candidates_ready_after_closure,
            "recommended_research_order": list(self.recommended_research_order),
            "top_blocked_candidate_id": self.top_blocked_candidate_id,
            "sources_loaded": dict(self.sources_loaded),
            "analyses": [a.to_dict() for a in self.analyses],
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE EVIDENCE GAP REPORT =====",
            "",
            f"Safety: {self.safety_mode}",
            f"Generated: {self.generated_at.isoformat()}",
            "",
            f"Candidates analyzed: {self.candidates_analyzed}",
            f"Total gaps identified: {self.total_gaps}",
            f"Gaps created (this run): {self.gaps_created}",
            f"Gaps updated (this run): {self.gaps_updated}",
            "",
            "===== EXECUTIVE SUMMARY =====",
            f"Top blocked candidate: {self.top_blocked_candidate_id}",
            f"Highest information gain: {self.highest_information_gain_candidate_id} "
            f"({self.highest_information_gain:.1f})",
            f"Easiest candidate to unblock: {self.easiest_unblock_candidate_id}",
            f"Candidates potentially ready after gap closure: "
            f"{self.candidates_ready_after_closure}",
            "",
            "Recommended research order:",
        ]
        for idx, cid in enumerate(self.recommended_research_order, start=1):
            lines.append(f"  {idx}. {cid}")
        lines.append("")
        lines.append("===== CANDIDATE GAP DETAILS =====")
        for analysis in sorted(self.analyses, key=lambda a: a.priority):
            lines.extend(self._format_candidate(analysis))
        lines.extend([
            "",
            "===== AVERTISMENT =====",
            "NOT IMPLEMENTED",
            "RESEARCH ROADMAP ONLY",
            "",
            "===== CONFIRMARE SIGURANȚĂ =====",
            "No live trading files were modified",
            "",
            "Planificare cercetare — nu modifică strategie sau execuție.",
            "",
        ])
        return "\n".join(lines)

    def _format_candidate(self, analysis: CandidateGapAnalysis) -> list[str]:
        lines = [
            "----------------------------------------",
            f"{analysis.candidate_id} | priority={analysis.priority} | "
            f"score={analysis.current_score:.1f}",
            f"  title: {analysis.title[:80]}",
            f"  current_readiness: {analysis.current_readiness.value}",
            f"  current_confidence: {analysis.current_confidence:.1f}",
            f"  estimated_confidence_after_completion: "
            f"{analysis.estimated_confidence_after_completion:.1f}",
            f"  estimated_readiness_after_completion: "
            f"{analysis.estimated_readiness_after_completion.value}",
            f"  estimated_information_gain: {analysis.estimated_information_gain:.1f}",
            f"  implementation_allowed: {analysis.implementation_allowed}",
            f"  remaining_work: {analysis.remaining_work_summary}",
        ]
        if analysis.blocking_items:
            lines.append("  blocking_items:")
            for item in analysis.blocking_items[:5]:
                lines.append(f"    - {item}")
        if analysis.missing_evidence:
            lines.append(f"  missing_evidence ({len(analysis.missing_evidence)}):")
            for gap in analysis.missing_evidence[:12]:
                lines.append(f"    - [{gap.category.value}] {gap.label}")
            if len(analysis.missing_evidence) > 12:
                lines.append(f"    ... +{len(analysis.missing_evidence) - 12} more")
        if analysis.research_actions:
            lines.append("  research_actions:")
            for action in analysis.research_actions[:5]:
                lines.append(f"    {action.priority_rank}. {action.action[:90]}")
        lines.append(f"  recommended_next_step: {analysis.recommended_next_step[:100]}")
        lines.append("")
        return lines


class EvidenceGapStore:
    """JSON persistence for gap analyses — stdlib only."""

    def __init__(self, path: Path | None = None, auto_load: bool = True) -> None:
        self._path = path or DEFAULT_GAP_JSON_PATH
        self._analyses: dict[str, CandidateGapAnalysis] = {}
        self._loaded_at_startup = False
        if auto_load:
            self._loaded_at_startup = self.load()

    @property
    def path(self) -> Path:
        return self._path

    def get(self, candidate_id: str) -> CandidateGapAnalysis | None:
        return self._analyses.get(candidate_id)

    def list_all(self) -> list[CandidateGapAnalysis]:
        return sorted(self._analyses.values(), key=lambda a: a.priority)

    def load(self) -> bool:
        if not self._path.is_file():
            return False
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Gap report unreadable (%s): %s", self._path, exc)
            return False
        if not isinstance(payload, dict) or payload.get("schema") != SCHEMA_NAME:
            return False
        items = payload.get("analyses", [])
        if not isinstance(items, list):
            return False
        self._analyses.clear()
        for item in items:
            if not isinstance(item, dict):
                continue
            analysis = CandidateGapAnalysis.from_dict(item)
            if analysis is not None:
                self._analyses[analysis.candidate_id] = analysis
        return True

    def upsert_analysis(
        self,
        analysis: CandidateGapAnalysis,
        merge_items: bool = True,
    ) -> tuple[bool, int, int]:
        """Insert or update analysis. Returns (is_new, gaps_added, gaps_skipped)."""
        existing = self._analyses.get(analysis.candidate_id)
        if existing is None:
            self._analyses[analysis.candidate_id] = analysis
            return True, len(analysis.missing_evidence), 0

        if not merge_items:
            self._analyses[analysis.candidate_id] = analysis
            return False, len(analysis.missing_evidence), 0

        seen_gaps = {g.fingerprint for g in existing.missing_evidence}
        merged_gaps = list(existing.missing_evidence)
        gaps_added = 0
        gaps_skipped = 0
        for gap in analysis.missing_evidence:
            if gap.fingerprint not in seen_gaps:
                merged_gaps.append(gap)
                seen_gaps.add(gap.fingerprint)
                gaps_added += 1
            else:
                gaps_skipped += 1

        seen_actions = {a.fingerprint for a in existing.research_actions}
        merged_actions = list(existing.research_actions)
        for action in analysis.research_actions:
            if action.fingerprint not in seen_actions:
                merged_actions.append(action)
                seen_actions.add(action.fingerprint)

        analysis.missing_evidence = merged_gaps
        analysis.research_actions = sorted(merged_actions, key=lambda a: a.priority_rank)
        self._analyses[analysis.candidate_id] = analysis
        return False, gaps_added, gaps_skipped

    def persist(self, report: EvidenceGapReport) -> Path:
        payload = report.to_dict()
        payload["analyses"] = [a.to_dict() for a in self.list_all()]
        self._path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return self._path

    def persist_txt(self, report: EvidenceGapReport) -> Path:
        DEFAULT_GAP_TXT_PATH.write_text(report.format_text() + "\n", encoding="utf-8")
        return DEFAULT_GAP_TXT_PATH
