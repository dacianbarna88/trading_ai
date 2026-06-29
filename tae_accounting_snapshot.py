#!/usr/bin/env python3
"""
TAE Accounting Snapshot CLI — canonical read-only financial SSOT.

Does not modify portfolio.csv or execute trades.
"""

from __future__ import annotations

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
