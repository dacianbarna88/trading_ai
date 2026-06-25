"""
Hypothesis quality ranking — Sprint 5.2

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Ranks tested hypotheses by research quality — not raw accuracy alone.
Does not promote hypotheses to live signals or execution.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from research_core.hypothesis.experiment_result import ExperimentResult, ExperimentStatus
from research_core.hypothesis.experiment_runner import ExperimentResultsStore
from research_core.hypothesis.hypothesis_model import Hypothesis, HypothesisStatus, SAFETY_MODE
from research_core.hypothesis.hypothesis_registry import HypothesisRegistry

logger = logging.getLogger(__name__)

DEFAULT_RANKINGS_PATH = Path("tae_hypothesis_rankings.json")
DEFAULT_DISCOVERY_RANKINGS_PATH = Path("tae_discovery_hypothesis_rankings.json")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_hypothesis_rankings"
DISCOVERY_RANKINGS_SCHEMA_NAME = "tae_discovery_hypothesis_rankings"

ROBUSTNESS_HIGH = "HIGH"
ROBUSTNESS_ROBUST = "ROBUST"
ROBUSTNESS_MODERATE = "MODERATE"
ROBUSTNESS_LOW = "LOW"
ROBUSTNESS_FRAGILE = "FRAGILE"
ROBUSTNESS_INSUFFICIENT = "INSUFFICIENT"


class RankingRecommendation(str, Enum):
    PROMOTE_TO_KNOWLEDGE_CANDIDATE = "PROMOTE_TO_KNOWLEDGE_CANDIDATE"
    KEEP_UNDER_OBSERVATION = "KEEP_UNDER_OBSERVATION"
    NEEDS_MORE_DATA = "NEEDS_MORE_DATA"
    REJECT_WEAK_EDGE = "REJECT_WEAK_EDGE"


@dataclass
class HypothesisRankingEntry:
    rank: int
    hypothesis_id: str
    title: str
    quality_score: float
    accuracy: float
    sample_size: int
    avg_forward_return: float
    robustness_label: str
    duplicate_group: str
    recommendation: str
    safety_mode: str = SAFETY_MODE

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "hypothesis_id": self.hypothesis_id,
            "title": self.title,
            "quality_score": round(self.quality_score, 2),
            "accuracy": round(self.accuracy, 4),
            "sample_size": self.sample_size,
            "avg_forward_return": round(self.avg_forward_return, 4),
            "robustness_label": self.robustness_label,
            "duplicate_group": self.duplicate_group,
            "recommendation": self.recommendation,
            "safety_mode": self.safety_mode,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HypothesisRankingEntry | None:
        try:
            return cls(
                rank=int(data.get("rank", 0)),
                hypothesis_id=str(data.get("hypothesis_id", "")),
                title=str(data.get("title", "")),
                quality_score=float(data.get("quality_score", 0)),
                accuracy=float(data.get("accuracy", 0)),
                sample_size=int(data.get("sample_size", 0)),
                avg_forward_return=float(data.get("avg_forward_return", 0)),
                robustness_label=str(data.get("robustness_label", "")),
                duplicate_group=str(data.get("duplicate_group", "")),
                recommendation=str(data.get("recommendation", "")),
                safety_mode=str(data.get("safety_mode", SAFETY_MODE)),
            )
        except (TypeError, ValueError):
            return None

    def summary_line(self) -> str:
        return (
            f"#{self.rank} {self.hypothesis_id} | score={self.quality_score:.1f} | "
            f"acc={self.accuracy:.2%} n={self.sample_size} ret={self.avg_forward_return:.2f}% | "
            f"{self.robustness_label} | {self.recommendation}"
        )


@dataclass
class DuplicateGroupSummary:
    group_id: str
    title: str
    member_ids: list[str]
    best_hypothesis_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "group_id": self.group_id,
            "title": self.title,
            "member_count": len(self.member_ids),
            "member_ids": list(self.member_ids),
            "best_hypothesis_id": self.best_hypothesis_id,
        }


class HypothesisRankingsStore:
    """JSON persistence for hypothesis quality rankings."""

    def __init__(self, path: Path | None = None, auto_load: bool = True) -> None:
        self._path = path or DEFAULT_RANKINGS_PATH
        self._rankings: list[HypothesisRankingEntry] = []
        self._duplicate_groups: list[DuplicateGroupSummary] = []
        self._meta: dict[str, Any] = {}
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
        return len(self._rankings)

    def list_all(self) -> list[HypothesisRankingEntry]:
        return list(self._rankings)

    def duplicate_groups(self) -> list[DuplicateGroupSummary]:
        return list(self._duplicate_groups)

    def set_rankings(
        self,
        rankings: list[HypothesisRankingEntry],
        duplicate_groups: list[DuplicateGroupSummary],
        meta: dict[str, Any] | None = None,
    ) -> None:
        self._rankings = list(rankings)
        self._duplicate_groups = list(duplicate_groups)
        self._meta = dict(meta or {})

    def load(self) -> bool:
        if not self._path.is_file():
            return False
        try:
            raw = self._path.read_text(encoding="utf-8")
            payload = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Rankings file unreadable (%s): %s", self._path, exc)
            return False

        if not isinstance(payload, dict) or payload.get("schema") != SCHEMA_NAME:
            return False

        items = payload.get("rankings", [])
        if not isinstance(items, list):
            return False

        restored: list[HypothesisRankingEntry] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            entry = HypothesisRankingEntry.from_dict(item)
            if entry is not None:
                restored.append(entry)

        groups_raw = payload.get("duplicate_groups", [])
        groups: list[DuplicateGroupSummary] = []
        if isinstance(groups_raw, list):
            for g in groups_raw:
                if not isinstance(g, dict):
                    continue
                members = g.get("member_ids", [])
                if not isinstance(members, list):
                    members = []
                groups.append(
                    DuplicateGroupSummary(
                        group_id=str(g.get("group_id", "")),
                        title=str(g.get("title", "")),
                        member_ids=[str(m) for m in members],
                        best_hypothesis_id=str(g.get("best_hypothesis_id", "")),
                    )
                )

        self._rankings = restored
        self._duplicate_groups = groups
        self._meta = {
            "total_tested": payload.get("total_tested", 0),
            "ranked_count": payload.get("ranked_count", len(restored)),
            "top_hypothesis_id": payload.get("top_hypothesis_id", ""),
        }
        return True

    def persist(self) -> Path:
        payload = {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "safety_mode": SAFETY_MODE,
            "total_tested": self._meta.get("total_tested", 0),
            "ranked_count": len(self._rankings),
            "top_hypothesis_id": self._meta.get("top_hypothesis_id", ""),
            "duplicate_group_count": len(self._duplicate_groups),
            "duplicate_groups": [g.to_dict() for g in self._duplicate_groups],
            "rankings": [r.to_dict() for r in self._rankings],
        }
        self._path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return self._path

    def format_summary(self) -> str:
        if not self._rankings:
            return "Hypothesis rankings empty."
        lines = ["===== HYPOTHESIS QUALITY RANKINGS =====", ""]
        for entry in self._rankings:
            lines.append(f"  {entry.summary_line()}")
            lines.append(f"    group: {entry.duplicate_group}")
        lines.append("")
        return "\n".join(lines)


class HypothesisRanker:
    """
    Computes research-quality rankings from registry + experiment results.
    Sprint 5.2 — structured scoring, not live signal generation.
    """

    RANKABLE_STATUSES = frozenset(
        {
            HypothesisStatus.TESTED,
            HypothesisStatus.INSUFFICIENT_DATA,
            HypothesisStatus.SUPPORTED,
            HypothesisStatus.REJECTED,
        }
    )

    def __init__(
        self,
        registry: HypothesisRegistry | None = None,
        results_store: ExperimentResultsStore | None = None,
    ) -> None:
        self._registry = registry or HypothesisRegistry()
        self._results = results_store or ExperimentResultsStore()

    def rank(
        self,
        source_cycle_prefix: str | None = None,
        exclude_source_cycle_prefix: str | None = None,
    ) -> tuple[list[HypothesisRankingEntry], list[DuplicateGroupSummary], dict[str, Any]]:
        candidates = self._collect_candidates(
            source_cycle_prefix=source_cycle_prefix,
            exclude_source_cycle_prefix=exclude_source_cycle_prefix,
        )
        if not candidates:
            return [], [], {"total_tested": 0, "ranked_count": 0, "top_hypothesis_id": ""}

        duplicate_map = self._build_duplicate_groups(candidates)
        scored: list[tuple[float, HypothesisRankingEntry]] = []

        for hypothesis, experiment in candidates:
            group_id, is_best_in_group = duplicate_map[hypothesis.hypothesis_id]
            quality, robustness = self._compute_quality_score(hypothesis, experiment, is_best_in_group)
            recommendation = self._assign_recommendation(
                hypothesis, experiment, quality, robustness, is_best_in_group
            )
            entry = HypothesisRankingEntry(
                rank=0,
                hypothesis_id=hypothesis.hypothesis_id,
                title=hypothesis.title,
                quality_score=quality,
                accuracy=experiment.accuracy if experiment else 0.0,
                sample_size=experiment.sample_size if experiment else 0,
                avg_forward_return=experiment.avg_forward_return if experiment else 0.0,
                robustness_label=robustness,
                duplicate_group=group_id,
                recommendation=recommendation.value,
            )
            scored.append((quality, entry))

        scored.sort(key=lambda pair: (-pair[0], pair[1].hypothesis_id))
        rankings: list[HypothesisRankingEntry] = []
        for idx, (_, entry) in enumerate(scored, start=1):
            entry.rank = idx
            rankings.append(entry)

        groups = self._summarize_duplicate_groups(candidates, duplicate_map, rankings)
        meta = {
            "total_tested": len(candidates),
            "ranked_count": len(rankings),
            "top_hypothesis_id": rankings[0].hypothesis_id if rankings else "",
        }
        return rankings, groups, meta

    def _collect_candidates(
        self,
        source_cycle_prefix: str | None = None,
        exclude_source_cycle_prefix: str | None = None,
    ) -> list[tuple[Hypothesis, ExperimentResult | None]]:
        latest = self._latest_results_by_hypothesis()
        candidates: list[tuple[Hypothesis, ExperimentResult | None]] = []

        for hypothesis in self._registry.list_all():
            if hypothesis.status not in self.RANKABLE_STATUSES:
                continue
            cycle = str(hypothesis.source_cycle)
            if source_cycle_prefix and not cycle.startswith(source_cycle_prefix):
                continue
            if exclude_source_cycle_prefix and cycle.startswith(exclude_source_cycle_prefix):
                continue
            experiment = latest.get(hypothesis.hypothesis_id)
            if hypothesis.status == HypothesisStatus.TESTED and experiment is None:
                candidates.append((hypothesis, None))
            elif experiment is not None or hypothesis.status in (
                HypothesisStatus.TESTED,
                HypothesisStatus.INSUFFICIENT_DATA,
            ):
                candidates.append((hypothesis, experiment))

        return candidates

    def _latest_results_by_hypothesis(self) -> dict[str, ExperimentResult]:
        latest: dict[str, ExperimentResult] = {}
        for result in self._results.list_all():
            prev = latest.get(result.hypothesis_id)
            if prev is None or result.tested_at > prev.tested_at:
                latest[result.hypothesis_id] = result
        return latest

    def _normalize_title(self, title: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", title.lower().strip())
        return slug.strip("_") or "untitled"

    def _build_duplicate_groups(
        self,
        candidates: list[tuple[Hypothesis, ExperimentResult | None]],
    ) -> dict[str, tuple[str, bool]]:
        """Map hypothesis_id -> (group_id, is_best_representative_in_group)."""
        by_title: dict[str, list[str]] = {}
        title_for_id: dict[str, str] = {}

        for hypothesis, experiment in candidates:
            group_id = self._normalize_title(hypothesis.title)
            title_for_id[hypothesis.hypothesis_id] = group_id
            by_title.setdefault(group_id, []).append(hypothesis.hypothesis_id)

        best_in_group: dict[str, str] = {}
        for group_id, ids in by_title.items():
            if len(ids) == 1:
                best_in_group[group_id] = ids[0]
                continue
            scored_ids: list[tuple[float, str]] = []
            for hid in ids:
                hyp = self._registry.get(hid)
                exp = self._latest_results_by_hypothesis().get(hid)
                if hyp is None:
                    continue
                score, _ = self._compute_quality_score(hyp, exp, is_best_in_group=True)
                scored_ids.append((score, hid))
            scored_ids.sort(key=lambda x: (-x[0], x[1]))
            best_in_group[group_id] = scored_ids[0][1] if scored_ids else ids[0]

        result: dict[str, tuple[str, bool]] = {}
        for hid, group_id in title_for_id.items():
            is_best = best_in_group.get(group_id) == hid
            result[hid] = (group_id, is_best)
        return result

    def _summarize_duplicate_groups(
        self,
        candidates: list[tuple[Hypothesis, ExperimentResult | None]],
        duplicate_map: dict[str, tuple[str, bool]],
        rankings: list[HypothesisRankingEntry],
    ) -> list[DuplicateGroupSummary]:
        groups: dict[str, list[str]] = {}
        titles: dict[str, str] = {}
        for hypothesis, _ in candidates:
            group_id, _ = duplicate_map[hypothesis.hypothesis_id]
            groups.setdefault(group_id, []).append(hypothesis.hypothesis_id)
            titles[group_id] = hypothesis.title

        summaries: list[DuplicateGroupSummary] = []
        for group_id, member_ids in sorted(groups.items()):
            if len(member_ids) < 2:
                continue
            best_id = ""
            for entry in rankings:
                if entry.duplicate_group == group_id:
                    best_id = entry.hypothesis_id
                    break
            summaries.append(
                DuplicateGroupSummary(
                    group_id=group_id,
                    title=titles.get(group_id, group_id),
                    member_ids=sorted(member_ids),
                    best_hypothesis_id=best_id,
                )
            )
        return summaries

    def _robustness_label(
        self,
        experiment: ExperimentResult | None,
        hypothesis: Hypothesis,
    ) -> str:
        if experiment is None:
            return ROBUSTNESS_INSUFFICIENT
        if experiment.status == ExperimentStatus.INSUFFICIENT_DATA:
            return ROBUSTNESS_INSUFFICIENT
        if hypothesis.status == HypothesisStatus.INSUFFICIENT_DATA:
            return ROBUSTNESS_INSUFFICIENT

        n = experiment.sample_size
        if n >= 400:
            return ROBUSTNESS_HIGH
        if n >= 200:
            return ROBUSTNESS_ROBUST
        if n >= 100:
            return ROBUSTNESS_MODERATE
        if n >= 50:
            return ROBUSTNESS_LOW
        if n >= 20:
            return ROBUSTNESS_FRAGILE
        return ROBUSTNESS_INSUFFICIENT

    def _compute_quality_score(
        self,
        hypothesis: Hypothesis,
        experiment: ExperimentResult | None,
        is_best_in_group: bool,
    ) -> tuple[float, str]:
        robustness = self._robustness_label(experiment, hypothesis)

        if experiment is None or experiment.status == ExperimentStatus.INSUFFICIENT_DATA:
            return 0.0, robustness

        accuracy = max(0.0, min(1.0, experiment.accuracy))
        sample = max(0, experiment.sample_size)
        avg_ret = experiment.avg_forward_return

        accuracy_pts = accuracy * 40.0
        sample_pts = min(30.0, (sample / 500.0) * 30.0)

        return_pts = 0.0
        if avg_ret > 0:
            return_pts = min(20.0, avg_ret * 2.0)
        else:
            return_pts = max(-15.0, avg_ret * 2.0)

        penalty = 0.0
        if sample < 100:
            penalty += 10.0
        if sample < 50:
            penalty += 10.0
        if sample < 20:
            penalty += 15.0
        if robustness in (ROBUSTNESS_FRAGILE, ROBUSTNESS_INSUFFICIENT):
            penalty += 8.0
        if not is_best_in_group:
            penalty += 8.0

        quality = max(0.0, min(100.0, accuracy_pts + sample_pts + return_pts - penalty))
        return round(quality, 2), robustness

    def _assign_recommendation(
        self,
        hypothesis: Hypothesis,
        experiment: ExperimentResult | None,
        quality: float,
        robustness: str,
        is_best_in_group: bool,
    ) -> RankingRecommendation:
        if experiment is None:
            return RankingRecommendation.NEEDS_MORE_DATA
        if experiment.status == ExperimentStatus.INSUFFICIENT_DATA:
            return RankingRecommendation.NEEDS_MORE_DATA
        if hypothesis.status == HypothesisStatus.INSUFFICIENT_DATA:
            return RankingRecommendation.NEEDS_MORE_DATA
        if robustness in (ROBUSTNESS_INSUFFICIENT, ROBUSTNESS_FRAGILE):
            return RankingRecommendation.NEEDS_MORE_DATA

        accuracy = experiment.accuracy
        avg_ret = experiment.avg_forward_return
        sample = experiment.sample_size

        if accuracy < 0.52 and avg_ret <= 0:
            return RankingRecommendation.REJECT_WEAK_EDGE
        if quality < 35.0:
            return RankingRecommendation.REJECT_WEAK_EDGE
        if avg_ret < -2.0 and accuracy < 0.55:
            return RankingRecommendation.REJECT_WEAK_EDGE

        promote_threshold = (
            quality >= 65.0
            and sample >= 150
            and accuracy >= 0.57
            and avg_ret > 1.0
            and robustness in (ROBUSTNESS_HIGH, ROBUSTNESS_ROBUST, ROBUSTNESS_MODERATE)
            and is_best_in_group
        )
        if promote_threshold:
            return RankingRecommendation.PROMOTE_TO_KNOWLEDGE_CANDIDATE

        if not is_best_in_group:
            return RankingRecommendation.KEEP_UNDER_OBSERVATION

        if quality >= 50.0 and sample >= 80:
            return RankingRecommendation.KEEP_UNDER_OBSERVATION

        if sample < 100 or robustness == ROBUSTNESS_LOW:
            return RankingRecommendation.NEEDS_MORE_DATA

        return RankingRecommendation.KEEP_UNDER_OBSERVATION
