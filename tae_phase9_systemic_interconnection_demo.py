"""
TAE Phase IX C1 — Systemic Module Interconnection Demo

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Read-only interconnection map — no module rewrites or competing runners.
"""

from __future__ import annotations

from pathlib import Path

from research_core.systemic_integration import (
    SAFETY_BANNER,
    SystemicInterconnectionReportStore,
    SystemicModuleInterconnection,
)
from research_core.systemic_integration.interconnection_report import (
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


def run_systemic_interconnection_demo() -> None:
    print("===== TAE PHASE IX C1 — SYSTEMIC MODULE INTERCONNECTION =====")
    print(SAFETY_BANNER)
    print("Read-only interconnection map — no module rewrites.")
    print("No broker. No execution. No BUY/SELL instructions.")
    print()

    interconnection = SystemicModuleInterconnection()
    report = interconnection.build()

    store = SystemicInterconnectionReportStore()
    store.persist(report)
    store.persist_txt(report)

    print(report.format_text())

    print("===== INTERCONNECTION SUMMARY =====")
    print(f"Verdict: {report.verdict.value}")
    print(f"Canonical modules: {len(report.canonical_module_map)}")
    print(f"Classifications: {len(report.module_classifications)}")
    print(f"Duplicate groups: {len(report.duplicate_groups)}")
    print(f"Conflict warnings: {len(report.conflict_warnings)}")
    print(f"Missing connections: {len(report.missing_connections)}")
    print(f"Protected files unchanged: {report.protected_files_unchanged}")
    print(f"JSON saved: {DEFAULT_JSON_PATH}")
    print(f"TXT saved: {DEFAULT_TXT_PATH}")
    print()
    print(report.verdict.value)


def main() -> None:
    run_systemic_interconnection_demo()


if __name__ == "__main__":
    main()
