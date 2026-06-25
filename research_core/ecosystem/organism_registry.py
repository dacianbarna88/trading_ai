"""Organism registry — discovery and hot-plug support."""

from __future__ import annotations

from typing import Any

from research_core.ecosystem.organism import Organism
from research_core.ecosystem.trust_manager import TrustManager


class OrganismRegistry:
    """
    Registers organisms for ecosystem discovery and health reporting.
    Supports future hot-plug of new research organisms.
    """

    def __init__(self, trust_manager: TrustManager) -> None:
        self._organisms: dict[str, Organism] = {}
        self._trust_manager = trust_manager

    def register(self, organism: Organism, initial_trust: float | None = None) -> str:
        name = organism.name
        if name in self._organisms:
            raise ValueError(f"Organism already registered: {name}")
        self._organisms[name] = organism
        self._trust_manager.register(name, initial_trust)
        return name

    def unregister(self, name: str) -> bool:
        if name not in self._organisms:
            return False
        del self._organisms[name]
        return True

    def get(self, name: str) -> Organism | None:
        return self._organisms.get(name)

    def list(self) -> list[str]:
        return sorted(self._organisms.keys())

    def list_organisms(self) -> list[Organism]:
        return list(self._organisms.values())

    def health(self) -> dict[str, Any]:
        report: dict[str, Any] = {}
        for name, organism in self._organisms.items():
            status = organism.health_status()
            status["trust"] = self._trust_manager.current(name)
            report[name] = status
        return report

    def count(self) -> int:
        return len(self._organisms)
