"""
Learning engine — Sprint 5.4 meta-learning from research history.

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Transforms experiment history into structured lessons — not trading signals.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.ecosystem.organism_memory import OrganismMemoryStore
from research_core.hypothesis.experiment_result import ExperimentStatus
from research_core.hypothesis.experiment_runner import ExperimentResultsStore
from research_core.hypothesis.hypothesis_ranking import HypothesisRankingsStore
from research_core.hypothesis.knowledge_candidate import KnowledgeCandidateRegistry
from research_core.learning.learning_report import LearningReport

logger = logging.getLogger(__name__)

REGIME_PATTERNS = (
    ("BULL", re.compile(r"\bBULL\b", re.IGNORECASE)),
    ("BEAR", re.compile(r"\bBEAR\b", re.IGNORECASE)),
    ("NEUTRAL", re.compile(r"\bNEUTRAL\b", re.IGNORECASE)),
)


class LearningEngine:
    """
    Aggregates experiment, ranking, candidate, and organism memory data
    into a meta-learning report. Sprint 5.4 foundation — no execution paths.
    """

    def __init__(
        self,
        experiment_store: ExperimentResultsStore | None = None,
        rankings_store: HypothesisRankingsStore | None = None,
        candidate_registry: KnowledgeCandidateRegistry | None = None,
        organism_memory: OrganismMemoryStore | None = None,
    ) -> None:
        self._experiments = experiment_store or ExperimentResultsStore()
        self._rankings = rankings_store or HypothesisRankingsStore()
        self._candidates = candidate_registry or KnowledgeCandidateRegistry()
        self._organisms = organism_memory or OrganismMemoryStore()

    def analyze(self) -> LearningReport:
        sources_loaded = self._load_all_sources()

        tested_results = [
            r
            for r in self._experiments.list_all()
            if r.status == ExperimentStatus.TESTED
        ]

        experiments_analyzed = len(tested_results)
        avg_accuracy = 0.0
        avg_forward_return = 0.0
        if tested_results:
            avg_accuracy = sum(r.accuracy for r in tested_results) / len(tested_results)
            avg_forward_return = sum(r.avg_forward_return for r in tested_results) / len(
                tested_results
            )

        best_organism, best_trust = self._best_organism()
        family, top_quality = self._strongest_hypothesis_family()
        strongest_regime = self._strongest_regime(tested_results)
        knowledge_count = self._candidates.count()
        learning_confidence = self._compute_learning_confidence(
            experiments_analyzed,
            tested_results,
            avg_accuracy,
            knowledge_count,
            sources_loaded,
        )
        lessons = self._build_lessons(
            experiments_analyzed=experiments_analyzed,
            avg_accuracy=avg_accuracy,
            avg_forward_return=avg_forward_return,
            best_organism=best_organism,
            best_trust=best_trust,
            family=family,
            top_quality=top_quality,
            regime=strongest_regime,
            knowledge_count=knowledge_count,
            learning_confidence=learning_confidence,
            sources_loaded=sources_loaded,
        )

        return LearningReport(
            experiments_analyzed=experiments_analyzed,
            average_accuracy=avg_accuracy,
            average_forward_return=avg_forward_return,
            best_organism=best_organism,
            strongest_hypothesis_family=family,
            strongest_regime=strongest_regime,
            knowledge_candidates_count=knowledge_count,
            learning_confidence=learning_confidence,
            key_lessons_learned=lessons,
            safety_mode=RESEARCH_SAFETY_BANNER,
            sources_loaded=sources_loaded,
            best_organism_trust_score=best_trust,
            top_quality_score=top_quality,
        )

    def _load_all_sources(self) -> dict[str, bool]:
        loaded: dict[str, bool] = {}

        if not self._experiments.loaded_at_startup:
            self._experiments.load()
        loaded["tae_experiment_results.json"] = self._experiments.count() > 0 or (
            self._experiments.path.is_file()
        )

        if not self._rankings.loaded_at_startup:
            self._rankings.load()
        loaded["tae_hypothesis_rankings.json"] = self._rankings.count() > 0 or (
            self._rankings.path.is_file()
        )

        if not self._candidates.loaded_at_startup:
            self._candidates.load()
        loaded["tae_knowledge_candidates.json"] = self._candidates.count() > 0 or (
            self._candidates.path.is_file()
        )

        if not self._organisms.loaded_at_startup:
            self._organisms.load()
        loaded["tae_organism_memory.json"] = len(self._organisms.all_memories()) > 0 or (
            self._organisms.path.is_file()
        )

        return loaded

    def _best_organism(self) -> tuple[str, float]:
        memories = self._organisms.all_memories()
        if not memories:
            return "unknown", 0.0

        best_name = "unknown"
        best_score = -1.0
        for memory in memories:
            score = memory.trust_score if memory.trust_score > 0 else memory.avg_trust
            if score > best_score:
                best_score = score
                best_name = memory.organism_name
        return best_name, best_score

    def _strongest_hypothesis_family(self) -> tuple[str, float]:
        rankings = self._rankings.list_all()
        if not rankings:
            return "unknown", 0.0

        family_best: dict[str, float] = {}
        for entry in rankings:
            family = entry.duplicate_group or self._slugify(entry.title)
            prev = family_best.get(family, 0.0)
            if entry.quality_score > prev:
                family_best[family] = entry.quality_score

        if not family_best:
            return "unknown", 0.0

        best_family = max(family_best.items(), key=lambda item: (item[1], item[0]))
        return best_family[0], best_family[1]

    def _strongest_regime(self, tested_results: list[Any]) -> str:
        regime_scores: dict[str, list[float]] = defaultdict(list)

        for entry in self._rankings.list_all():
            regime = self._extract_regime_from_text(
                entry.title, entry.duplicate_group
            )
            if regime:
                regime_scores[regime].append(entry.avg_forward_return)

        for result in tested_results:
            regime = self._extract_regime_from_text(result.hypothesis_title, "")
            if regime:
                regime_scores[regime].append(result.avg_forward_return)

        for candidate in self._candidates.list_all():
            regime = self._extract_regime_from_text(candidate.title, "")
            if regime:
                regime_scores[regime].append(candidate.avg_forward_return)

        if not regime_scores:
            return "unknown"

        best = max(
            regime_scores.items(),
            key=lambda item: (
                sum(item[1]) / len(item[1]) if item[1] else 0.0,
                len(item[1]),
            ),
        )
        return best[0]

    def _extract_regime_from_text(self, title: str, extra: str) -> str | None:
        combined = f"{title} {extra}"
        for regime, pattern in REGIME_PATTERNS:
            if pattern.search(combined):
                return regime
        return None

    def _slugify(self, text: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", text.lower().strip())
        return slug.strip("_") or "unknown"

    def _compute_learning_confidence(
        self,
        experiments_analyzed: int,
        tested_results: list[Any],
        avg_accuracy: float,
        knowledge_count: int,
        sources_loaded: dict[str, bool],
    ) -> float:
        if experiments_analyzed == 0:
            sources_ok = sum(1 for v in sources_loaded.values() if v)
            return min(15.0, sources_ok * 3.0)

        avg_sample = sum(r.sample_size for r in tested_results) / len(tested_results)
        sample_pts = min(25.0, (avg_sample / 500.0) * 25.0)
        experiment_pts = min(20.0, experiments_analyzed * 5.0)
        accuracy_pts = min(30.0, avg_accuracy * 30.0)
        candidate_pts = min(10.0, knowledge_count * 5.0)
        source_pts = min(15.0, sum(1 for v in sources_loaded.values() if v) * 3.75)

        total = sample_pts + experiment_pts + accuracy_pts + candidate_pts + source_pts
        return round(min(100.0, max(0.0, total)), 2)

    def _build_lessons(
        self,
        experiments_analyzed: int,
        avg_accuracy: float,
        avg_forward_return: float,
        best_organism: str,
        best_trust: float,
        family: str,
        top_quality: float,
        regime: str,
        knowledge_count: int,
        learning_confidence: float,
        sources_loaded: dict[str, bool],
    ) -> list[str]:
        lessons: list[str] = []

        missing = [name for name, ok in sources_loaded.items() if not ok]
        if missing:
            lessons.append(
                f"Some research sources were missing or empty ({', '.join(missing)}) "
                "— meta-learning confidence is reduced."
            )

        if experiments_analyzed > 0:
            lessons.append(
                f"Analyzed {experiments_analyzed} historical experiment(s): "
                f"mean accuracy {avg_accuracy:.2%}, mean forward return {avg_forward_return:.2f}% "
                "(research cohorts — not live trading outcomes)."
            )
        else:
            lessons.append(
                "No TESTED experiments available yet — run Sprint 5.1 experiment runner "
                "before expecting rich meta-learning."
            )

        if best_organism != "unknown":
            lessons.append(
                f"Organism '{best_organism}' leads calibrated trust "
                f"(score {best_trust:.1f}) across council cycles — weight research reviews accordingly."
            )

        if family != "unknown":
            lessons.append(
                f"Strongest hypothesis family '{family}' (quality score {top_quality:.1f}) "
                "— prioritize further research on this theme, not automatic execution."
            )

        if regime != "unknown":
            lessons.append(
                f"Regime '{regime}' shows the strongest forward-return signal in current "
                "hypothesis titles and rankings — continue regime-conditioned research."
            )

        duplicate_groups = self._rankings.duplicate_groups()
        if duplicate_groups:
            lessons.append(
                f"Detected {len(duplicate_groups)} duplicate hypothesis title group(s) — "
                "meta-learning should treat repeated titles as one discovery, not independent edges."
            )

        if knowledge_count > 0:
            lessons.append(
                f"{knowledge_count} knowledge candidate(s) in registry — pipeline from "
                "hypothesis → experiment → ranking → candidate is producing research objects."
            )
        else:
            lessons.append(
                "No knowledge candidates yet — promote high-quality rankings via Sprint 5.3 "
                "when quality thresholds are met."
            )

        lessons.append(
            f"Overall learning confidence {learning_confidence:.1f}/100 — "
            "research-only meta-learning; does not authorize trading or broker actions."
        )

        return lessons
