#!/usr/bin/env python3
"""TAE Confidence Runtime — connects confidence validation modules."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from research_core.confidence_runtime.confidence_runner import run_confidence_modules

OUTPUT_JSON = "tae_confidence_runtime.json"


def main() -> int:
    root = Path(".")
    result = run_confidence_modules(root)
    (root / OUTPUT_JSON).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    counts = result.get("step_counts") or {}
    summary = result.get("advisory_summary") or {}
    print("===== TAE CONFIDENCE RUNTIME =====")
    print(f"OK={counts.get('ok')} SKIP={counts.get('skipped')} FAIL={counts.get('fail')}")
    print(f"Validation: {summary.get('validation_status')} accuracy={summary.get('vote_accuracy_avg')}")
    print(f"Output: {OUTPUT_JSON}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
