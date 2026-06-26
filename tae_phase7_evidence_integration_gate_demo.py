"""
TAE Phase VII — Evidence Integration Gate Demo

PAPER_ONLY | NO_BROKER | NO_EXECUTION

Reads evidence engine report and applies integration gate rules.
No strategy changes. No trade execution.
"""

from __future__ import annotations

from pathlib import Path

from integration_layer import (
    EvidenceIntegrationGate,
    IntegrationReportStore,
    SAFETY_BANNER,
)
from integration_layer.integration_report import (
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


def _snapshot_mtimes(paths: list[Path]) -> dict[str, float]:
    out: dict[str, float] = {}
    for path in paths:
        if path.is_file():
            out[str(path)] = path.stat().st_mtime
    return out


def _mtimes_unchanged(before: dict[str, float], after: dict[str, float]) -> bool:
    for key, mtime in before.items():
        if key not in after or after[key] != mtime:
            return False
    return True


def run_evidence_integration_gate_demo() -> None:
    print("===== TAE PHASE VII — EVIDENCE INTEGRATION GATE =====")
    print(SAFETY_BANNER)
    print("Paper-only integration gate — no strategy or portfolio changes.")
    print("No broker. No execution. No BUY/SELL instructions.")
    print()

    before_mtimes = _snapshot_mtimes(PROTECTED_PATHS)

    gate = EvidenceIntegrationGate()
    report = gate.evaluate()

    store = IntegrationReportStore()
    store.persist(report)
    store.persist_txt(report)

    after_mtimes = _snapshot_mtimes(PROTECTED_PATHS)
    protected_ok = _mtimes_unchanged(before_mtimes, after_mtimes)

    print(report.format_text())

    print("===== INTEGRATION GATE SUMMARY =====")
    print(f"Verdict: {report.verdict.value}")
    print(f"Evidence engine: {report.evidence_engine_verdict}")
    print(f"Implementation allowed: {report.allowed_count} item(s)")
    for decision in report.decisions:
        if decision.implementation_allowed:
            print(f"  ✓ {decision.evidence_id} => {decision.gate_status}")
    print()
    print(f"Protected files unchanged: {protected_ok}")
    if protected_ok:
        print(
            "  Confirmed: live_bot.py, dashboard_v2.py, config/settings.py, "
            "portfolio.csv, core/trades.py, core/portfolio_prices.py untouched."
        )
    print(f"JSON saved: {DEFAULT_JSON_PATH}")
    print(f"TXT saved: {DEFAULT_TXT_PATH}")
    print()
    print(report.verdict.value)


def main() -> None:
    run_evidence_integration_gate_demo()


if __name__ == "__main__":
    main()
