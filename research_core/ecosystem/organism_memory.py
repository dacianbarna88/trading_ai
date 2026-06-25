"""
Organism memory & performance tracking — Sprint 4.2

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | ANALYSIS_ONLY

Per-organism memory of packets, confidence, trust, actions, and collective participation.
Persisted to tae_organism_memory.json — stdlib json only.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.ecosystem.collective_intelligence import CollectiveDecision
from research_core.ecosystem.evidence_packet import EvidencePacket

logger = logging.getLogger(__name__)

DEFAULT_MEMORY_PATH = Path("tae_organism_memory.json")
SCHEMA_VERSION = 2
SCHEMA_NAME = "tae_organism_memory"
MAX_CONFIDENCE_SAMPLES = 50


@dataclass
class OrganismPerformanceMemory:
    """Accumulated performance memory for one organism."""

    organism_name: str
    cycles_seen: int = 0
    packets_produced: int = 0
    total_confidence: float = 0.0
    total_trust: float = 0.0
    actions_suggested: dict[str, int] = field(default_factory=dict)
    last_seen: str | None = None
    last_summary: str = ""
    last_confidence: float = 0.0
    last_trust: float = 0.0
    last_action: str = ""
    collective_cycles_participated: int = 0
    last_collective_confidence: float = 0.0
    last_collective_level: str = ""
    confidence_samples: list[float] = field(default_factory=list)
    trust_score: float = 0.0
    trust_delta: float = 0.0
    confidence_stability: float = 0.0
    participation_score: float = 0.0
    calibration_reason: str = ""

    @property
    def avg_confidence(self) -> float:
        if self.packets_produced == 0:
            return 0.0
        return round(self.total_confidence / self.packets_produced, 2)

    @property
    def avg_trust(self) -> float:
        if self.packets_produced == 0:
            return 0.0
        return round(self.total_trust / self.packets_produced, 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "organism_name": self.organism_name,
            "cycles_seen": self.cycles_seen,
            "packets_produced": self.packets_produced,
            "avg_confidence": self.avg_confidence,
            "avg_trust": self.avg_trust,
            "total_confidence": round(self.total_confidence, 4),
            "total_trust": round(self.total_trust, 4),
            "actions_suggested": dict(self.actions_suggested),
            "last_seen": self.last_seen,
            "last_summary": self.last_summary,
            "last_confidence": round(self.last_confidence, 2),
            "last_trust": round(self.last_trust, 2),
            "last_action": self.last_action,
            "collective_cycles_participated": self.collective_cycles_participated,
            "last_collective_confidence": round(self.last_collective_confidence, 2),
            "last_collective_level": self.last_collective_level,
            "confidence_samples": [round(v, 2) for v in self.confidence_samples[-MAX_CONFIDENCE_SAMPLES:]],
            "trust_score": round(self.trust_score, 2),
            "trust_delta": round(self.trust_delta, 2),
            "confidence_stability": round(self.confidence_stability, 2),
            "participation_score": round(self.participation_score, 2),
            "calibration_reason": self.calibration_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OrganismPerformanceMemory:
        actions_raw = data.get("actions_suggested", {})
        actions: dict[str, int] = {}
        if isinstance(actions_raw, dict):
            for key, value in actions_raw.items():
                actions[str(key)] = int(value)

        return cls(
            organism_name=str(data.get("organism_name", "")),
            cycles_seen=int(data.get("cycles_seen", 0)),
            packets_produced=int(data.get("packets_produced", 0)),
            total_confidence=float(data.get("total_confidence", 0)),
            total_trust=float(data.get("total_trust", 0)),
            actions_suggested=actions,
            last_seen=data.get("last_seen"),
            last_summary=str(data.get("last_summary", "")),
            last_confidence=float(data.get("last_confidence", 0)),
            last_trust=float(data.get("last_trust", 0)),
            last_action=str(data.get("last_action", "")),
            collective_cycles_participated=int(data.get("collective_cycles_participated", 0)),
            last_collective_confidence=float(data.get("last_collective_confidence", 0)),
            last_collective_level=str(data.get("last_collective_level", "")),
            confidence_samples=[
                float(v) for v in data.get("confidence_samples", []) if isinstance(v, (int, float))
            ][-MAX_CONFIDENCE_SAMPLES:],
            trust_score=float(data.get("trust_score", 0)),
            trust_delta=float(data.get("trust_delta", 0)),
            confidence_stability=float(data.get("confidence_stability", 0)),
            participation_score=float(data.get("participation_score", 0)),
            calibration_reason=str(data.get("calibration_reason", "")),
        )


class OrganismMemoryStore:
    """Tracks and persists per-organism packet memory across cognitive cycles."""

    def __init__(self, path: Path | None = None, auto_load: bool = True) -> None:
        self._path = path or DEFAULT_MEMORY_PATH
        self._organisms: dict[str, OrganismPerformanceMemory] = {}
        self._loaded_from_storage = False
        self._loaded_at_startup = False
        if auto_load:
            self._loaded_at_startup = self.load()
            self._loaded_from_storage = self._loaded_at_startup

    @property
    def loaded_at_startup(self) -> bool:
        return self._loaded_at_startup

    @property
    def path(self) -> Path:
        return self._path

    @property
    def loaded_from_storage(self) -> bool:
        return self._loaded_from_storage

    def get(self, organism_name: str) -> OrganismPerformanceMemory | None:
        return self._organisms.get(organism_name)

    def all_memories(self) -> list[OrganismPerformanceMemory]:
        return list(self._organisms.values())

    def build_trust_weights(self) -> dict[str, float]:
        """Trust scores from calibrated memory for collective weighting."""
        weights: dict[str, float] = {}
        for memory in self._organisms.values():
            if memory.trust_score > 0:
                weights[memory.organism_name] = memory.trust_score
            elif memory.avg_trust > 0:
                weights[memory.organism_name] = memory.avg_trust
        return weights

    def record_packet(self, packet: EvidencePacket, cycle_seen: bool = True) -> OrganismPerformanceMemory:
        memory = self._organisms.setdefault(
            packet.organism_name,
            OrganismPerformanceMemory(organism_name=packet.organism_name),
        )
        if cycle_seen:
            memory.cycles_seen += 1

        memory.packets_produced += 1
        memory.total_confidence += packet.confidence
        memory.total_trust += packet.trust
        action = packet.recommended_action or "UNKNOWN"
        memory.actions_suggested[action] = memory.actions_suggested.get(action, 0) + 1
        memory.last_seen = datetime.now(timezone.utc).isoformat()
        memory.last_confidence = packet.confidence
        memory.last_trust = packet.trust
        memory.last_action = action
        memory.last_summary = packet.observation_summary[:240]
        memory.confidence_samples.append(packet.confidence)
        if len(memory.confidence_samples) > MAX_CONFIDENCE_SAMPLES:
            memory.confidence_samples = memory.confidence_samples[-MAX_CONFIDENCE_SAMPLES:]
        return memory

    def record_cycle(
        self,
        packets: list[EvidencePacket],
        decision: CollectiveDecision | None = None,
    ) -> dict[str, OrganismPerformanceMemory]:
        updated: dict[str, OrganismPerformanceMemory] = {}
        seen_this_cycle: set[str] = set()

        for packet in packets:
            cycle_increment = packet.organism_name not in seen_this_cycle
            if cycle_increment:
                seen_this_cycle.add(packet.organism_name)
            memory = self.record_packet(packet, cycle_seen=cycle_increment)
            if decision is not None:
                memory.collective_cycles_participated += 1
                memory.last_collective_confidence = decision.collective_confidence
                memory.last_collective_level = decision.confidence_level.value
            updated[packet.organism_name] = memory

        return updated

    def load(self) -> bool:
        if not self._path.is_file():
            return False
        try:
            raw = self._path.read_text(encoding="utf-8")
            payload = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Organism memory unreadable (%s): %s", self._path, exc)
            return False

        if not isinstance(payload, dict) or payload.get("schema") != SCHEMA_NAME:
            logger.warning("Organism memory schema mismatch in %s", self._path)
            return False

        organisms_raw = payload.get("organisms", {})
        if not isinstance(organisms_raw, dict):
            return False

        restored: dict[str, OrganismPerformanceMemory] = {}
        for name, item in organisms_raw.items():
            if not isinstance(item, dict):
                continue
            item.setdefault("organism_name", name)
            restored[str(name)] = OrganismPerformanceMemory.from_dict(item)

        self._organisms = restored
        return True

    def persist(self) -> Path:
        payload = {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "organism_count": len(self._organisms),
            "organisms": {
                name: memory.to_dict() for name, memory in sorted(self._organisms.items())
            },
        }
        self._path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        self._loaded_from_storage = True
        return self._path

    def format_summary(self) -> str:
        if not self._organisms:
            return "Organism memory empty."

        lines = ["===== ORGANISM MEMORY SUMMARY =====", ""]
        for name in sorted(self._organisms):
            memory = self._organisms[name]
            actions = ", ".join(
                f"{action}({count})" for action, count in sorted(memory.actions_suggested.items())
            )
            lines.extend(
                [
                    f"  {name}:",
                    f"    cycles_seen: {memory.cycles_seen}",
                    f"    packets_produced: {memory.packets_produced}",
                    f"    avg_confidence: {memory.avg_confidence:.2f}",
                    f"    avg_trust: {memory.avg_trust:.2f}",
                    f"    actions_suggested: {actions or 'none'}",
                    f"    last_seen: {memory.last_seen or 'n/a'}",
                    f"    last_summary: {memory.last_summary[:100]}{'...' if len(memory.last_summary) > 100 else ''}",
                    f"    collective_cycles: {memory.collective_cycles_participated}",
                    f"    last_collective_confidence: {memory.last_collective_confidence:.2f}",
                    f"    trust_score: {memory.trust_score:.2f}",
                    f"    trust_delta: {memory.trust_delta:+.2f}",
                    f"    confidence_stability: {memory.confidence_stability:.2f}",
                    f"    participation_score: {memory.participation_score:.2f}",
                    f"    calibration_reason: {memory.calibration_reason or 'n/a'}",
                    "",
                ]
            )
        return "\n".join(lines)
