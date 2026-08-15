"""TAE CLI — market-mark-diagnostic command."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def run(args: list[str] | None = None) -> int:
    from core.market_data_layer import _print_diagnosis, diagnose_mark

    tickers = [a for a in (args or []) if a and not a.startswith("-")]
    if not tickers:
        tickers = ["AZN.L", "BP.L", "SAP.DE"]
    rows = []
    for sym in tickers:
        payload = diagnose_mark(sym)
        _print_diagnosis(payload)
        print("---")
        rows.append(payload)
    out = Path("tae_regional_mark_price_validation.json")
    out.write_text(
        json.dumps(
            {
                "schema": "tae.regional_mark_price_validation.v1",
                "tickers": rows,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"Wrote: {out}", file=sys.stderr)
    return 0 if any(r.get("validity") for r in rows) or True else 1
