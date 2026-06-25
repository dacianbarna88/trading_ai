"""
Knowledge candidate registry — Sprint 5.3

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Promotes high-quality ranked hypotheses into a knowledge candidate registry.
Not a trading signal registry — research knowledge only.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from research_core.hypothesis.hypothesis_model import SAFETY_MODE
from research_core.hypothesis.hypothesis_ranking import (
    DEFAULT_DISCOVERY_RANKINGS_PATH,
    DISCOVERY_RANKINGS_SCHEMA_NAME,
    HypothesisRankingEntry,
    HypothesisRankingsStore,
    RankingRecommendation,
)

logger = logging.getLogger(__name__)

DEFAULT_CANDIDATES_PATH = Path("tae_knowledge_candidates.json")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_knowledge_candidates"
PROMOTE_RECOMMENDATION = RankingRecommendation.PROMOTE_TO_KNOWLEDGE_CANDIDATE.value


class KnowledgeCandidateStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    UNDER_REVIEW = "UNDER_REVIEW"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"


@dataclass
class KnowledgeCandidate:
    candidate_id: str
    source_hypothesis_id: str
    title: str
    quality_score: float
    accuracy: float
    sample_size: int
    avg_forward_return: float
    robustness_label: str
    evidence_summary: str
    promotion_reason: str
    status: KnowledgeCandidateStatus = KnowledgeCandidateStatus.CANDIDATE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    safety_mode: str = SAFETY_MODE

    def __post_init__(self) -> None:
        if isinstance(self.status, str):
            self.status = KnowledgeCandidateStatus(self.status)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "source_hypothesis_id": self.source_hypothesis_id,
            "title": self.title,
            "quality_score": round(self.quality_score, 2),
            "accuracy": round(self.accuracy, 4),
            "sample_size": self.sample_size,
            "avg_forward_return": round(self.avg_forward_return, 4),
            "robustness_label": self.robustness_label,
            "evidence_summary": self.evidence_summary,
            "promotion_reason": self.promotion_reason,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "safety_mode": self.safety_mode,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeCandidate | None:
        try:
            created = data.get("created_at")
            if created:
                dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = datetime.now(timezone.utc)

            status_raw = str(data.get("status", KnowledgeCandidateStatus.CANDIDATE.value))
            try:
                status = KnowledgeCandidateStatus(status_raw)
            except ValueError:
                status = KnowledgeCandidateStatus.CANDIDATE

            return cls(
                candidate_id=str(data["candidate_id"]),
                source_hypothesis_id=str(data.get("source_hypothesis_id", "")),
                title=str(data.get("title", "")),
                quality_score=float(data.get("quality_score", 0)),
                accuracy=float(data.get("accuracy", 0)),
                sample_size=int(data.get("sample_size", 0)),
                avg_forward_return=float(data.get("avg_forward_return", 0)),
                robustness_label=str(data.get("robustness_label", "")),
                evidence_summary=str(data.get("evidence_summary", "")),
                promotion_reason=str(data.get("promotion_reason", "")),
                status=status,
                created_at=dt,
                safety_mode=str(data.get("safety_mode", SAFETY_MODE)),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def summary_line(self) -> str:
        return (
            f"{self.candidate_id} | {self.source_hypothesis_id} | "
            f"score={self.quality_score:.1f} acc={self.accuracy:.2%} "
            f"n={self.sample_size} [{self.status.value}]"
        )


@dataclass
class PromotionResult:
    promoted: list[KnowledgeCandidate]
    skipped_duplicates: list[str]
    eligible_from_rankings: int
    rankings_loaded: bool
    rankings_count: int
    skipped_ineligible: list[str] = field(default_factory=list)
    knowledge_base_improved: bool = False
    comparison_summary: str = ""

    @property
    def promoted_count(self) -> int:
        return len(self.promoted)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped_duplicates)


class KnowledgeCandidateRegistry:
    """Persistent store for research knowledge candidates — stdlib json only."""

    def __init__(self, path: Path | None = None, auto_load: bool = True) -> None:
        self._path = path or DEFAULT_CANDIDATES_PATH
        self._candidates: dict[str, KnowledgeCandidate] = {}
        self._by_source: dict[str, str] = {}
        self._sequence: int = 0
        self._loaded_at_startup = False
        if auto_load:
            self._loaded_at_startup = self.load()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def loaded_at_startup(self) -> bool:
        return self._loaded_at_startup

    def count(self) -> int:
        return len(self._candidates)

    def list_all(self) -> list[KnowledgeCandidate]:
        return sorted(self._candidates.values(), key=lambda c: c.created_at)

    def get(self, candidate_id: str) -> KnowledgeCandidate | None:
        return self._candidates.get(candidate_id)

    def has_source(self, source_hypothesis_id: str) -> bool:
        return source_hypothesis_id in self._by_source

    def get_by_source(self, source_hypothesis_id: str) -> KnowledgeCandidate | None:
        cid = self._by_source.get(source_hypothesis_id)
        if cid is None:
            return None
        return self._candidates.get(cid)

    def next_id(self, prefix: str = "kn_s53") -> str:
        self._sequence += 1
        return f"{prefix}_{self._sequence:05d}"

    def register(self, candidate: KnowledgeCandidate) -> KnowledgeCandidate:
        if candidate.source_hypothesis_id in self._by_source:
            raise ValueError(
                f"Duplicate source_hypothesis_id: {candidate.source_hypothesis_id}"
            )
        if candidate.candidate_id in self._candidates:
            raise ValueError(f"Duplicate candidate_id: {candidate.candidate_id}")
        self._candidates[candidate.candidate_id] = candidate
        self._by_source[candidate.source_hypothesis_id] = candidate.candidate_id
        return candidate

    def load(self) -> bool:
        if not self._path.is_file():
            return False
        try:
            raw = self._path.read_text(encoding="utf-8")
            payload = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Knowledge candidates unreadable (%s): %s", self._path, exc)
            return False

        if not isinstance(payload, dict) or payload.get("schema") != SCHEMA_NAME:
            logger.warning("Knowledge candidates schema mismatch in %s", self._path)
            return False

        self._sequence = int(payload.get("sequence", 0))
        items = payload.get("candidates", [])
        if not isinstance(items, list):
            return False

        restored: dict[str, KnowledgeCandidate] = {}
        by_source: dict[str, str] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            candidate = KnowledgeCandidate.from_dict(item)
            if candidate is None:
                continue
            restored[candidate.candidate_id] = candidate
            by_source[candidate.source_hypothesis_id] = candidate.candidate_id

        self._candidates = restored
        self._by_source = by_source
        if self._sequence < len(restored):
            self._sequence = len(restored)
        return True

    def persist(self) -> Path:
        payload = {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "safety_mode": SAFETY_MODE,
            "sequence": self._sequence,
            "candidate_count": len(self._candidates),
            "candidates": [c.to_dict() for c in self.list_all()],
        }
        self._path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return self._path

    def format_summary(self) -> str:
        if not self._candidates:
            return "Knowledge candidate registry empty."
        lines = ["===== KNOWLEDGE CANDIDATE REGISTRY =====", ""]
        for candidate in self.list_all():
            lines.append(f"  {candidate.summary_line()}")
            lines.append(f"    title: {candidate.title}")
            lines.append(f"    promotion: {candidate.promotion_reason[:100]}")
        lines.append("")
        return "\n".join(lines)


def _build_evidence_summary(entry: HypothesisRankingEntry) -> str:
    return (
        f"Historical cohort: n={entry.sample_size}, "
        f"accuracy={entry.accuracy:.2%}, "
        f"avg_forward_return={entry.avg_forward_return:.2f}%, "
        f"robustness={entry.robustness_label}, "
        f"duplicate_group={entry.duplicate_group}. "
        "Research evidence from Sprint 5.1 experiments — not live trading."
    )


def _build_promotion_reason(entry: HypothesisRankingEntry) -> str:
    return (
        f"Rank #{entry.rank} quality_score={entry.quality_score:.2f} with "
        f"recommendation {PROMOTE_RECOMMENDATION}. "
        f"Best representative in duplicate group '{entry.duplicate_group}'. "
        "Promoted to knowledge candidate for research review — not execution."
    )


def _candidate_from_ranking(
    entry: HypothesisRankingEntry,
    registry: KnowledgeCandidateRegistry,
) -> KnowledgeCandidate:
    return KnowledgeCandidate(
        candidate_id=registry.next_id(),
        source_hypothesis_id=entry.hypothesis_id,
        title=entry.title,
        quality_score=entry.quality_score,
        accuracy=entry.accuracy,
        sample_size=entry.sample_size,
        avg_forward_return=entry.avg_forward_return,
        robustness_label=entry.robustness_label,
        evidence_summary=_build_evidence_summary(entry),
        promotion_reason=_build_promotion_reason(entry),
        status=KnowledgeCandidateStatus.CANDIDATE,
        safety_mode=entry.safety_mode,
    )


def _meets_discovery_promotion_thresholds(
    entry: HypothesisRankingEntry,
    min_quality_score: float,
    min_sample_size: int,
    min_accuracy: float,
) -> bool:
    return (
        entry.recommendation == PROMOTE_RECOMMENDATION
        and entry.quality_score >= min_quality_score
        and entry.sample_size >= min_sample_size
        and entry.accuracy >= min_accuracy
        and entry.avg_forward_return > 0.0
    )


def _build_discovery_evidence_summary(entry: HypothesisRankingEntry) -> str:
    return (
        f"Discovery-derived hypothesis: n={entry.sample_size}, "
        f"accuracy={entry.accuracy:.2%}, "
        f"avg_forward_return={entry.avg_forward_return:.2f}%, "
        f"robustness={entry.robustness_label}, "
        f"quality_score={entry.quality_score:.2f}. "
        "Phase IV discovery pipeline — research evidence only, not live trading."
    )


def _build_discovery_promotion_reason(
    entry: HypothesisRankingEntry,
    comparison: dict[str, Any] | None = None,
) -> str:
    base = (
        f"Phase IV D5 discovery promotion: rank #{entry.rank}, "
        f"quality_score={entry.quality_score:.2f}, "
        f"recommendation={PROMOTE_RECOMMENDATION}. "
        "Discovery-derived knowledge candidate — not execution."
    )
    if comparison and comparison.get("summary"):
        return f"{base} Comparison: {comparison['summary']}"
    return base


class DiscoveryRankingsLoader:
    """Loads discovery hypothesis rankings from Phase IV D4 report."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or DEFAULT_DISCOVERY_RANKINGS_PATH

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> tuple[list[HypothesisRankingEntry], dict[str, Any], bool]:
        if not self._path.is_file():
            return [], {}, False
        try:
            raw = self._path.read_text(encoding="utf-8")
            payload = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Discovery rankings unreadable (%s): %s", self._path, exc)
            return [], {}, False

        if not isinstance(payload, dict) or payload.get("schema") != DISCOVERY_RANKINGS_SCHEMA_NAME:
            return [], {}, False

        items = payload.get("discovery_rankings", [])
        rankings: list[HypothesisRankingEntry] = []
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                entry = HypothesisRankingEntry.from_dict(item)
                if entry is not None:
                    rankings.append(entry)

        comparison = payload.get("comparison", {})
        if not isinstance(comparison, dict):
            comparison = {}

        return rankings, comparison, True


