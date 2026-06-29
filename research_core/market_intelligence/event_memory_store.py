"""
Event memory store — Phase X Sprint X.6A

ANALYSIS_ONLY | RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE

Empty registry scaffold with JSON persistence and schema validation.
No ingestion, models, or wiring.
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.market_intelligence.event_schema import (
    CURRENT_SCHEMA_VERSION,
    SCHEMA_NAME,
    SCHEMA_VERSION_MANIFEST,
    SOURCE_MODULE_STORE,
    TAE_VERSION,
    build_metadata,
    merge_preserve_unknown,
    utc_now_iso,
    validate_registry,
)

DEFAULT_JSON_PATH = Path("tae_event_memory.json")


class EventMemoryStore:
    """JSON-backed event memory registry — scaffold only."""

    def __init__(self, path: Path | str = DEFAULT_JSON_PATH) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def create_empty_registry(self) -> dict[str, Any]:
        metadata = build_metadata(source_module=SOURCE_MODULE_STORE)
        return {
            "schema": SCHEMA_NAME,
            "schema_version": CURRENT_SCHEMA_VERSION,
            "schema_version_manifest": deepcopy(SCHEMA_VERSION_MANIFEST),
            "safety_mode": (
                "ANALYSIS_ONLY | RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE"
            ),
            "research_only": True,
            "public_data_attestation": True,
            "mnpi_excluded": True,
            "events": [],
            "event_count": 0,
            **metadata,
        }

    def load(self) -> dict[str, Any]:
        if not self._path.is_file():
            raise FileNotFoundError(f"Event memory file not found: {self._path}")
        payload = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Event memory root must be a JSON object")
        return payload

    def save(self, registry: dict[str, Any]) -> None:
        registry["updated_at"] = utc_now_iso()
        self._path.write_text(
            json.dumps(registry, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def validate(self, registry: dict[str, Any]) -> tuple[bool, list[str]]:
        return validate_registry(registry)

    def round_trip(self, registry: dict[str, Any]) -> tuple[bool, list[str]]:
        """Save, reload with unknown-field preservation, and validate."""
        self.save(registry)
        loaded = self.load()
        merged = merge_preserve_unknown(loaded, {})
        return self.validate(merged)

    @staticmethod
    def touch_metadata(registry: dict[str, Any]) -> dict[str, Any]:
        updated = deepcopy(registry)
        updated["updated_at"] = datetime.now(timezone.utc).isoformat()
        updated["source_module"] = SOURCE_MODULE_STORE
        updated["tae_version"] = TAE_VERSION
        return updated
