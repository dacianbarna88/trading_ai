"""
Discovery-to-Hypothesis bridge — Phase IV Sprint D2

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Converts selected NEW discoveries into UNTESTED hypotheses for future testing.
A discovery is not a hypothesis — this bridge creates research objects only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.discovery.discovery_model import (
    Discovery,
    DiscoveryCategory,
    DiscoveryStatus,
)
from research_core.discovery.discovery_registry import DiscoveryRegistry
from research_core.hypothesis.hypothesis_model import Hypothesis, HypothesisStatus, SAFETY_MODE
from research_core.hypothesis.hypothesis_registry import HypothesisRegistry

DEFAULT_MIN_CONFIDENCE = 60.0
DEFAULT_MIN_NOVELTY = 50.0
ORGANISM_PATTERN = re.compile(r"([a-z][a-z0-9_]*_organism)", re.IGNORECASE)
ORGANISM_EXCLUDE = frozenset({"best_organism", "dominant_organism"})
REGIME_PATTERN = re.compile(r"\b(BULL|BEAR|NEUTRAL)\b", re.IGNORECASE)
FAMILY_PATTERN = re.compile(r"'([a-z0-9_]+)'", re.IGNORECASE)


@dataclass
class BridgeResult:
    discoveries_loaded: int = 0
    eligible_count: int = 0
    hypotheses_created: list[Hypothesis] = field(default_factory=list)
    skipped_duplicates: list[str] = field(default_factory=list)
    skipped_ineligible: list[str] = field(default_factory=list)
    discoveries_updated: list[str] = field(default_factory=list)

    @property
    def created_count(self) -> int:
        return len(self.hypotheses_created)

    @property
    def skipped_duplicate_count(self) -> int:
        return len(self.skipped_duplicates)


class DiscoveryToHypothesisBridge:
    """
    Converts qualifying discoveries into UNTESTED hypotheses.
    Sprint D2 — does not run experiments or touch execution paths.
    """

    def __init__(
        self,
        discovery_registry: DiscoveryRegistry | None = None,
        hypothesis_registry: HypothesisRegistry | None = None,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        min_novelty: float = DEFAULT_MIN_NOVELTY,
    ) -> None:
        self._discoveries = discovery_registry or DiscoveryRegistry()
        self._hypotheses = hypothesis_registry or HypothesisRegistry()
        self._min_confidence = min_confidence
        self._min_novelty = min_novelty

    @property
    def discovery_registry(self) -> DiscoveryRegistry:
        return self._discoveries

    @property
    def hypothesis_registry(self) -> HypothesisRegistry:
        return self._hypotheses

    def convert(self) -> BridgeResult:
        if not self._discoveries.loaded_at_startup:
            self._discoveries.load()
        if not self._hypotheses.loaded_at_startup:
            self._hypotheses.load()

        result = BridgeResult(discoveries_loaded=self._discoveries.count())

        for discovery in self._discoveries.list_all():
            if not self._is_eligible(discovery):
                result.skipped_ineligible.append(
                    f"{discovery.discovery_id} ({discovery.status.value}, "
                    f"conf={discovery.confidence:.1f}, novelty={discovery.novelty_score:.1f})"
                )
                continue

            result.eligible_count += 1

            if self._has_hypothesis_for_discovery(discovery.discovery_id):
                result.skipped_duplicates.append(discovery.discovery_id)
                if discovery.status == DiscoveryStatus.NEW:
                    discovery.status = DiscoveryStatus.LINKED
                    result.discoveries_updated.append(discovery.discovery_id)
                continue

            hypothesis = self._discovery_to_hypothesis(discovery)
            hypothesis.hypothesis_id = self._hypotheses.next_id(prefix="hyp_d2")
            self._hypotheses.add_generated(hypothesis)
            result.hypotheses_created.append(hypothesis)

            discovery.status = DiscoveryStatus.CONVERTED
            result.discoveries_updated.append(discovery.discovery_id)

        return result

    def _is_eligible(self, discovery: Discovery) -> bool:
        return (
            discovery.status == DiscoveryStatus.NEW
            and discovery.confidence >= self._min_confidence
            and discovery.novelty_score >= self._min_novelty
        )

    def _has_hypothesis_for_discovery(self, discovery_id: str) -> bool:
        for hypothesis in self._hypotheses.list_all():
            if hypothesis.source_cycle == discovery_id:
                return True
            conditions = hypothesis.conditions
            if conditions.get("discovery_id") == discovery_id:
                return True
        return False

    def _discovery_to_hypothesis(self, discovery: Discovery) -> Hypothesis:
        title = self._build_title(discovery)
        organisms = self._extract_organisms(discovery)
        conditions = self._build_conditions(discovery)
        prediction = self._build_prediction(discovery)
        horizon = self._build_horizon(discovery)
        confidence = min(
            100.0,
            (discovery.confidence * 0.6 + discovery.novelty_score * 0.4),
        )
        rationale = (
            f"Hypothesis bridged from discovery {discovery.discovery_id} "
            f"(category={discovery.category}). "
            f"Evidence: {discovery.evidence[:200]}{'...' if len(discovery.evidence) > 200 else ''} "
            "Research hypothesis for future experiment — not a trade order."
        )

        return Hypothesis(
            hypothesis_id="",
            title=title,
            source_cycle=discovery.discovery_id,
            source_organisms=organisms,
            conditions=conditions,
            prediction=prediction,
            horizon=horizon,
            confidence=confidence,
            rationale=rationale,
            status=HypothesisStatus.UNTESTED,
            safety_mode=SAFETY_MODE,
        )

    def _build_title(self, discovery: Discovery) -> str:
        raw = discovery.title.strip()
        if raw.lower().startswith("from discovery:"):
            return raw[:120]
        return f"From Discovery: {raw}"[:120]

    def _extract_organisms(self, discovery: Discovery) -> list[str]:
        text = f"{discovery.title} {discovery.description} {discovery.evidence}"
        found = ORGANISM_PATTERN.findall(text)
        unique: list[str] = []
        seen: set[str] = set()
        for name in found:
            lower = name.lower()
            if lower in ORGANISM_EXCLUDE or lower in seen:
                continue
            seen.add(lower)
            unique.append(name)
        if discovery.category == DiscoveryCategory.ORGANISM_DOMINANCE.value and not unique:
            unique.append("evidence_engine_v40_organism")
        return unique

    def _build_conditions(self, discovery: Discovery) -> dict[str, Any]:
        conditions: dict[str, Any] = {
            "discovery_id": discovery.discovery_id,
            "discovery_category": discovery.category,
            "discovery_confidence": discovery.confidence,
            "discovery_novelty_score": discovery.novelty_score,
            "source_experiments": list(discovery.source_experiments),
            "bridged_from_discovery": True,
        }

        regimes = REGIME_PATTERN.findall(
            f"{discovery.title} {discovery.description} {discovery.evidence}"
        )
        if regimes:
            conditions["market_regime"] = regimes[0].upper()
            conditions["regimes_observed"] = list(dict.fromkeys(r.upper() for r in regimes))

        families = FAMILY_PATTERN.findall(discovery.description + discovery.evidence)
        if families:
            conditions["hypothesis_families"] = families[:4]

        category = discovery.category
        if category == DiscoveryCategory.HIGH_PERFORMING_CLUSTER.value:
            conditions["cluster_comparison"] = True
            conditions["momentum_confidence_gte"] = 65.0
            if "momentum" in discovery.title.lower():
                conditions["focus_family"] = "momentum_continuation"
        elif category == DiscoveryCategory.CROSS_REGIME_ANOMALY.value:
            conditions["cross_regime_validation"] = True
            conditions["target_regimes"] = ["BEAR", "NEUTRAL"]
            conditions["baseline_regime"] = conditions.get("market_regime", "BULL")
        elif category == DiscoveryCategory.ORGANISM_DOMINANCE.value:
            organisms = self._extract_organisms(discovery)
            if organisms:
                conditions["dominant_organism"] = organisms[0]
            conditions["organism_attribution_test"] = True
        elif category == DiscoveryCategory.FORWARD_RETURN_ANOMALY.value:
            conditions["forward_return_threshold_pct"] = 6.0
            conditions["validate_forward_return_tail"] = True

        return conditions

    def _build_prediction(self, discovery: Discovery) -> str:
        return (
            f"If re-tested as a structured hypothesis, the pattern described in "
            f"'{discovery.title}' should hold under research cohort filters: "
            f"{discovery.description[:150]}{'...' if len(discovery.description) > 150 else ''} "
            "(research framing — not a BUY/SELL signal)."
        )

    def _build_horizon(self, discovery: Discovery) -> str:
        if discovery.category == DiscoveryCategory.CROSS_REGIME_ANOMALY.value:
            return "20 sessions"
        if discovery.category == DiscoveryCategory.FORWARD_RETURN_ANOMALY.value:
            return "60 sessions"
        return "10 sessions"
