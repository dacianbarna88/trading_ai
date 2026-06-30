#!/usr/bin/env python3
"""TAE Event Memory Runtime — LEGACY_RUNTIME_SOURCE; SSOT: tae_unified_runtime.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from research_core.event_memory_runtime.event_memory_runner import run_event_memory_modules

OUTPUT_JSON = "tae_event_memory_runtime.json"


def main() -> int:
    root = Path(".")
    result = run_event_memory_modules(root)
    (root / OUTPUT_JSON).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    counts = result.get("step_counts") or {}
    summary = result.get("advisory_summary") or {}
    print("===== TAE EVENT MEMORY RUNTIME =====")
    print(f"OK={counts.get('ok')} SKIP={counts.get('skipped')} FAIL={counts.get('fail')}")
    print(f"Events: {summary.get('event_count')} verdict={summary.get('verdict')}")
    print(f"Output: {OUTPUT_JSON}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
