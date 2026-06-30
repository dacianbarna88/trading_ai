#!/usr/bin/env python3
"""
TAE Research Runtime — invokes existing research modules (read-only artifacts).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from research_core.research_runtime.research_runner import run_research_modules

OUTPUT_JSON = "tae_research_runtime.json"


def main() -> int:
    root = Path(".")
    result = run_research_modules(root)
    (root / OUTPUT_JSON).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    counts = result.get("step_counts") or {}
    print("===== TAE RESEARCH RUNTIME =====")
    print(f"Modules: {len(result.get('modules_connected') or [])}")
    print(f"OK={counts.get('ok')} SKIP={counts.get('skipped')} FAIL={counts.get('fail')}")
    for step in result.get("module_steps") or []:
        print(f"  {step.get('name')}: {step.get('status')}")
    print(f"Output: {OUTPUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
