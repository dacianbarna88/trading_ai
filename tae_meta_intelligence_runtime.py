#!/usr/bin/env python3
"""TAE Meta Intelligence Runtime — connects existing meta/ecosystem artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from research_core.meta_intelligence_runtime.meta_runner import run_meta_modules

OUTPUT_JSON = "tae_meta_intelligence_runtime.json"


def main() -> int:
    root = Path(".")
    result = run_meta_modules(root)
    (root / OUTPUT_JSON).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    counts = result.get("step_counts") or {}
    summary = result.get("advisory_summary") or {}
    print("===== TAE META INTELLIGENCE RUNTIME =====")
    print(f"OK={counts.get('ok')} SKIP={counts.get('skipped')} FAIL={counts.get('fail')}")
    print(f"Meta summary: {summary.get('meta_summary')}")
    print(f"Output: {OUTPUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
