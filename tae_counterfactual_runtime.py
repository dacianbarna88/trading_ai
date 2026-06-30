#!/usr/bin/env python3
"""TAE Counterfactual Runtime — connects entry/exit analysis and shadow validation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from research_core.counterfactual_runtime.counterfactual_runner import run_counterfactual_modules

OUTPUT_JSON = "tae_counterfactual_runtime.json"


def main() -> int:
    root = Path(".")
    result = run_counterfactual_modules(root)
    (root / OUTPUT_JSON).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    counts = result.get("step_counts") or {}
    summary = result.get("advisory_summary") or {}
    print("===== TAE COUNTERFACTUAL RUNTIME =====")
    print(f"OK={counts.get('ok')} SKIP={counts.get('skipped')} FAIL={counts.get('fail')}")
    print(f"Entry: {summary.get('entry_verdict')} Exit: {summary.get('exit_verdict')}")
    print(f"Output: {OUTPUT_JSON}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
