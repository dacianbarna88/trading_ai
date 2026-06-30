#!/usr/bin/env python3
"""TAE Sector Runtime — connects sector intelligence upstream modules."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from research_core.sector_runtime.sector_runner import run_sector_modules

OUTPUT_JSON = "tae_sector_runtime.json"


def main() -> int:
    root = Path(".")
    result = run_sector_modules(root)
    (root / OUTPUT_JSON).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    counts = result.get("step_counts") or {}
    summary = result.get("advisory_summary") or {}
    print("===== TAE SECTOR RUNTIME =====")
    print(f"OK={counts.get('ok')} SKIP={counts.get('skipped')} FAIL={counts.get('fail')}")
    print(f"Top sector: {summary.get('top_sector')} score={summary.get('sector_score')}")
    print(f"Output: {OUTPUT_JSON}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
