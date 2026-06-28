"""
Base adapter types — Phase IX Sprint IX.3

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Read-only translation between canonical JSON and contract payloads.
No calculations, mutations, broker calls, or trading logic.
"""

from __future__ import annotations

import json
from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from research_core.contracts.base_contract import (
    BaseContract,
    CompatibilityStatus,
    SAFETY_BANNER,
)

__all__ = [
    "ADAPTER_RULE",
    "AdapterDescription",
    "AdapterLoadResult",
    "AdapterStatus",
    "BaseAdapter",
    "SAFETY_BANNER",
    "read_json_report",
]

ADAPTER_RULE = (
    "Module A → Contract → Adapter → Canonical JSON → Adapter → Contract → Module B"
)


class AdapterStatus(str, Enum):
    ADAPTER_COMPLIANT = "ADAPTER_COMPLIANT"
    NEEDS_ADAPTER_MIGRATION = "NEEDS_ADAPTER_MIGRATION"
    LEGACY_DIRECT_LINK = "LEGACY_DIRECT_LINK"
    FORBIDDEN_DIRECT_DEPENDENCY = "FORBIDDEN_DIRECT_DEPENDENCY"
    MISSING_CANONICAL_REPORT = "MISSING_CANONICAL_REPORT"
    CONTRACT_VALIDATION_FAILED = "CONTRACT_VALIDATION_FAILED"


@dataclass
class AdapterDescription:
    adapter_id: str
    version: str
    contract_id: str
    subsystem_name: str
    canonical_module: str
    canonical_reports: list[str]
    optional_reports: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "version": self.version,
            "contract_id": self.contract_id,
            "subsystem_name": self.subsystem_name,
            "canonical_module": self.canonical_module,
            "canonical_reports": list(self.canonical_reports),
            "optional_reports": list(self.optional_reports),
        }


@dataclass
class AdapterLoadResult:
    adapter_id: str
    primary_report: str
    sources: dict[str, dict[str, Any] | None]
    missing_reports: list[str]
    loaded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "primary_report": self.primary_report,
            "sources_loaded": {k: v is not None for k, v in self.sources.items()},
            "missing_reports": list(self.missing_reports),
            "loaded_at": self.loaded_at.isoformat(),
        }


def read_json_report(path: Path | str, root: Path | None = None) -> dict[str, Any] | None:
    """Read-only JSON load — never mutates source files."""
    report_path = Path(path)
    if root is not None and not report_path.is_absolute():
        report_path = root / report_path
    if not report_path.is_file():
        return None
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


class BaseAdapter(ABC):
    ADAPTER_ID: str
    VERSION: str
    CONTRACT_ID: str
    SUBSYSTEM_NAME: str
    CANONICAL_MODULE: str
    PRIMARY_REPORT: str
    CANONICAL_REPORTS: tuple[str, ...]
    OPTIONAL_REPORTS: tuple[str, ...] = ()

    def __init__(self, root: Path | str = Path(".")) -> None:
        self._root = Path(root)
        self._contract_instance: BaseContract | None = None

    def contract(self) -> BaseContract:
        if self._contract_instance is None:
            self._contract_instance = self._build_contract()
        return self._contract_instance

    def describe(self) -> AdapterDescription:
        return AdapterDescription(
            adapter_id=self.ADAPTER_ID,
            version=self.VERSION,
            contract_id=self.CONTRACT_ID,
            subsystem_name=self.SUBSYSTEM_NAME,
            canonical_module=self.CANONICAL_MODULE,
            canonical_reports=list(self.CANONICAL_REPORTS),
            optional_reports=list(self.OPTIONAL_REPORTS),
        )

    def load_source(self) -> AdapterLoadResult:
        sources: dict[str, dict[str, Any] | None] = {}
        missing: list[str] = []
        for name in self.CANONICAL_REPORTS:
            payload = read_json_report(name, self._root)
            sources[name] = payload
            if payload is None and name == self.PRIMARY_REPORT:
                missing.append(name)
        for name in self.OPTIONAL_REPORTS:
            sources[name] = read_json_report(name, self._root)
        return AdapterLoadResult(
            adapter_id=self.ADAPTER_ID,
            primary_report=self.PRIMARY_REPORT,
            sources=sources,
            missing_reports=missing,
        )

    def to_contract_payload(self) -> dict[str, Any]:
        loaded = self.load_source()
        primary = loaded.sources.get(self.PRIMARY_REPORT)
        if primary is None:
            return {
                "adapter_id": self.ADAPTER_ID,
                "contract_id": self.CONTRACT_ID,
                "normalized": False,
                "reason": "MISSING_CANONICAL_REPORT",
            }
        normalized = self.contract().normalize(primary)
        normalized["adapter_id"] = self.ADAPTER_ID
        normalized["adapter_version"] = self.VERSION
        return normalized

    def validate_contract_payload(self) -> dict[str, Any]:
        loaded = self.load_source()
        primary = loaded.sources.get(self.PRIMARY_REPORT)
        result = self.contract().validate(primary)
        out = result.to_dict()
        out["adapter_id"] = self.ADAPTER_ID
        return out

    def adapter_status(self) -> AdapterStatus:
        loaded = self.load_source()
        if loaded.missing_reports:
            return AdapterStatus.MISSING_CANONICAL_REPORT
        validation = self.validate_contract_payload()
        if not validation.get("valid"):
            return AdapterStatus.CONTRACT_VALIDATION_FAILED
        if validation.get("compatibility_status") == CompatibilityStatus.CONTRACT_COMPLIANT.value:
            return AdapterStatus.ADAPTER_COMPLIANT
        return AdapterStatus.CONTRACT_VALIDATION_FAILED

    def snapshot(self) -> dict[str, Any]:
        return {
            "description": self.describe().to_dict(),
            "load": self.load_source().to_dict(),
            "validation": self.validate_contract_payload(),
            "contract_payload": self.to_contract_payload(),
            "adapter_status": self.adapter_status().value,
            "safety_mode": SAFETY_BANNER,
        }

    def _build_contract(self) -> BaseContract:
        raise NotImplementedError
