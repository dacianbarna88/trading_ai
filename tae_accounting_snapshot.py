#!/usr/bin/env python3
"""
TAE Accounting Snapshot CLI — canonical read-only financial SSOT.

Does not modify portfolio.csv or execute trades.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from research_core.accounting.accounting_snapshot import (
    build_accounting_snapshot,
    persist_accounting_snapshot,
)


def main() -> int:
    root = Path(".")
    snapshot = build_accounting_snapshot(root)
    json_path, md_path = persist_accounting_snapshot(snapshot, root)

    from research_core.accounting.capital_base_integrity import (
        build_capital_base_integrity_audit,
        render_capital_base_audit_md,
    )

    audit = build_capital_base_integrity_audit(root, snapshot=snapshot)
    Path("tae_capital_base_integrity_audit.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    Path("TAE_CAPITAL_BASE_INTEGRITY_AUDIT.md").write_text(
        render_capital_base_audit_md(audit),
        encoding="utf-8",
    )

    print("===== TAE ACCOUNTING SNAPSHOT =====")
    print(f"Data quality: {snapshot.get('data_quality_status')}")
    print(f"Corrected total trading PnL: {snapshot.get('corrected_total_trading_pnl')}")
    print(f"Corrected realized: {snapshot.get('corrected_realized_pnl')}")
    print(f"Corrected unrealized: {snapshot.get('corrected_unrealized_pnl')}")
    print(f"Account value (corrected): {snapshot.get('account_value_corrected')}")
    print(f"Cash: {snapshot.get('cash_available')} | Deposits: {snapshot.get('capital_deposits')}")
    print(f"SELL mismatches: {snapshot.get('sell_mismatch_count')}")
    drag = snapshot.get("top_drag_corrected")
    if drag:
        print(f"Top drag (corrected): {drag.get('ticker')} {drag.get('pnl')}")
    print(f"Wrote: {json_path}, {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
