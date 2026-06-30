#!/usr/bin/env python3
"""TAE Macro Runtime — connects macro intelligence upstream modules."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from research_core.macro_runtime.macro_runner import run_macro_modules

OUTPUT_JSON = "tae_macro_runtime.json"


def main() -> int:
    root = Path(".")
    result = run_macro_modules(root)
    (root / OUTPUT_JSON).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    counts = result.get("step_counts") or {}
    summary = result.get("advisory_summary") or {}
    print("===== TAE MACRO RUNTIME =====")
    print(f"OK={counts.get('ok')} SKIP={counts.get('skipped')} FAIL={counts.get('fail')}")
    print(f"Macro: {summary.get('macro_verdict')} Regime: {summary.get('macro_regime')}")
    print(f"Output: {OUTPUT_JSON}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
