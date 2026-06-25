"""Ecosystem health monitoring — structured operational reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from research_core.ecosystem.collective_intelligence import CollectiveIntelligence
from research_core.ecosystem.communication_bus import CommunicationBus
from research_core.ecosystem.knowledge_core import KnowledgeCore
from research_core.ecosystem.organism_registry import OrganismRegistry
from research_core.ecosystem.trust_manager import TrustManager


@dataclass
class HealthReport:
    timestamp: datetime
    active_organisms: list[str]
    trust_distribution: dict[str, float]
    knowledge_count: int
    packet_count: int
    agreement_ratio: float
    learning_events: int
    system_health: str
    organism_health: dict[str, Any] = field(default_factory=dict)
    knowledge_stats: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "active_organisms": self.active_organisms,
            "trust_distribution": self.trust_distribution,
            "knowledge_count": self.knowledge_count,
            "packet_count": self.packet_count,
            "agreement_ratio": round(self.agreement_ratio, 2),
            "learning_events": self.learning_events,
            "system_health": self.system_health,
            "organism_health": self.organism_health,
            "knowledge_stats": self.knowledge_stats,
        }


class HealthMonitor:
    """Aggregates ecosystem signals into a structured health report."""

    def __init__(
        self,
        registry: OrganismRegistry,
        trust_manager: TrustManager,
        knowledge_core: KnowledgeCore,
        bus: CommunicationBus,
        collective: CollectiveIntelligence,
    ) -> None:
        self._registry = registry
        self._trust = trust_manager
        self._knowledge = knowledge_core
        self._bus = bus
        self._collective = collective

    def report(self) -> HealthReport:
        organisms = self._registry.list()
        trust_dist = self._trust.distribution()
        knowledge_stats = self._knowledge.knowledge_statistics()
        organism_health = self._registry.health()

        latest_decision = self._collective.decisions()
        agreement_ratio = 0.0
        if latest_decision:
            agreement_ratio = latest_decision[-1].agreement

        active_count = sum(
            1 for name in organisms
            if organism_health.get(name, {}).get("status") == "healthy"
        )
        health_ratio = active_count / max(len(organisms), 1)
        if health_ratio >= 0.9:
            system_health = "HEALTHY"
        elif health_ratio >= 0.6:
            system_health = "DEGRADED"
        else:
            system_health = "CRITICAL"

        return HealthReport(
            timestamp=datetime.now(timezone.utc),
            active_organisms=organisms,
            trust_distribution=trust_dist,
            knowledge_count=knowledge_stats.get("total_patterns", 0),
            packet_count=self._bus.packet_count(),
            agreement_ratio=agreement_ratio,
            learning_events=len(self._knowledge.learning_events()),
            system_health=system_health,
            organism_health=organism_health,
            knowledge_stats=knowledge_stats,
        )
