"""
TAE Hypothesis generator — derive research hypotheses from council outputs.

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Produces explicit, testable research objects — not trade orders.
"""

from __future__ import annotations

from typing import Any

from research_core.ecosystem.cognitive_layer import CognitiveCycleResult
from research_core.ecosystem.organisms import (
    CONTEXT_ORGANISM_NAME,
    EVIDENCE_ORGANISM_NAME,
    MOMENTUM_ORGANISM_NAME,
)
from research_core.hypothesis.hypothesis_model import Hypothesis, HypothesisStatus, SAFETY_MODE


class HypothesisGenerator:
    """
    Transforms Research Council cycle results into structured hypotheses.
    Sprint 5.1 Experiment Runner will consume UNTESTED hypotheses from the registry.
    """

    def generate_from_council(
        self,
        result: CognitiveCycleResult,
        cycle_label: str,
        registry_sequence_hint: int = 0,
    ) -> list[Hypothesis]:
        decision = result.decision
        packets_by_org = {p.organism_name: p for p in result.packets}

        momentum_packet = packets_by_org.get(MOMENTUM_ORGANISM_NAME)
        context_packet = packets_by_org.get(CONTEXT_ORGANISM_NAME)
        evidence_packet = packets_by_org.get(EVIDENCE_ORGANISM_NAME)

        regime = self._dominant_regime(result.packets)
        momentum_conf = momentum_packet.confidence if momentum_packet else 0.0
        context_conf = context_packet.confidence if context_packet else 0.0
        evidence_conf = evidence_packet.confidence if evidence_packet else 0.0

        organisms = list(decision.contributing_organisms)
        hypotheses: list[Hypothesis] = []

        primary = self._build_primary_hypothesis(
            cycle_label=cycle_label,
            registry_sequence_hint=registry_sequence_hint,
            regime=regime,
            momentum_conf=momentum_conf,
            context_conf=context_conf,
            evidence_conf=evidence_conf,
            decision=decision,
            organisms=organisms,
            momentum_packet=momentum_packet,
            evidence_packet=evidence_packet,
        )
        hypotheses.append(primary)

        council_hypothesis = self._build_council_synthesis_hypothesis(
            cycle_label=cycle_label,
            registry_sequence_hint=registry_sequence_hint + 1,
            decision=decision,
            organisms=organisms,
            regime=regime,
        )
        if council_hypothesis.title != primary.title:
            hypotheses.append(council_hypothesis)

        return hypotheses

    def _dominant_regime(self, packets: list[Any]) -> str:
        regimes: list[str] = []
        for packet in packets:
            features = packet.supporting_features or {}
            regime = features.get("market_regime") or features.get("regime")
            if regime:
                regimes.append(str(regime).upper())
        if not regimes:
            return "NEUTRAL"
        for candidate in ("BULL", "BEAR", "NEUTRAL"):
            if candidate in regimes:
                return candidate
        return regimes[0]

    def _build_primary_hypothesis(
        self,
        cycle_label: str,
        registry_sequence_hint: int,
        regime: str,
        momentum_conf: float,
        context_conf: float,
        evidence_conf: float,
        decision: Any,
        organisms: list[str],
        momentum_packet: Any | None,
        evidence_packet: Any | None,
    ) -> Hypothesis:
        agreement = decision.agreement
        weighted = decision.trust_weighted_confidence or decision.collective_confidence

        if regime == "BULL" and momentum_conf >= 65.0:
            title = "Momentum Continuation Under Bull Regime"
            conditions = {
                "market_regime": "BULL",
                "momentum_confidence_gte": 70.0,
                "agreement_gte": 70.0,
                "trust_weighted_confidence_gte": 65.0,
                "observed_momentum_confidence": round(momentum_conf, 2),
                "observed_agreement": round(agreement, 2),
                "observed_trust_weighted_confidence": round(weighted, 2),
            }
            prediction = "Momentum continuation favored over next 5-10 sessions (research framing)."
            horizon = "10 sessions"
            confidence = min(100.0, (momentum_conf + weighted) / 2.0)
            rationale = (
                f"Council observed BULL regime with momentum confidence {momentum_conf:.1f}, "
                f"agreement {agreement:.1f}%, trust-weighted confidence {weighted:.1f}. "
                "Hypothesis frames continuation as research priority — not a trade order."
            )
        elif regime == "BEAR" and evidence_conf >= 60.0:
            title = "Evidence-Weighted Bear Regime Research Candidate"
            conditions = {
                "market_regime": "BEAR",
                "evidence_confidence_gte": 60.0,
                "collective_decision_level": decision.confidence_level.value,
                "observed_evidence_confidence": round(evidence_conf, 2),
                "observed_trust_weighted_confidence": round(weighted, 2),
            }
            prediction = "Bear-regime evidence dossiers merit structured walk-forward review."
            horizon = "10 sessions"
            confidence = min(100.0, (evidence_conf + weighted) / 2.0)
            rationale = (
                f"Evidence organism confidence {evidence_conf:.1f} in BEAR regime with "
                f"collective {decision.confidence_level.value}. Research validation required."
            )
        elif context_conf >= 55.0 and agreement >= 70.0:
            title = "Context-Aligned Collective Research Path"
            conditions = {
                "market_regime": regime,
                "context_confidence_gte": 55.0,
                "agreement_gte": 70.0,
                "observed_context_confidence": round(context_conf, 2),
                "observed_agreement": round(agreement, 2),
            }
            prediction = "Context-aligned signals deserve cohort analysis before any paper label."
            horizon = "8 sessions"
            confidence = min(100.0, (context_conf + agreement) / 2.0)
            rationale = (
                f"Context research score {context_conf:.1f} with high council agreement "
                f"{agreement:.1f}% in {regime} regime."
            )
        else:
            title = "Council-Weighted Research Watch"
            conditions = {
                "market_regime": regime,
                "collective_confidence_gte": 55.0,
                "observed_trust_weighted_confidence": round(weighted, 2),
                "observed_agreement": round(agreement, 2),
                "decision_level": decision.confidence_level.value,
            }
            prediction = "Collective research posture favors continued observation and dossier review."
            horizon = "5 sessions"
            confidence = weighted
            rationale = (
                f"Default council synthesis: weighted confidence {weighted:.1f}, "
                f"agreement {agreement:.1f}%, regime {regime}. Not an execution signal."
            )

        if momentum_packet and momentum_packet.supporting_features.get("impulse_strength"):
            conditions["impulse_strength"] = momentum_packet.supporting_features["impulse_strength"]

        return Hypothesis(
            hypothesis_id="",  # assigned by registry
            title=title,
            source_cycle=cycle_label,
            source_organisms=organisms,
            conditions=conditions,
            prediction=prediction,
            horizon=horizon,
            confidence=confidence,
            rationale=rationale,
            status=HypothesisStatus.UNTESTED,
            safety_mode=SAFETY_MODE,
        )

    def _build_council_synthesis_hypothesis(
        self,
        cycle_label: str,
        registry_sequence_hint: int,
        decision: Any,
        organisms: list[str],
        regime: str,
    ) -> Hypothesis:
        weighted = decision.trust_weighted_confidence or decision.collective_confidence
        return Hypothesis(
            hypothesis_id="",
            title=f"Trust-Weighted Council Alignment ({regime})",
            source_cycle=cycle_label,
            source_organisms=organisms,
            conditions={
                "market_regime": regime,
                "trust_weighted_confidence_gte": max(55.0, weighted - 5.0),
                "agreement_gte": max(50.0, decision.agreement - 5.0),
                "disagreement_lte": decision.disagreement + 5.0,
                "decision_level": decision.confidence_level.value,
                "trust_weighting_applied": decision.trust_weighting_applied,
            },
            prediction=(
                "Organisms with higher calibrated trust should dominate the next research review cycle."
            ),
            horizon="5 sessions",
            confidence=weighted,
            rationale=(
                f"Council synthesis hypothesis from {len(organisms)} organisms: "
                f"weighted {weighted:.1f}, agreement {decision.agreement:.1f}%. "
                "Prepared for Sprint 5.1 experiment runner — not live execution."
            ),
            status=HypothesisStatus.UNTESTED,
            safety_mode=SAFETY_MODE,
        )
