"""
TAE Phase VIII B7 — Ecosystem Inventory & Duplication Audit Demo

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Read-only ecosystem audit — no files deleted or rewritten.
"""

from __future__ import annotations

from pathlib import Path

from research_core.ecosystem_inventory import (
    EcosystemInventoryAudit,
    EcosystemInventoryReportStore,
    SAFETY_BANNER,
)
from research_core.ecosystem_inventory.inventory_report import (
    DEFAULT_JSON_PATH,
    DEFAULT_TXT_PATH,
)

PROTECTED_PATHS = [
    Path("live_bot.py"),
    Path("dashboard_v2.py"),
    Path("config/settings.py"),
    Path("portfolio.csv"),
    Path("core/trades.py"),
    Path("core/portfolio_prices.py"),
]


def run_ecosystem_inventory_audit_demo() -> None:
    print("===== TAE PHASE VIII B7 — ECOSYSTEM INVENTORY & DUPLICATION AUDIT =====")
    print(SAFETY_BANNER)
    print("Read-only ecosystem audit — no files deleted or rewritten.")
    print("No broker. No execution. No BUY/SELL instructions.")
    print()

    audit = EcosystemInventoryAudit()
    report = audit.audit()

    store = EcosystemInventoryReportStore()
    store.persist(report)
    store.persist_txt(report)

    print(report.format_text())

    print("===== AUDIT SUMMARY =====")
    print(f"Verdict: {report.verdict.value}")
    print(f"Modules scanned: {report.total_modules_scanned}")
    print(f"Active: {report.active_modules} | Legacy: {report.legacy_modules}")
    print(f"Duplicate groups: {len(report.duplicate_groups)}")
    print(f"Protected files unchanged: {report.protected_files_unchanged}")
    print(f"JSON saved: {DEFAULT_JSON_PATH}")
    print(f"TXT saved: {DEFAULT_TXT_PATH}")
    print()
    print(report.verdict.value)


def main() -> None:
    run_ecosystem_inventory_audit_demo()


if __name__ == "__main__":
    main()
