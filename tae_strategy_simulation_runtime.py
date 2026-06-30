#!/usr/bin/env python3
"""TAE Strategy Simulation Runtime — connects existing simulation modules."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from research_core.strategy_simulation_runtime.simulation_runner import run_simulation_modules

OUTPUT_JSON = "tae_strategy_simulation_runtime.json"


def main() -> int:
    root = Path(".")
    result = run_simulation_modules(root)
    (root / OUTPUT_JSON).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    counts = result.get("step_counts") or {}
    summary = result.get("advisory_summary") or {}
    print("===== TAE STRATEGY SIMULATION RUNTIME =====")
    print(f"OK={counts.get('ok')} SKIP={counts.get('skipped')} FAIL={counts.get('fail')}")
    print(f"Top simulated: {len(summary.get('top_simulated_strategies') or [])}")
    print(f"Output: {OUTPUT_JSON}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
