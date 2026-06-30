#!/usr/bin/env python3
"""
TAE Committee Runtime — LEGACY_RUNTIME_SOURCE pipeline step artifact.
Consumers must read tae_unified_runtime.json (SSOT).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from research_core.committee_runtime.committee_runner import run_committee_modules

OUTPUT_JSON = "tae_committee_runtime.json"


def main() -> int:
    root = Path(".")
    result = run_committee_modules(root)
    (root / OUTPUT_JSON).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    counts = result.get("step_counts") or {}
    print("===== TAE COMMITTEE RUNTIME =====")
    print(f"Modules: {len(result.get('modules_connected') or [])}")
    print(f"OK={counts.get('ok')} SKIP={counts.get('skipped')} FAIL={counts.get('fail')}")
    for step in result.get("module_steps") or []:
        print(f"  {step.get('name')}: {step.get('status')}")
    summary = result.get("advisory_summary") or {}
    print(f"Committee decision: {(summary.get('weighted_decisions') or {}).get('final_decision')}")
    print(f"Output: {OUTPUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