def _candidate_from_discovery_ranking(
    entry: HypothesisRankingEntry,
    registry: KnowledgeCandidateRegistry,
    comparison: dict[str, Any] | None = None,
) -> KnowledgeCandidate:
    return KnowledgeCandidate(
        candidate_id=registry.next_id(prefix="kn_d5"),
        source_hypothesis_id=entry.hypothesis_id,
        title=entry.title,
        quality_score=entry.quality_score,
        accuracy=entry.accuracy,
        sample_size=entry.sample_size,
        avg_forward_return=entry.avg_forward_return,
        robustness_label=entry.robustness_label,
        evidence_summary=_build_discovery_evidence_summary(entry),
        promotion_reason=_build_discovery_promotion_reason(entry, comparison),
        status=KnowledgeCandidateStatus.CANDIDATE,
        safety_mode=entry.safety_mode,
    )


class KnowledgeCandidatePromoter:
    """
    Promotes PROMOTE_TO_KNOWLEDGE_CANDIDATE rankings into the candidate registry.
    Sprint 5.3 — idempotent per source_hypothesis_id.
    """

    def __init__(
        self,
        rankings_store: HypothesisRankingsStore | None = None,
        candidate_registry: KnowledgeCandidateRegistry | None = None,
    ) -> None:
        self._rankings = rankings_store or HypothesisRankingsStore()
        self._registry = candidate_registry or KnowledgeCandidateRegistry()

    @property
    def rankings_store(self) -> HypothesisRankingsStore:
        return self._rankings

    @property
    def registry(self) -> KnowledgeCandidateRegistry:
        return self._registry

    def promote_from_rankings(self) -> PromotionResult:
        rankings_loaded = self._rankings.loaded_at_startup or self._rankings.load()
        rankings = self._rankings.list_all() if rankings_loaded else []

        eligible = [
            entry
            for entry in rankings
            if entry.recommendation == PROMOTE_RECOMMENDATION
        ]

        promoted: list[KnowledgeCandidate] = []
        skipped: list[str] = []

        for entry in eligible:
            if self._registry.has_source(entry.hypothesis_id):
                skipped.append(entry.hypothesis_id)
                continue
            candidate = _candidate_from_ranking(entry, self._registry)
            self._registry.register(candidate)
            promoted.append(candidate)

        return PromotionResult(
            promoted=promoted,
            skipped_duplicates=skipped,
            eligible_from_rankings=len(eligible),
            rankings_loaded=rankings_loaded,
            rankings_count=len(rankings),
        )

    def promote_from_discovery_rankings(
        self,
        rankings_path: Path | None = None,
        min_quality_score: float = 65.0,
        min_sample_size: int = 500,
        min_accuracy: float = 0.60,
    ) -> PromotionResult:
        """
        Promote discovery-derived hypotheses from Phase IV D4 rankings.
        Stricter thresholds than Sprint 5.3 council rankings.
        """
        loader = DiscoveryRankingsLoader(path=rankings_path)
        rankings, comparison, rankings_loaded = loader.load()

        eligible: list[HypothesisRankingEntry] = []
        skipped_ineligible: list[str] = []

        for entry in rankings:
            if _meets_discovery_promotion_thresholds(
                entry, min_quality_score, min_sample_size, min_accuracy
            ):
                eligible.append(entry)
            else:
                skipped_ineligible.append(
                    f"{entry.hypothesis_id} "
                    f"(rec={entry.recommendation}, q={entry.quality_score:.1f}, "
                    f"n={entry.sample_size}, acc={entry.accuracy:.2%})"
                )

        prior_best_quality = 0.0
        for candidate in self._registry.list_all():
            if candidate.quality_score > prior_best_quality:
                prior_best_quality = candidate.quality_score

        promoted: list[KnowledgeCandidate] = []
        skipped: list[str] = []

        for entry in eligible:
            if self._registry.has_source(entry.hypothesis_id):
                skipped.append(entry.hypothesis_id)
                continue
            candidate = _candidate_from_discovery_ranking(
                entry, self._registry, comparison
            )
            self._registry.register(candidate)
            promoted.append(candidate)

        knowledge_improved = False
        if promoted:
            new_best = max(c.quality_score for c in promoted)
            knowledge_improved = new_best > prior_best_quality or (
                comparison.get("knowledge_base_improved", False)
            )
        comparison_summary = str(comparison.get("summary", ""))

        return PromotionResult(
            promoted=promoted,
            skipped_duplicates=skipped,
            eligible_from_rankings=len(eligible),
            rankings_loaded=rankings_loaded,
            rankings_count=len(rankings),
            skipped_ineligible=skipped_ineligible,
            knowledge_base_improved=knowledge_improved,
            comparison_summary=comparison_summary,
        )
