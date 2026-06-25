"""
Organism trust calibration — Sprint 4.3

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | ANALYSIS_ONLY

Conservative trust adjustments from organism memory: stability, participation, confidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from research_core.ecosystem.organism_memory import OrganismMemoryStore, OrganismPerformanceMemory

TRUST_MIN = 0.0
TRUST_MAX = 100.0
MAX_DELTA_PER_CALIBRATION = 3.0


def clamp_trust(value: float) -> float:
    return max(TRUST_MIN, min(TRUST_MAX, round(value, 2)))


@dataclass
class TrustCalibrationResult:
    organism_name: str
    previous_trust: float
    new_trust: float
    trust_delta: float
    confidence_stability: float
    participation_score: float
    calibration_reason: str

    def to_dict(self) -> dict[str, float | str]:
        return {
            "organism_name": self.organism_name,
            "previous_trust": self.previous_trust,
            "new_trust": self.new_trust,
            "trust_delta": self.trust_delta,
            "confidence_stability": self.confidence_stability,
            "participation_score": self.participation_score,
            "calibration_reason": self.calibration_reason,
        }


class TrustCalibrator:
    """
    Adjusts organism trust from accumulated memory using conservative rules.
    """

    def __init__(self, max_delta: float = MAX_DELTA_PER_CALIBRATION) -> None:
        self._max_delta = max(0.5, min(max_delta, 5.0))

    def compute_confidence_stability(self, memory: OrganismPerformanceMemory) -> float:
        samples = memory.confidence_samples
        if len(samples) < 2:
            if len(samples) == 1:
                return 55.0
            return 40.0

        mean = sum(samples) / len(samples)
        variance = sum((value - mean) ** 2 for value in samples) / len(samples)
        # Low variance => high stability; std dev ~0-20 typical for confidence
        std = variance ** 0.5
        stability = 100.0 - min(50.0, std * 2.5)
        return round(max(0.0, min(100.0, stability)), 2)

    def compute_participation_score(self, memory: OrganismPerformanceMemory) -> float:
        if memory.packets_produced == 0:
            return 0.0
        cycle_component = min(50.0, memory.cycles_seen * 12.0)
        collective_component = min(30.0, memory.collective_cycles_participated * 8.0)
        packet_component = min(20.0, memory.packets_produced * 4.0)
        return round(min(100.0, cycle_component + collective_component + packet_component), 2)

    def _baseline_trust(self, memory: OrganismPerformanceMemory) -> float:
        if memory.trust_score > 0:
            return memory.trust_score
        if memory.packets_produced > 0 and memory.avg_trust > 0:
            return memory.avg_trust
        return 50.0

    def calibrate(self, memory: OrganismPerformanceMemory) -> TrustCalibrationResult:
        if memory.packets_produced == 0:
            baseline = self._baseline_trust(memory)
            memory.confidence_stability = self.compute_confidence_stability(memory)
            memory.participation_score = 0.0
            memory.trust_delta = 0.0
            memory.calibration_reason = "No packets produced — trust unchanged."
            return TrustCalibrationResult(
                organism_name=memory.organism_name,
                previous_trust=baseline,
                new_trust=baseline,
                trust_delta=0.0,
                confidence_stability=memory.confidence_stability,
                participation_score=0.0,
                calibration_reason=memory.calibration_reason,
            )

        stability = self.compute_confidence_stability(memory)
        participation = self.compute_participation_score(memory)
        memory.confidence_stability = stability
        memory.participation_score = participation

        previous = self._baseline_trust(memory)
        delta = 0.0
        reasons: list[str] = []

        if stability >= 80.0:
            delta += 1.0
            reasons.append(f"high confidence stability ({stability:.0f})")
        elif stability < 45.0:
            delta -= 1.0
            reasons.append(f"low confidence stability ({stability:.0f})")

        if participation >= 60.0:
            delta += 1.0
            reasons.append(f"strong participation ({participation:.0f})")
        elif participation < 25.0:
            delta -= 0.5
            reasons.append(f"limited participation ({participation:.0f})")

        avg_conf = memory.avg_confidence
        if avg_conf >= 70.0 and stability >= 60.0:
            delta += 0.5
            reasons.append(f"sustained confidence ({avg_conf:.1f})")
        elif avg_conf < 40.0:
            delta -= 1.0
            reasons.append(f"weak average confidence ({avg_conf:.1f})")

        if memory.last_collective_confidence >= 65.0 and memory.collective_cycles_participated > 0:
            delta += 0.5
            reasons.append(
                f"constructive collective role (collective {memory.last_collective_confidence:.1f})"
            )

        delta = max(-self._max_delta, min(self._max_delta, delta))
        new_trust = clamp_trust(previous + delta)

        if not reasons:
            reason = "Stable profile — conservative hold."
        else:
            sign = "+" if delta >= 0 else ""
            reason = f"{sign}{delta:.1f}: " + "; ".join(reasons)

        memory.trust_score = new_trust
        memory.trust_delta = round(new_trust - previous, 2)
        memory.calibration_reason = reason

        return TrustCalibrationResult(
            organism_name=memory.organism_name,
            previous_trust=round(previous, 2),
            new_trust=new_trust,
            trust_delta=memory.trust_delta,
            confidence_stability=stability,
            participation_score=participation,
            calibration_reason=reason,
        )

    def calibrate_store(self, memory_store: OrganismMemoryStore) -> list[TrustCalibrationResult]:
        results: list[TrustCalibrationResult] = []
        for memory in memory_store.all_memories():
            results.append(self.calibrate(memory))
        return results

    def format_report(self, results: list[TrustCalibrationResult]) -> str:
        if not results:
            return "No trust calibration results."

        lines = ["===== TRUST CALIBRATION =====", ""]
        for result in sorted(results, key=lambda r: r.organism_name):
            lines.extend(
                [
                    f"  {result.organism_name}:",
                    f"    previous trust: {result.previous_trust:.2f}",
                    f"    new trust: {result.new_trust:.2f}",
                    f"    trust delta: {result.trust_delta:+.2f}",
                    f"    confidence_stability: {result.confidence_stability:.2f}",
                    f"    participation_score: {result.participation_score:.2f}",
                    f"    reason: {result.calibration_reason}",
                    "",
                ]
            )
        return "\n".join(lines)
