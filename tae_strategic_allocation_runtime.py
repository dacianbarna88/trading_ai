#!/usr/bin/env python3
"""TAE Strategic Allocation Runtime — invokes existing allocation modules."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from research_core.strategic_allocation_runtime.allocation_runner import run_allocation_modules

OUTPUT_JSON = "tae_strategic_allocation_runtime.json"


def main() -> int:
    root = Path(".")
    result = run_allocation_modules(root)
    (root / OUTPUT_JSON).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    counts = result.get("step_counts") or {}
    print("===== TAE STRATEGIC ALLOCATION RUNTIME =====")
    print(f"OK={counts.get('ok')} SKIP={counts.get('skipped')} FAIL={counts.get('fail')}")
    summary = result.get("advisory_summary") or {}
    print(f"Portfolio score: {summary.get('portfolio_score')}")
    print(f"Output: {OUTPUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
