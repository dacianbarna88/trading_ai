#!/usr/bin/env python3
"""TAE Unified Runtime SSOT — single record per ticker across all intelligence layers."""

from __future__ import annotations

import sys
from pathlib import Path

from research_core.meta_intelligence_runtime.unified_runtime_builder import (
    OUTPUT_JSON,
    write_unified_runtime,
)


def main() -> int:
    root = Path(".")
    result = write_unified_runtime(root)
    if not result.get("ok"):
        print(f"FAIL: {result.get('error', 'unknown')}")
        return 1

    summary = result.get("advisory_summary") or {}
    score_summary = summary.get("unified_runtime_score_summary") or {}
    print("===== TAE UNIFIED RUNTIME SSOT =====")
    print(f"Records: {summary.get('record_count')}")
    print(f"Unified avg: {score_summary.get('avg')} max: {score_summary.get('max')}")
    print(f"Output: {OUTPUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
