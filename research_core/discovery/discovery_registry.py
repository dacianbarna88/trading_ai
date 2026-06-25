"""
Discovery registry — Phase IV Sprint D1 JSON persistence.

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.discovery.discovery_model import Discovery

logger = logging.getLogger(__name__)

DEFAULT_REGISTRY_PATH = Path("tae_discoveries.json")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_discoveries"


class DiscoveryRegistry:
    """Persistent store for research discoveries — stdlib json only."""

    def __init__(self, path: Path | None = None, auto_load: bool = True) -> None:
        self._path = path or DEFAULT_REGISTRY_PATH
        self._discoveries: dict[str, Discovery] = {}
        self._by_fingerprint: dict[str, str] = {}
        self._sequence: int = 0
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
        return len(self._discoveries)

    def list_all(self) -> list[Discovery]:
        return sorted(self._discoveries.values(), key=lambda d: d.created_at)

    def get(self, discovery_id: str) -> Discovery | None:
        return self._discoveries.get(discovery_id)

    def has_fingerprint(self, fingerprint: str) -> bool:
        return fingerprint in self._by_fingerprint

    def get_by_fingerprint(self, fingerprint: str) -> Discovery | None:
        did = self._by_fingerprint.get(fingerprint)
        if did is None:
            return None
        return self._discoveries.get(did)

    def next_id(self, prefix: str = "disc_d1") -> str:
        self._sequence += 1
        return f"{prefix}_{self._sequence:05d}"

    def register(self, discovery: Discovery) -> Discovery:
        if discovery.fingerprint in self._by_fingerprint:
            raise ValueError(f"Duplicate discovery fingerprint: {discovery.fingerprint}")
        if discovery.discovery_id in self._discoveries:
            raise ValueError(f"Duplicate discovery_id: {discovery.discovery_id}")
        self._discoveries[discovery.discovery_id] = discovery
        self._by_fingerprint[discovery.fingerprint] = discovery.discovery_id
        return discovery

    def try_register(self, discovery: Discovery) -> tuple[Discovery | None, bool]:
        """Register if fingerprint is new; return (discovery, is_new)."""
        if self.has_fingerprint(discovery.fingerprint):
            return self.get_by_fingerprint(discovery.fingerprint), False
        if not discovery.discovery_id:
            discovery.discovery_id = self.next_id()
        return self.register(discovery), True

    def load(self) -> bool:
        if not self._path.is_file():
            return False
        try:
            raw = self._path.read_text(encoding="utf-8")
            payload = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Discovery registry unreadable (%s): %s", self._path, exc)
            return False

        if not isinstance(payload, dict) or payload.get("schema") != SCHEMA_NAME:
            logger.warning("Discovery registry schema mismatch in %s", self._path)
            return False

        self._sequence = int(payload.get("sequence", 0))
        items = payload.get("discoveries", [])
        if not isinstance(items, list):
            return False

        restored: dict[str, Discovery] = {}
        by_fp: dict[str, str] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            discovery = Discovery.from_dict(item)
            if discovery is None:
                continue
            restored[discovery.discovery_id] = discovery
            by_fp[discovery.fingerprint] = discovery.discovery_id

        self._discoveries = restored
        self._by_fingerprint = by_fp
        if self._sequence < len(restored):
            self._sequence = len(restored)
        return True

    def persist(self) -> Path:
        payload = {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "safety_mode": RESEARCH_SAFETY_BANNER,
            "sequence": self._sequence,
            "discovery_count": len(self._discoveries),
            "discoveries": [d.to_dict() for d in self.list_all()],
        }
        self._path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return self._path

    def format_summary(self) -> str:
        if not self._discoveries:
            return "Discovery registry empty."
        lines = ["===== DISCOVERY REGISTRY =====", ""]
        for discovery in self.list_all():
            lines.append(f"  {discovery.summary_line()}")
            lines.append(f"    category: {discovery.category}")
        lines.append("")
        return "\n".join(lines)
