#!/usr/bin/env python3
"""Write TAE capital base integrity audit artifacts (read-only)."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from research_core.accounting.accounting_snapshot import build_accounting_snapshot, persist_accounting_snapshot
from research_core.accounting.capital_base_integrity import (
    build_capital_base_integrity_audit,
    render_capital_base_audit_md,
)

OUT_JSON = Path("tae_capital_base_integrity_audit.json")
OUT_MD = Path("TAE_CAPITAL_BASE_INTEGRITY_AUDIT.md")


def main() -> int:
    root = Path(".")
    snapshot = build_accounting_snapshot(root)
    persist_accounting_snapshot(snapshot, root)
    audit = build_capital_base_integrity_audit(root, snapshot=snapshot)
    audit["generated_at"] = datetime.now(timezone.utc).isoformat()

    OUT_JSON.write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_capital_base_audit_md(audit), encoding="utf-8")

    print("===== TAE CAPITAL BASE INTEGRITY AUDIT =====")
    print(f"Status: {audit.get('capital_base_status')}")
    print(f"Starting capital config: {audit.get('starting_capital_config')}")
    print(f"Deposits detected / counted / excluded: "
          f"{audit.get('capital_deposits_detected')} / "
          f"{audit.get('capital_deposits_counted')} / "
          f"{audit.get('capital_deposits_excluded')}")
    print(f"Effective contributed capital: {audit.get('effective_contributed_capital')}")
    print(f"Cash: {audit.get('cash_available')} (live_bot style: {audit.get('cash_live_bot_style')})")
    print(f"Account value: {audit.get('account_value_cash_based')}")
    print(f"Trading PnL: {audit.get('corrected_total_trading_pnl')}")
    print(f"Wrote: {OUT_JSON}, {OUT_MD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
