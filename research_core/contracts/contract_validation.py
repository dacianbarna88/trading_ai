"""Contract validation against canonical JSON outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from research_core.contracts.base_contract import BaseContract, CompatibilityStatus
from research_core.contracts.contract_registry import all_contracts


def load_report_json(path: str | Path) -> dict[str, Any] | None:
    report_path = Path(path)
    if not report_path.is_file():
        return None
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def validate_all_contracts(root: Path | str = Path(".")) -> list[dict[str, Any]]:
    root = Path(root)
    results: list[dict[str, Any]] = []
    for contract in all_contracts():
        report_name = contract.OUTPUT_REPORTS[0] if contract.OUTPUT_REPORTS else ""
        payload = load_report_json(root / report_name) if report_name else None
        result = contract.validate(payload)
        results.append(result.to_dict())
    return results


def validation_matrix(root: Path | str = Path(".")) -> dict[str, Any]:
    results = validate_all_contracts(root)
    compliant = sum(
        1
        for r in results
        if r["compatibility_status"] == CompatibilityStatus.CONTRACT_COMPLIANT.value
    )
    return {
        "total_contracts": len(results),
        "compliant_count": compliant,
        "results": results,
    }
