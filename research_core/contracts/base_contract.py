"""
Base contract types — Phase IX Sprint IX.2D

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Interface boundary definitions only — no business logic, calculations, or mutations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

SAFETY_BANNER = "ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION"

INTEGRATION_RULE = "Module A → Contract → Module B (no direct subsystem coupling)"


class CompatibilityStatus(str, Enum):
    CONTRACT_COMPLIANT = "CONTRACT_COMPLIANT"
    LEGACY_DIRECT_LINK = "LEGACY_DIRECT_LINK"
    NEEDS_CONTRACT_ADAPTER = "NEEDS_CONTRACT_ADAPTER"
    FORBIDDEN_DIRECT_DEPENDENCY = "FORBIDDEN_DIRECT_DEPENDENCY"
    NO_PAYLOAD = "NO_PAYLOAD"
    PARTIAL_PAYLOAD = "PARTIAL_PAYLOAD"


class DependencyClassification(str, Enum):
    CONTRACT_COMPLIANT = "CONTRACT_COMPLIANT"
    LEGACY_DIRECT_LINK = "LEGACY_DIRECT_LINK"
    NEEDS_CONTRACT_ADAPTER = "NEEDS_CONTRACT_ADAPTER"
    FORBIDDEN_DIRECT_DEPENDENCY = "FORBIDDEN_DIRECT_DEPENDENCY"
    INTERNAL = "INTERNAL"
    UNKNOWN = "UNKNOWN"


@dataclass
class ContractValidationResult:
    contract_id: str
    subsystem_name: str
    report_path: str
    payload_available: bool
    valid: bool
    missing_required: list[str] = field(default_factory=list)
    present_optional: list[str] = field(default_factory=list)
    absent_optional: list[str] = field(default_factory=list)
    compatibility_status: CompatibilityStatus = CompatibilityStatus.NO_PAYLOAD
    messages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "subsystem_name": self.subsystem_name,
            "report_path": self.report_path,
            "payload_available": self.payload_available,
            "valid": self.valid,
            "missing_required": list(self.missing_required),
            "present_optional": list(self.present_optional),
            "absent_optional": list(self.absent_optional),
            "compatibility_status": self.compatibility_status.value,
            "messages": list(self.messages),
        }


@dataclass
class ContractDescription:
    contract_id: str
    version: str
    subsystem_name: str
    canonical_module: str
    required_fields: list[str]
    optional_fields: list[str]
    output_reports: list[str]
    consumed_reports: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "version": self.version,
            "subsystem_name": self.subsystem_name,
            "canonical_module": self.canonical_module,
            "required_fields": list(self.required_fields),
            "optional_fields": list(self.optional_fields),
            "output_reports": list(self.output_reports),
            "consumed_reports": list(self.consumed_reports),
        }


class BaseContract(ABC):
    CONTRACT_ID: str
    VERSION: str
    SUBSYSTEM_NAME: str
    CANONICAL_MODULE: str
    REQUIRED_FIELDS: tuple[str, ...]
    OPTIONAL_FIELDS: tuple[str, ...]
    OUTPUT_REPORTS: tuple[str, ...]
    CONSUMED_REPORTS: tuple[str, ...] = ()

    def describe(self) -> ContractDescription:
        return ContractDescription(
            contract_id=self.CONTRACT_ID,
            version=self.VERSION,
            subsystem_name=self.SUBSYSTEM_NAME,
            canonical_module=self.CANONICAL_MODULE,
            required_fields=list(self.REQUIRED_FIELDS),
            optional_fields=list(self.OPTIONAL_FIELDS),
            output_reports=list(self.OUTPUT_REPORTS),
            consumed_reports=list(self.CONSUMED_REPORTS),
        )

    def validate(self, payload: dict[str, Any] | None) -> ContractValidationResult:
        if payload is None:
            return ContractValidationResult(
                contract_id=self.CONTRACT_ID,
                subsystem_name=self.SUBSYSTEM_NAME,
                report_path=self.OUTPUT_REPORTS[0] if self.OUTPUT_REPORTS else "",
                payload_available=False,
                valid=False,
                compatibility_status=CompatibilityStatus.NO_PAYLOAD,
                messages=["Report payload not available on disk"],
            )

        if not isinstance(payload, dict):
            return ContractValidationResult(
                contract_id=self.CONTRACT_ID,
                subsystem_name=self.SUBSYSTEM_NAME,
                report_path=self.OUTPUT_REPORTS[0] if self.OUTPUT_REPORTS else "",
                payload_available=True,
                valid=False,
                compatibility_status=CompatibilityStatus.PARTIAL_PAYLOAD,
                messages=["Payload is not a JSON object"],
            )

        missing_required = [f for f in self.REQUIRED_FIELDS if f not in payload]
        present_optional = [f for f in self.OPTIONAL_FIELDS if f in payload]
        absent_optional = [f for f in self.OPTIONAL_FIELDS if f not in payload]
        messages: list[str] = []

        schema = payload.get("schema")
        expected_schema = self._expected_schema()
        if expected_schema and schema != expected_schema:
            messages.append(f"Schema mismatch: expected {expected_schema}, got {schema!r}")

        valid = not missing_required and not (
            expected_schema and schema != expected_schema
        )
        if missing_required:
            compatibility = CompatibilityStatus.NEEDS_CONTRACT_ADAPTER
            messages.append(f"Missing required fields: {', '.join(missing_required)}")
        elif messages:
            compatibility = CompatibilityStatus.PARTIAL_PAYLOAD
        else:
            compatibility = CompatibilityStatus.CONTRACT_COMPLIANT

        extra = self._extra_validation(payload)
        messages.extend(extra.messages)
        if not extra.valid:
            valid = False
            if compatibility == CompatibilityStatus.CONTRACT_COMPLIANT:
                compatibility = CompatibilityStatus.NEEDS_CONTRACT_ADAPTER

        return ContractValidationResult(
            contract_id=self.CONTRACT_ID,
            subsystem_name=self.SUBSYSTEM_NAME,
            report_path=self.OUTPUT_REPORTS[0] if self.OUTPUT_REPORTS else "",
            payload_available=True,
            valid=valid,
            missing_required=missing_required,
            present_optional=present_optional,
            absent_optional=absent_optional,
            compatibility_status=compatibility,
            messages=messages,
        )

    def normalize(self, payload: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {
                "contract_id": self.CONTRACT_ID,
                "version": self.VERSION,
                "subsystem_name": self.SUBSYSTEM_NAME,
                "normalized": False,
            }
        keys = set(self.REQUIRED_FIELDS) | set(self.OPTIONAL_FIELDS)
        normalized = {k: payload[k] for k in keys if k in payload}
        normalized["contract_id"] = self.CONTRACT_ID
        normalized["contract_version"] = self.VERSION
        normalized["subsystem_name"] = self.SUBSYSTEM_NAME
        return normalized

    def compatibility_status(self, payload: dict[str, Any] | None) -> CompatibilityStatus:
        return self.validate(payload).compatibility_status

    def _expected_schema(self) -> str | None:
        return None

    def _extra_validation(self, payload: dict[str, Any]) -> ContractValidationResult:
        return ContractValidationResult(
            contract_id=self.CONTRACT_ID,
            subsystem_name=self.SUBSYSTEM_NAME,
            report_path="",
            payload_available=True,
            valid=True,
        )
