#!/usr/bin/env python3
"""
TAE Phase IX Sprint IX.2A — Accounting System Integration Demo

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Integrates accounting modules around the canonical Independent Double Entry kernel.
Produces dependency map and integration validation reports.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from research_core.accounting.accounting_integration_report import AccountingIntegrationAudit
from research_core.accounting.independent_double_entry import (
    CANONICAL_KERNEL_MODULE,
    DEFAULT_JSON_PATH,
)
from research_core.ecosystem_audit.audit_constants import PROTECTED_PATHS
from research_core.strategy_evolution.candidate_report import SAFETY_BANNER

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _protected_mtime_snapshot(root: Path) -> dict[str, float]:
    snapshot: dict[str, float] = {}
    for rel in PROTECTED_PATHS:
        full = root / rel
        if full.is_file():
            snapshot[rel] = full.stat().st_mtime
    return snapshot


def _verify_protected_unchanged(root: Path, before: dict[str, float]) -> None:
    for rel, mtime in before.items():
        full = root / rel
        if not full.is_file():
            raise RuntimeError(f"Protected file missing after audit: {rel}")
        if full.stat().st_mtime != mtime:
            raise RuntimeError(f"Protected file modified during audit: {rel}")


def main() -> int:
    root = Path(".")
    logger.info("TAE Phase IX Sprint IX.2A — Accounting System Integration")
    logger.info("Safety: %s", SAFETY_BANNER)
    logger.info("Canonical kernel: %s", CANONICAL_KERNEL_MODULE)

    before = _protected_mtime_snapshot(root)
    audit = AccountingIntegrationAudit()
    dep_map, report = audit.run()
    paths = audit.persist_all(dep_map, report)
    _verify_protected_unchanged(root, before)

    print()
    print("===== TAE ACCOUNTING SYSTEM INTEGRATION — SPRINT IX.2A =====")
    print()
    print(f"Safety: {SAFETY_BANNER}")
    print(f"Canonical kernel: {CANONICAL_KERNEL_MODULE}")
    print(f"Canonical JSON: {DEFAULT_JSON_PATH} (exists={DEFAULT_JSON_PATH.is_file()})")
    print()
    print(f"Dependency map verdict: {dep_map.verdict}")
    print(f"Integration verdict: {report.verdict}")
    print()
    print(f"Kernel count: {dep_map.kernel_count} (required: 1)")
    print(f"Single kernel verified: {report.single_kernel_verified}")
    print(f"No duplicate PnL kernel: {report.no_duplicate_pnl_kernel_verified}")
    print(f"No duplicate ledger kernel: {report.no_duplicate_ledger_kernel_verified}")
    print(f"Integration targets connected: {sum(1 for t in report.integration_targets if t.status.value != 'DISCONNECTED')}/{len(report.integration_targets)}")
    print()
    print("Integration targets:")
    for target in report.integration_targets:
        print(f"  [{target.status.value}] {target.module_path}")
    print()
    print("Reports written:")
    for key, path in sorted(paths.items()):
        print(f"  {path}")
    print()
    print("Protected files verified unchanged.")
    return 0 if report.verdict == "ACCOUNTING_INTEGRATION_READY" else 1


if __name__ == "__main__":
    sys.exit(main())
