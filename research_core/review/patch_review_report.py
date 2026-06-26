"""
Patch review report model — Phase VI Sprint B1

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Formal review of implementation patch proposals — review only, no sandbox apply.
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

logger = logging.getLogger(__name__)

DEFAULT_REVIEW_JSON_PATH = Path("tae_patch_review.json")
DEFAULT_REVIEW_TXT_PATH = Path("tae_patch_review.txt")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_patch_review"


class ReviewVerdict(str, Enum):
    APPROVED_FOR_SANDBOX = "APPROVED_FOR_SANDBOX"
    REQUIRE_MORE_EVIDENCE = "REQUIRE_MORE_EVIDENCE"
    REJECTED = "REJECTED"


class OperationalImpact(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ImplementationStatus(str, Enum):
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    IMPLEMENTED = "IMPLEMENTED"


@dataclass
class CategoryScores:
    research_evidence_score: float
    statistical_confidence_score: float
    validation_completeness_score: float
    cross_regime_coverage_score: float
    cross_region_coverage_score: float
    learning_support_score: float
    implementation_risk_score: float
    rollback_readiness_score: float
    operational_impact: OperationalImpact

    def __post_init__(self) -> None:
        if isinstance(self.operational_impact, str):
            self.operational_impact = OperationalImpact(self.operational_impact)

    def to_dict(self) -> dict[str, Any]:
        return {
            "research_evidence_score": round(self.research_evidence_score, 2),
            "statistical_confidence_score": round(self.statistical_confidence_score, 2),
            "validation_completeness_score": round(self.validation_completeness_score, 2),
            "cross_regime_coverage_score": round(self.cross_regime_coverage_score, 2),
            "cross_region_coverage_score": round(self.cross_region_coverage_score, 2),
            "learning_support_score": round(self.learning_support_score, 2),
            "implementation_risk_score": round(self.implementation_risk_score, 2),
            "rollback_readiness_score": round(self.rollback_readiness_score, 2),
            "operational_impact": self.operational_impact.value,
        }


@dataclass
class PatchReviewEntry:
    review_id: str
    patch_id: str
    source_candidate_id: str
    verdict: ReviewVerdict
    review_score: float
    scores: CategoryScores
    missing_evidence: list[str]
    blockers: list[str]
    rationale: str
    next_required_steps: list[str]
    human_approval_required: bool = True
    sandbox_required: bool = True
    implementation_status: ImplementationStatus = ImplementationStatus.NOT_IMPLEMENTED
    safety_mode: str = RESEARCH_SAFETY_BANNER
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if isinstance(self.verdict, str):
            self.verdict = ReviewVerdict(self.verdict)
        if isinstance(self.implementation_status, str):
            self.implementation_status = ImplementationStatus(self.implementation_status)

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "patch_id": self.patch_id,
            "source_candidate_id": self.source_candidate_id,
            "verdict": self.verdict.value,
            "review_score": round(self.review_score, 2),
            "scores": self.scores.to_dict(),
            "missing_evidence": list(self.missing_evidence),
            "blockers": list(self.blockers),
            "rationale": self.rationale,
            "next_required_steps": list(self.next_required_steps),
            "human_approval_required": self.human_approval_required,
            "sandbox_required": self.sandbox_required,
            "implementation_status": self.implementation_status.value,
            "safety_mode": self.safety_mode,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PatchReviewEntry | None:
        try:
            created = data.get("created_at")
            if created:
                dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = datetime.now(timezone.utc)

            scores_raw = data.get("scores", {})
            if not isinstance(scores_raw, dict):
                scores_raw = {}

            verdict_raw = str(data.get("verdict", ReviewVerdict.REQUIRE_MORE_EVIDENCE.value))
            try:
                verdict = ReviewVerdict(verdict_raw)
            except ValueError:
                verdict = ReviewVerdict.REQUIRE_MORE_EVIDENCE

            impl = str(data.get("implementation_status", ImplementationStatus.NOT_IMPLEMENTED.value))
            try:
                implementation_status = ImplementationStatus(impl)
            except ValueError:
                implementation_status = ImplementationStatus.NOT_IMPLEMENTED

            impact = str(scores_raw.get("operational_impact", OperationalImpact.LOW.value))
            try:
                operational_impact = OperationalImpact(impact)
            except ValueError:
                operational_impact = OperationalImpact.LOW

            scores = CategoryScores(
                research_evidence_score=float(scores_raw.get("research_evidence_score", 0)),
                statistical_confidence_score=float(scores_raw.get("statistical_confidence_score", 0)),
                validation_completeness_score=float(scores_raw.get("validation_completeness_score", 0)),
                cross_regime_coverage_score=float(scores_raw.get("cross_regime_coverage_score", 0)),
                cross_region_coverage_score=float(scores_raw.get("cross_region_coverage_score", 0)),
                learning_support_score=float(scores_raw.get("learning_support_score", 0)),
                implementation_risk_score=float(scores_raw.get("implementation_risk_score", 0)),
                rollback_readiness_score=float(scores_raw.get("rollback_readiness_score", 0)),
                operational_impact=operational_impact,
            )

            missing = data.get("missing_evidence", [])
            blockers = data.get("blockers", [])
            steps = data.get("next_required_steps", [])
            if not isinstance(missing, list):
                missing = []
            if not isinstance(blockers, list):
                blockers = []
            if not isinstance(steps, list):
                steps = []

            return cls(
                review_id=str(data["review_id"]),
                patch_id=str(data.get("patch_id", "")),
                source_candidate_id=str(data.get("source_candidate_id", "")),
                verdict=verdict,
                review_score=float(data.get("review_score", 0)),
                scores=scores,
                missing_evidence=[str(m) for m in missing],
                blockers=[str(b) for b in blockers],
                rationale=str(data.get("rationale", "")),
                next_required_steps=[str(s) for s in steps],
                human_approval_required=bool(data.get("human_approval_required", True)),
                sandbox_required=bool(data.get("sandbox_required", True)),
                implementation_status=implementation_status,
                safety_mode=str(data.get("safety_mode", RESEARCH_SAFETY_BANNER)),
                created_at=dt,
            )
        except (KeyError, TypeError, ValueError):
            return None

    def summary_line(self) -> str:
        return (
            f"{self.review_id} | {self.verdict.value} | "
            f"score={self.review_score:.1f} | {self.source_candidate_id}"
        )


@dataclass
class PatchReviewReport:
    patches_reviewed: int
    approved_for_sandbox: int
    require_more_evidence: int
    rejected: int
    reviews_generated: int
    reviews_skipped_duplicate: int
    reviews: list[PatchReviewEntry]
    highest_quality_review: PatchReviewEntry | None
    biggest_blocker: str
    next_recommended_work: str
    sources_loaded: dict[str, bool] = field(default_factory=dict)
    safety_mode: str = RESEARCH_SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "patches_reviewed": self.patches_reviewed,
            "approved_for_sandbox": self.approved_for_sandbox,
            "require_more_evidence": self.require_more_evidence,
            "rejected": self.rejected,
            "reviews_generated": self.reviews_generated,
            "reviews_skipped_duplicate": self.reviews_skipped_duplicate,
            "highest_quality_review_id": (
                self.highest_quality_review.review_id if self.highest_quality_review else ""
            ),
            "biggest_blocker": self.biggest_blocker,
            "next_recommended_work": self.next_recommended_work,
            "sources_loaded": dict(self.sources_loaded),
            "reviews": [r.to_dict() for r in self.reviews],
        }

    def format_executive_summary(self) -> list[str]:
        lines = [
            "===== EXECUTIVE SUMMARY — PATCH REVIEW =====",
            "",
            f"Patches reviewed: {self.patches_reviewed}",
            f"Approved for sandbox: {self.approved_for_sandbox}",
            f"Require more evidence: {self.require_more_evidence}",
            f"Rejected: {self.rejected}",
            "",
        ]
        if self.highest_quality_review:
            hq = self.highest_quality_review
            lines.append(
                f"Highest quality patch: {hq.patch_id} "
                f"(score={hq.review_score:.1f}, verdict={hq.verdict.value})"
            )
        lines.append(f"Biggest blocker: {self.biggest_blocker}")
        lines.append(f"Next recommended work: {self.next_recommended_work}")
        lines.append("Live files modified: NO")
        lines.append("")
        lines.append("NOT IMPLEMENTED — REVIEW ONLY")
        lines.append("No live trading files were modified")
        lines.append("")
        return lines

    def format_text(self) -> str:
        lines = [
            "===== TAE PATCH REVIEW CENTER =====",
            "",
            f"Safety: {self.safety_mode}",
            f"Generated: {self.generated_at.isoformat()}",
            "",
        ]
        lines.extend(self.format_executive_summary())

        lines.append("===== REVIEW DETAILS =====")
        lines.append("")
        for entry in self.reviews:
            lines.extend([
                "----------------------------------------",
                entry.summary_line(),
                f"  title patch: {entry.patch_id}",
                "",
                "Scores:",
                f"  research_evidence: {entry.scores.research_evidence_score:.1f}",
                f"  statistical_confidence: {entry.scores.statistical_confidence_score:.1f}",
                f"  validation_completeness: {entry.scores.validation_completeness_score:.1f}",
                f"  cross_regime_coverage: {entry.scores.cross_regime_coverage_score:.1f}",
                f"  cross_region_coverage: {entry.scores.cross_region_coverage_score:.1f}",
                f"  learning_support: {entry.scores.learning_support_score:.1f}",
                f"  implementation_risk: {entry.scores.implementation_risk_score:.1f}",
                f"  rollback_readiness: {entry.scores.rollback_readiness_score:.1f}",
                f"  operational_impact: {entry.scores.operational_impact.value}",
                "",
                "Missing evidence:",
            ])
            for item in entry.missing_evidence:
                lines.append(f"  - {item}")
            if not entry.missing_evidence:
                lines.append("  (none listed)")
            lines.append("")
            lines.append("Blockers:")
            for item in entry.blockers:
                lines.append(f"  - {item}")
            lines.append("")
            lines.append(f"Rationale: {entry.rationale[:400]}")
            lines.append("")
            lines.append("Next required steps:")
            for step in entry.next_required_steps:
                lines.append(f"  - {step}")
            lines.extend([
                "",
                f"human_approval_required: {entry.human_approval_required}",
                f"sandbox_required: {entry.sandbox_required}",
                f"implementation_status: {entry.implementation_status.value}",
                "",
            ])

        lines.extend([
            "===== AVERTISMENT =====",
            "NOT IMPLEMENTED — REVIEW ONLY",
            "",
            "===== CONFIRMARE SIGURANȚĂ =====",
            "No live trading files were modified",
            "",
            "Revizuire documentație — nu se aplică patch-uri sau sandbox automat.",
            "",
        ])
        return "\n".join(lines)


class PatchReviewStore:
    """JSON persistence for patch reviews — stdlib only."""

    def __init__(self, path: Path | None = None, auto_load: bool = True) -> None:
        self._path = path or DEFAULT_REVIEW_JSON_PATH
        self._reviews: dict[str, PatchReviewEntry] = {}
        self._loaded_at_startup = False
        if auto_load:
            self._loaded_at_startup = self.load()

    @property
    def path(self) -> Path:
        return self._path

    def list_all(self) -> list[PatchReviewEntry]:
        return sorted(self._reviews.values(), key=lambda r: r.created_at)

    def has_patch(self, patch_id: str) -> bool:
        return any(r.patch_id == patch_id for r in self._reviews.values())

    def load(self) -> bool:
        if not self._path.is_file():
            return False
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Review store unreadable (%s): %s", self._path, exc)
            return False
        if not isinstance(payload, dict) or payload.get("schema") != SCHEMA_NAME:
            return False
        items = payload.get("reviews", [])
        if not isinstance(items, list):
            return False
        self._reviews.clear()
        for item in items:
            if not isinstance(item, dict):
                continue
            entry = PatchReviewEntry.from_dict(item)
            if entry is not None:
                self._reviews[entry.review_id] = entry
        return True

    def merge_new(self, reviews: list[PatchReviewEntry]) -> tuple[int, int]:
        added = 0
        skipped = 0
        for review in reviews:
            if review.review_id in self._reviews or self.has_patch(review.patch_id):
                skipped += 1
                continue
            self._reviews[review.review_id] = review
            added += 1
        return added, skipped

    def persist(self, report: PatchReviewReport) -> Path:
        payload = report.to_dict()
        payload["reviews"] = [r.to_dict() for r in self.list_all()]
        self._path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return self._path

    def persist_txt(self, report: PatchReviewReport) -> Path:
        DEFAULT_REVIEW_TXT_PATH.write_text(report.format_text() + "\n", encoding="utf-8")
        return DEFAULT_REVIEW_TXT_PATH
