#!/usr/bin/env python3
"""
TAE Portfolio Reconciliation — read-only SELL integrity report.

Does not modify portfolio.csv or execute trades.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from research_core.accounting.execution_integrity import (
    build_execution_integrity_report,
    build_reconciliation_report,
)

INTEGRITY_JSON = Path("tae_execution_integrity_audit.json")
INTEGRITY_MD = Path("TAE_EXECUTION_INTEGRITY_AUDIT.md")
RECON_JSON = Path("tae_portfolio_reconciliation.json")
RECON_MD = Path("tae_portfolio_reconciliation.md")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def render_integrity_md(report: dict) -> str:
    summary = report["summary"]
    lines = [
        "# TAE Execution Integrity Audit",
        "",
        f"**Generated:** {_utc_now()}  ",
        "**Mode:** ACCOUNTING_INTEGRITY_READ_ONLY  ",
        "**Live trading impact:** NONE",
        "",
        "## Root cause",
        "",
        report.get("root_cause", ""),
        "",
        "## Fix (future rows)",
        "",
        report.get("fix_applied", ""),
        "",
        "## Summary",
        "",
        f"- Total SELL rows: {summary.get('total_sell_rows')}",
        f"- SELL OK: {summary.get('sell_ok')}",
        f"- SELL mismatched: {summary.get('sell_mismatched')}",
        f"- Reported realized PnL: {summary.get('total_reported_realized_pnl')}",
        f"- Corrected realized PnL: {summary.get('corrected_realized_pnl')}",
        f"- Delta: {summary.get('realized_pnl_delta')}",
        f"- Status: **{summary.get('execution_integrity_status')}**",
        f"- Recommended next action: {summary.get('recommended_next_action')}",
        "",
        "## Biggest mismatches",
        "",
    ]
    for item in report.get("biggest_mismatches") or []:
        lines.append(
            f"- **{item.get('ticker')}** ({item.get('sell_date')}): "
            f"reported {item.get('reported_pnl')} vs expected {item.get('expected_realized_pnl')} "
            f"— {item.get('consistency_status')}"
        )
        lines.append(f"  - Reason: {item.get('reason')}")
    lines.extend(["", "## All SELL audits", ""])
    for item in report.get("sell_audits") or []:
        lines.append(
            f"- {item.get('ticker')} | {item.get('consistency_status')} | "
            f"reported {item.get('reported_pnl')} | expected {item.get('expected_realized_pnl')} | "
            f"{item.get('reason')}"
        )
    lines.append("")
    return "\n".join(lines)


def render_reconciliation_md(report: dict) -> str:
    summary = report["summary"]
    lines = [
        "# TAE Portfolio Reconciliation",
        "",
        f"**Generated:** {_utc_now()}  ",
        "**Mode:** READ_ONLY_RECONCILIATION  ",
        "**Live trading impact:** NONE",
        "",
        "## Summary",
        "",
        f"- Total SELL rows: {summary.get('total_sell_rows')}",
        f"- SELL OK: {summary.get('sell_ok')}",
        f"- SELL mismatched: {summary.get('sell_mismatched')}",
        f"- Total reported realized PnL: {summary.get('total_reported_realized_pnl')}",
        f"- Corrected realized PnL: {summary.get('corrected_realized_pnl')}",
        f"- Delta: {summary.get('realized_pnl_delta')}",
        f"- Recommended next action: {summary.get('recommended_next_action')}",
        "",
        "## Root cause",
        "",
        report.get("root_cause", ""),
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    integrity = build_execution_integrity_report()
    integrity["generated_at"] = _utc_now()
    reconciliation = build_reconciliation_report(integrity)
    reconciliation["generated_at"] = _utc_now()

    INTEGRITY_JSON.write_text(json.dumps(integrity, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    INTEGRITY_MD.write_text(render_integrity_md(integrity), encoding="utf-8")
    RECON_JSON.write_text(json.dumps(reconciliation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    RECON_MD.write_text(render_reconciliation_md(reconciliation), encoding="utf-8")

    s = integrity["summary"]
    print(f"SELL rows: {s['total_sell_rows']} | OK: {s['sell_ok']} | mismatched: {s['sell_mismatched']}")
    print(f"Reported realized: {s['total_reported_realized_pnl']} | Corrected: {s['corrected_realized_pnl']}")
    print(f"Status: {s['execution_integrity_status']}")
    print(f"Wrote: {INTEGRITY_JSON}, {RECON_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
