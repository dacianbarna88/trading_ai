"""Unified Runtime SSOT reader — canonical consumer surface for tae_unified_runtime.json."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

LEGACY_RUNTIME_SOURCE = "LEGACY_RUNTIME_SOURCE"
UNIFIED_RUNTIME_JSON = "tae_unified_runtime.json"

# (root_global_key, advisory_summary_nested_key)
SSOT_SECTIONS: dict[str, tuple[str, str]] = {
    "strategy": ("strategy_global", "strategy_summary"),
    "counterfactual": ("counterfactual_global", "counterfactual_summary"),
    "ecosystem": ("ecosystem_global", "ecosystem_summary"),
    "macro": ("macro_global", "macro_summary"),
    "sector": ("sector_global", "sector_summary"),
    "confidence": ("confidence_global", "confidence_summary"),
}


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


class UnifiedRuntimeSSOT:
    """Read-only accessor for tae_unified_runtime.json."""

    def __init__(self, payload: dict[str, Any] | None) -> None:
        self._payload = payload or {}

    @classmethod
    def load(cls, root: Path | str = ".") -> UnifiedRuntimeSSOT:
        root = Path(root)
        return cls(_load_json(root / UNIFIED_RUNTIME_JSON))

    @property
    def ok(self) -> bool:
        return bool(self._payload.get("ssot")) and bool(self._payload.get("records_list"))

    @property
    def payload(self) -> dict[str, Any]:
        return self._payload

    @property
    def advisory_summary(self) -> dict[str, Any]:
        summary = self._payload.get("advisory_summary")
        return summary if isinstance(summary, dict) else {}

    @property
    def records_list(self) -> list[dict[str, Any]]:
        rows = self._payload.get("records_list")
        return rows if isinstance(rows, list) else []

    @property
    def records_by_ticker(self) -> dict[str, dict[str, Any]]:
        records = self._payload.get("records") or {}
        if isinstance(records, dict) and records:
            return {str(k).upper(): v for k, v in records.items() if isinstance(v, dict)}
        return {
            str(r.get("Ticker") or "").upper(): r
            for r in self.records_list
            if isinstance(r, dict) and r.get("Ticker")
        }

    @property
    def learning_global(self) -> dict[str, Any]:
        lg = self._payload.get("learning_global")
        return lg if isinstance(lg, dict) else {}

    def section(self, name: str) -> dict[str, Any]:
        if not self.ok:
            return {}
        global_key, advisory_key = SSOT_SECTIONS.get(name, (None, None))
        if global_key:
            block = self._payload.get(global_key)
            if isinstance(block, dict) and block:
                return block
        if advisory_key:
            block = self.advisory_summary.get(advisory_key)
            if isinstance(block, dict) and block:
                return block
        return {}

    def event_memory_summary(self) -> dict[str, Any]:
        cf = self.section("counterfactual")
        if not cf:
            return {}
        return {
            "event_memory_verdict": cf.get("event_memory_verdict"),
            "event_count": cf.get("event_count"),
            "schema_validation_passed": cf.get("schema_validation_passed"),
            "verdict": cf.get("event_memory_verdict"),
        }

    def records_with_signal(self, signal: str) -> list[dict[str, Any]]:
        target = signal.upper()
        return [
            r
            for r in self.records_list
            if str(r.get("Signal") or "").upper() == target
        ]


def load_unified_ssot(root: Path | str = ".") -> UnifiedRuntimeSSOT:
    return UnifiedRuntimeSSOT.load(root)
