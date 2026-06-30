#!/usr/bin/env python3
"""TAE Learning Runtime — LEGACY_RUNTIME_SOURCE; SSOT: tae_unified_runtime.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from research_core.learning_runtime.learning_runner import run_learning_modules

OUTPUT_JSON = "tae_learning_runtime.json"


def main() -> int:
    root = Path(".")
    result = run_learning_modules(root)
    (root / OUTPUT_JSON).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    counts = result.get("step_counts") or {}
    print("===== TAE LEARNING RUNTIME =====")
    print(f"OK={counts.get('ok')} SKIP={counts.get('skipped')} FAIL={counts.get('fail')}")
    summary = result.get("advisory_summary") or {}
    print(f"Learning health score: {summary.get('learning_health_score')}")
    print(f"Output: {OUTPUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
