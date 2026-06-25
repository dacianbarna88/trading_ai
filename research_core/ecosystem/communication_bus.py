"""Publish/subscribe communication bus — organisms never call each other directly."""

from __future__ import annotations

from collections import defaultdict
from typing import Callable

from research_core.ecosystem.evidence_packet import EvidencePacket

PacketHandler = Callable[[EvidencePacket], None]


class CommunicationBus:
    """
    Central message router for EvidencePackets.
    Organisms publish; Knowledge Core and Collective Intelligence subscribe.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[PacketHandler]] = defaultdict(list)
        self._published: list[EvidencePacket] = []

    def subscribe(self, channel: str, handler: PacketHandler) -> None:
        self._subscribers[channel].append(handler)

    def unsubscribe(self, channel: str, handler: PacketHandler) -> None:
        handlers = self._subscribers.get(channel, [])
        if handler in handlers:
            handlers.remove(handler)

    def publish(self, packet: EvidencePacket, channel: str = "evidence") -> None:
        self._published.append(packet)
        for handler in self._subscribers.get(channel, []):
            handler(packet)
        for handler in self._subscribers.get("*", []):
            handler(packet)

    def published_packets(self) -> list[EvidencePacket]:
        return list(self._published)

    def packet_count(self) -> int:
        return len(self._published)

    def subscriber_count(self, channel: str = "evidence") -> int:
        return len(self._subscribers.get(channel, []))
