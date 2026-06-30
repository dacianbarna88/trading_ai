#!/usr/bin/env python3
"""Enrich live_signals.csv with strategic allocation context."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from research_core.strategic_allocation_runtime.live_signals_enricher import enrich_live_signals_file

OUTPUT_JSON = "tae_live_signals_allocation_enrich.json"


def main() -> int:
    root = Path(".")
    result = enrich_live_signals_file(root)
    (root / OUTPUT_JSON).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print("===== TAE LIVE SIGNALS ALLOCATION ENRICH =====")
    if not result.get("ok"):
        print(f"Status: SKIP/FAIL — {result.get('error')}")
        return 0 if "Missing" in str(result.get("error")) else 1

    print(f"Rows enriched: {result.get('enriched')}")
    print(f"STRONG BUY rows: {result.get('strong_buy_count')}")
    print(f"Artifacts: {result.get('artifacts_loaded')}")
    print(f"Output: live_signals.csv, {OUTPUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
