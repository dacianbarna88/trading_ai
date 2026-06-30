#!/usr/bin/env python3
"""TAE Ecosystem Runtime — connects full ecosystem, orchestrator, evidence, daily intelligence."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from research_core.ecosystem_runtime.ecosystem_runner import run_ecosystem_modules

OUTPUT_JSON = "tae_ecosystem_runtime.json"


def main() -> int:
    root = Path(".")
    result = run_ecosystem_modules(root)
    (root / OUTPUT_JSON).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    counts = result.get("step_counts") or {}
    summary = result.get("advisory_summary") or {}
    print("===== TAE ECOSYSTEM RUNTIME =====")
    print(f"OK={counts.get('ok')} SKIP={counts.get('skipped')} FAIL={counts.get('fail')}")
    print(f"Ecosystem: {summary.get('ecosystem_run_status')} Evidence: {summary.get('evidence_verdict')}")
    print(f"Output: {OUTPUT_JSON}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
