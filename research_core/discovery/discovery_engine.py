"""
Research discovery engine — Phase IV Sprint D1

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Searches experiment history, rankings, learning report, and knowledge candidates
for unexpected statistical relationships worth future research.
Not BUY/SELL signals, not hypotheses, not execution paths.
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.discovery.discovery_model import (
    Discovery,
    DiscoveryCategory,
    DiscoveryStatus,
)
from research_core.discovery.discovery_registry import DiscoveryRegistry
from research_core.hypothesis.experiment_result import ExperimentStatus
from research_core.hypothesis.experiment_runner import ExperimentResultsStore
from research_core.hypothesis.hypothesis_ranking import HypothesisRankingsStore
from research_core.hypothesis.knowledge_candidate import KnowledgeCandidateRegistry
from research_core.learning.learning_report import DEFAULT_REPORT_PATH, LearningReport

logger = logging.getLogger(__name__)

HIGH_RETURN_THRESHOLD = 6.0
CLUSTER_QUALITY_GAP = 2.0
REGIME_PATTERN = re.compile(r"\b(BULL|BEAR|NEUTRAL)\b", re.IGNORECASE)


@dataclass
class DiscoveryRunResult:
    discovered: list[Discovery] = field(default_factory=list)
    skipped_duplicates: list[str] = field(default_factory=list)
    sources_loaded: dict[str, bool] = field(default_factory=dict)
    candidates_evaluated: int = 0

    @property
    def new_count(self) -> int:
        return len(self.discovered)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped_duplicates)


class ResearchDiscoveryEngine:
    """
    Phase IV discovery engine — meta-analysis over Sprint 5 research artifacts.
    Finds research opportunities; does not emit trade signals.
    """

    def __init__(
        self,
        registry: DiscoveryRegistry | None = None,
        experiment_store: ExperimentResultsStore | None = None,
        rankings_store: HypothesisRankingsStore | None = None,
        candidate_registry: KnowledgeCandidateRegistry | None = None,
        learning_report_path: Path | None = None,
    ) -> None:
        self._registry = registry or DiscoveryRegistry()
        self._experiments = experiment_store or ExperimentResultsStore()
        self._rankings = rankings_store or HypothesisRankingsStore()
        self._candidates = candidate_registry or KnowledgeCandidateRegistry()
        self._learning_path = learning_report_path or DEFAULT_REPORT_PATH

    @property
    def registry(self) -> DiscoveryRegistry:
        return self._registry

    def run(self) -> DiscoveryRunResult:
        sources_loaded = self._load_sources()
        learning = self._load_learning_report()

        tested = [
            r
            for r in self._experiments.list_all()
            if r.status == ExperimentStatus.TESTED
        ]
        rankings = self._rankings.list_all()

        candidates: list[Discovery] = []
        candidates.extend(self._detect_high_performing_clusters(rankings, tested))
        candidates.extend(self._detect_cross_regime_anomalies(rankings, tested, learning))
        candidates.extend(self._detect_organism_dominance(learning, tested))
        candidates.extend(self._detect_forward_return_anomalies(rankings, tested, learning))

        result = DiscoveryRunResult(
            sources_loaded=sources_loaded,
            candidates_evaluated=len(candidates),
        )

        for discovery in candidates:
            registered, is_new = self._registry.try_register(discovery)
            if is_new and registered is not None:
                result.discovered.append(registered)
            else:
                label = registered.title if registered else discovery.title
                result.skipped_duplicates.append(label)

        return result

    def _load_sources(self) -> dict[str, bool]:
        loaded: dict[str, bool] = {}

        if not self._experiments.loaded_at_startup:
            self._experiments.load()
        loaded["tae_experiment_results.json"] = (
            self._experiments.count() > 0 or self._experiments.path.is_file()
        )

        if not self._rankings.loaded_at_startup:
            self._rankings.load()
        loaded["tae_hypothesis_rankings.json"] = (
            self._rankings.count() > 0 or self._rankings.path.is_file()
        )

        if not self._candidates.loaded_at_startup:
            self._candidates.load()
        loaded["tae_knowledge_candidates.json"] = (
            self._candidates.count() > 0 or self._candidates.path.is_file()
        )

        loaded["tae_learning_report.json"] = self._learning_path.is_file()

        return loaded

    def _load_learning_report(self) -> LearningReport | None:
        if not self._learning_path.is_file():
            return None
        try:
            raw = self._learning_path.read_text(encoding="utf-8")
            payload = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Learning report unreadable: %s", exc)
            return None
        if not isinstance(payload, dict):
            return None
        return LearningReport.from_dict(payload)

    def _experiment_ids_for_hypotheses(
        self, hypothesis_ids: list[str], tested: list[Any],
    ) -> list[str]:
        ids: list[str] = []
        hid_set = set(hypothesis_ids)
        for result in tested:
            if result.hypothesis_id in hid_set:
                ids.append(result.experiment_id)
        return ids

    def _family_stats(self, rankings: list[Any]) -> dict[str, dict[str, float]]:
        """Best entry per duplicate_group family."""
        families: dict[str, dict[str, Any]] = {}
        for entry in rankings:
            family = entry.duplicate_group or entry.title
            prev = families.get(family)
            if prev is None or entry.quality_score > prev["quality_score"]:
                families[family] = {
                    "quality_score": entry.quality_score,
                    "accuracy": entry.accuracy,
                    "avg_forward_return": entry.avg_forward_return,
                    "hypothesis_id": entry.hypothesis_id,
                    "title": entry.title,
                }
        return families

    def _detect_high_performing_clusters(
        self,
        rankings: list[Any],
        tested: list[Any],
    ) -> list[Discovery]:
        if len(rankings) < 2:
            return []

        families = self._family_stats(rankings)
        if len(families) < 2:
            return []

        sorted_families = sorted(
            families.items(),
            key=lambda item: item[1]["quality_score"],
            reverse=True,
        )
        best_family, best_stats = sorted_families[0]
        second_family, second_stats = sorted_families[1]
        gap = best_stats["quality_score"] - second_stats["quality_score"]

        if gap < CLUSTER_QUALITY_GAP:
            return []

        member_ids = [
            e.hypothesis_id
            for e in rankings
            if (e.duplicate_group or e.title) == best_family
        ]
        exp_ids = self._experiment_ids_for_hypotheses(member_ids, tested)

        title = f"High-Performing Cluster: {best_stats['title'][:60]}"
        description = (
            f"Hypothesis family '{best_family}' leads quality rankings "
            f"(score {best_stats['quality_score']:.1f}) vs "
            f"'{second_family}' ({second_stats['quality_score']:.1f}) — "
            f"gap {gap:.1f} points. Unexpected cluster outperformance for research."
        )
        evidence = (
            f"Family '{best_family}': quality={best_stats['quality_score']:.2f}, "
            f"accuracy={best_stats['accuracy']:.2%}, "
            f"avg_return={best_stats['avg_forward_return']:.2f}%. "
            f"Runner-up '{second_family}': quality={second_stats['quality_score']:.2f}. "
            "Derived from hypothesis rankings — not live trading."
        )

        return [
            Discovery(
                discovery_id="",
                title=title,
                description=description,
                evidence=evidence,
                confidence=min(95.0, 55.0 + gap * 2.0),
                novelty_score=min(90.0, 40.0 + gap * 3.0),
                source_experiments=exp_ids,
                suggested_next_step=(
                    f"Design cross-family control experiments comparing "
                    f"'{best_family}' vs '{second_family}' on identical cohort filters "
                    "(research only — not a trade signal)."
                ),
                status=DiscoveryStatus.NEW,
                category=DiscoveryCategory.HIGH_PERFORMING_CLUSTER.value,
            )
        ]

    def _detect_cross_regime_anomalies(
        self,
        rankings: list[Any],
        tested: list[Any],
        learning: LearningReport | None,
    ) -> list[Discovery]:
        regimes_in_titles: dict[str, int] = defaultdict(int)
        for entry in rankings:
            for regime in self._extract_regimes(entry.title):
                regimes_in_titles[regime] += 1
        for result in tested:
            for regime in self._extract_regimes(result.hypothesis_title):
                regimes_in_titles[regime] += 1

        if not regimes_in_titles:
            return []

        dominant_regime = max(regimes_in_titles.items(), key=lambda x: x[1])[0]
        other_regimes = [r for r in regimes_in_titles if r != dominant_regime]

        if other_regimes and regimes_in_titles[dominant_regime] <= max(
            regimes_in_titles.get(r, 0) for r in other_regimes
        ):
            return []

        if len(regimes_in_titles) == 1 and dominant_regime:
            exp_ids = [r.experiment_id for r in tested]
            title = f"Cross-Regime Gap: {dominant_regime}-Only Research Coverage"
            description = (
                f"All ranked/tested hypotheses reference '{dominant_regime}' regime. "
                "No BEAR or NEUTRAL regime families in current experiment set — "
                "cross-regime performance unknown."
            )
            evidence = (
                f"Regime label counts in titles: {dict(regimes_in_titles)}. "
                f"Learning report strongest regime: "
                f"{learning.strongest_regime if learning else 'unknown'}. "
                "Anomaly: strong signals may be regime-specific."
            )
            return [
                Discovery(
                    discovery_id="",
                    title=title,
                    description=description,
                    evidence=evidence,
                    confidence=72.0,
                    novelty_score=68.0,
                    source_experiments=exp_ids,
                    suggested_next_step=(
                        f"Run Sprint 6 cross-regime experiment matrix for "
                        f"top families in BEAR and NEUTRAL cohorts "
                        "(research only — no execution)."
                    ),
                    status=DiscoveryStatus.NEW,
                    category=DiscoveryCategory.CROSS_REGIME_ANOMALY.value,
                )
            ]

        if len(regimes_in_titles) >= 2:
            regime_returns: dict[str, list[float]] = defaultdict(list)
            for entry in rankings:
                for regime in self._extract_regimes(entry.title):
                    regime_returns[regime].append(entry.avg_forward_return)

            if len(regime_returns) >= 2:
                avg_by_regime = {
                    r: sum(v) / len(v) for r, v in regime_returns.items() if v
                }
                best_r = max(avg_by_regime.items(), key=lambda x: x[1])
                worst_r = min(avg_by_regime.items(), key=lambda x: x[1])
                spread = best_r[1] - worst_r[1]
                if spread >= 1.0:
                    return [
                        Discovery(
                            discovery_id="",
                            title=f"Cross-Regime Spread: {best_r[0]} vs {worst_r[0]}",
                            description=(
                                f"Regime '{best_r[0]}' avg forward return "
                                f"{best_r[1]:.2f}% vs '{worst_r[0]}' "
                                f"{worst_r[1]:.2f}% — spread {spread:.2f}%."
                            ),
                            evidence=str(dict(avg_by_regime)),
                            confidence=min(90.0, 50.0 + spread * 5.0),
                            novelty_score=min(85.0, 45.0 + spread * 4.0),
                            source_experiments=[r.experiment_id for r in tested],
                            suggested_next_step=(
                                "Investigate regime-conditioned cohort filters "
                                "before generalizing any hypothesis family."
                            ),
                            status=DiscoveryStatus.NEW,
                            category=DiscoveryCategory.CROSS_REGIME_ANOMALY.value,
                        )
                    ]

        return []

    def _detect_organism_dominance(
        self,
        learning: LearningReport | None,
        tested: list[Any],
    ) -> list[Discovery]:
        if learning is None or not learning.best_organism:
            return []

        best = learning.best_organism
        trust = learning.best_organism_trust_score
        if trust < 70.0:
            return []

        exp_ids = [r.experiment_id for r in tested]
        title = f"Organism Dominance: {best}"
        description = (
            f"Organism '{best}' leads calibrated trust "
            f"(score {trust:.1f}) across council cycles and learning meta-analysis. "
            "Evidence organism may predict research outcomes better than peers."
        )
        evidence = (
            f"Learning report best_organism={best}, trust={trust:.1f}. "
            f"Learning confidence={learning.learning_confidence:.1f}/100. "
            "Unexpected organism dominance pattern for research prioritization."
        )

        confidence = min(92.0, trust * 0.85)
        novelty = 55.0 if "evidence" in best.lower() else 70.0

        return [
            Discovery(
                discovery_id="",
                title=title,
                description=description,
                evidence=evidence,
                confidence=confidence,
                novelty_score=novelty,
                source_experiments=exp_ids,
                suggested_next_step=(
                    f"Run organism-attribution experiments: compare council outputs "
                    f"when '{best}' is excluded vs included (research framing only)."
                ),
                status=DiscoveryStatus.NEW,
                category=DiscoveryCategory.ORGANISM_DOMINANCE.value,
            )
        ]

    def _detect_forward_return_anomalies(
        self,
        rankings: list[Any],
        tested: list[Any],
        learning: LearningReport | None,
    ) -> list[Discovery]:
        discoveries: list[Discovery] = []

        families = self._family_stats(rankings)
        high_return_families = [
            (fam, stats)
            for fam, stats in families.items()
            if stats["avg_forward_return"] >= HIGH_RETURN_THRESHOLD
        ]

        if high_return_families:
            fam, stats = max(high_return_families, key=lambda x: x[1]["avg_forward_return"])
            member_ids = [
                e.hypothesis_id
                for e in rankings
                if (e.duplicate_group or e.title) == fam
            ]
            exp_ids = self._experiment_ids_for_hypotheses(member_ids, tested)
            overall_avg = learning.average_forward_return if learning else 0.0
            excess = stats["avg_forward_return"] - overall_avg

            discoveries.append(
                Discovery(
                    discovery_id="",
                    title=f"Forward Return Anomaly: >{HIGH_RETURN_THRESHOLD}% in {fam}",
                    description=(
                        f"Family '{fam}' shows avg forward return "
                        f"{stats['avg_forward_return']:.2f}% "
                        f"(overall mean {overall_avg:.2f}%). "
                        f"Excess ~{excess:.2f}% — statistically notable for research."
                    ),
                    evidence=(
                        f"Threshold>{HIGH_RETURN_THRESHOLD}%. "
                        f"Family return={stats['avg_forward_return']:.2f}%, "
                        f"accuracy={stats['accuracy']:.2%}, n from rankings. "
                        "Not a BUY signal — research anomaly only."
                    ),
                    confidence=min(88.0, 50.0 + excess * 4.0),
                    novelty_score=min(80.0, 40.0 + excess * 3.0),
                    source_experiments=exp_ids,
                    suggested_next_step=(
                        "Validate forward-return tail in out-of-sample cohort "
                        f"for family '{fam}' before hypothesis promotion."
                    ),
                    status=DiscoveryStatus.NEW,
                    category=DiscoveryCategory.FORWARD_RETURN_ANOMALY.value,
                )
            )

        high_count = sum(1 for r in tested if r.avg_forward_return >= HIGH_RETURN_THRESHOLD)
        if len(tested) >= 2 and high_count >= len(tested) // 2 + 1:
            discoveries.append(
                Discovery(
                    discovery_id="",
                    title="Broad Forward Return Elevated Across Experiments",
                    description=(
                        f"{high_count}/{len(tested)} experiments show avg forward return "
                        f">={HIGH_RETURN_THRESHOLD}% — unusually high cohort baseline."
                    ),
                    evidence=(
                        f"Experiment returns: "
                        + ", ".join(f"{r.avg_forward_return:.2f}%" for r in tested)
                    ),
                    confidence=65.0,
                    novelty_score=60.0,
                    source_experiments=[r.experiment_id for r in tested],
                    suggested_next_step=(
                        "Audit cohort selection filters — elevated baseline may "
                        "reflect BULL-only sampling rather than universal edge."
                    ),
                    status=DiscoveryStatus.NEW,
                    category=DiscoveryCategory.FORWARD_RETURN_ANOMALY.value,
                )
            )

        return discoveries

    def _extract_regimes(self, text: str) -> list[str]:
        return [m.upper() for m in REGIME_PATTERN.findall(text)]
