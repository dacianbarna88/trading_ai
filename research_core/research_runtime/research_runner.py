"""
Research runtime orchestrator — invokes existing research scripts only (no rewrites).
"""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PYTHON = sys.executable


@dataclass
class ResearchModuleSpec:
    name: str
    script: str
    artifact: str
    skip_if_artifact_present: bool = False
    needs_pythonpath: bool = True
    timeout_seconds: int = 300


RESEARCH_MODULES: tuple[ResearchModuleSpec, ...] = (
    ResearchModuleSpec(
        name="momentum_continuation",
        script="momentum_continuation_engine.py",
        artifact="momentum_continuation_signals.csv",
        skip_if_artifact_present=True,
        timeout_seconds=600,
    ),
    ResearchModuleSpec(
        name="daily_gainers",
        script="daily_gainers_strategy_research.py",
        artifact="daily_gainers_strategy_results.csv",
        skip_if_artifact_present=True,
        timeout_seconds=900,
    ),
    ResearchModuleSpec(
        name="daily_gainers_momentum_filter",
        script="daily_gainers_momentum_filter_research.py",
        artifact="daily_gainers_momentum_filter_results.csv",
        skip_if_artifact_present=True,
        timeout_seconds=900,
    ),
    ResearchModuleSpec(
        name="threshold_intelligence",
        script="intelligence/threshold_intelligence_layer.py",
        artifact="threshold_intelligence_summary.txt",
        skip_if_artifact_present=False,
        timeout_seconds=60,
    ),
    ResearchModuleSpec(
        name="macro_committee",
        script="macro_intelligence/macro_committee_engine.py",
        artifact="macro_committee_summary.txt",
        skip_if_artifact_present=False,
        timeout_seconds=60,
    ),
    ResearchModuleSpec(
        name="adaptive_allocation",
        script="generate_adaptive_allocation.py",
        artifact="adaptive_allocation.json",
        skip_if_artifact_present=False,
        timeout_seconds=60,
    ),
    ResearchModuleSpec(
        name="regional_validation",
        script="tae_phase6_regional_validation_kn_d5_00002_demo.py",
        artifact="tae_regional_validation_kn_d5_00002.json",
        skip_if_artifact_present=True,
        timeout_seconds=120,
    ),
    ResearchModuleSpec(
        name="entry_counterfactual",
        script="tae_phase7_entry_counterfactual_demo.py",
        artifact="tae_entry_counterfactual.json",
        skip_if_artifact_present=False,
        timeout_seconds=120,
    ),
    ResearchModuleSpec(
        name="exit_counterfactual",
        script="tae_phase7_exit_counterfactual_demo.py",
        artifact="tae_exit_counterfactual.json",
        skip_if_artifact_present=False,
        timeout_seconds=120,
    ),
)

SCANNER_ARTIFACTS = (
    "sector_rotation.csv",
    "regional_strength.csv",
    "global_market_scanner.csv",
)


def _run_script(root: Path, spec: ResearchModuleSpec) -> dict[str, Any]:
    script_path = root / spec.script
    artifact_path = root / spec.artifact
    started = time.monotonic()

    if spec.skip_if_artifact_present and artifact_path.is_file():
        return {
            "name": spec.name,
            "status": "SKIPPED",
            "reason": f"Artifact present: {spec.artifact}",
            "artifact": spec.artifact,
            "runtime_seconds": round(time.monotonic() - started, 3),
        }

    if not script_path.is_file():
        return {
            "name": spec.name,
            "status": "SKIPPED",
            "reason": f"Missing script: {spec.script}",
            "artifact": spec.artifact,
            "runtime_seconds": round(time.monotonic() - started, 3),
        }

    env = None
    if spec.needs_pythonpath:
        import os

        env = os.environ.copy()
        env["PYTHONPATH"] = str(root) + (f":{env['PYTHONPATH']}" if env.get("PYTHONPATH") else "")

    try:
        proc = subprocess.run(
            [PYTHON, str(script_path)],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=spec.timeout_seconds,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "name": spec.name,
            "status": "TIMEOUT",
            "reason": f"Exceeded {spec.timeout_seconds}s",
            "artifact": spec.artifact,
            "runtime_seconds": round(time.monotonic() - started, 3),
        }
    except OSError as exc:
        return {
            "name": spec.name,
            "status": "FAIL",
            "reason": str(exc),
            "artifact": spec.artifact,
            "runtime_seconds": round(time.monotonic() - started, 3),
        }

    ok = proc.returncode == 0 and artifact_path.is_file()
    return {
        "name": spec.name,
        "status": "OK" if ok else "FAIL",
        "returncode": proc.returncode,
        "artifact": spec.artifact,
        "artifact_present": artifact_path.is_file(),
        "runtime_seconds": round(time.monotonic() - started, 3),
        "stderr_tail": (proc.stderr or "")[-800:],
    }


def run_research_modules(root: Path | str = ".") -> dict[str, Any]:
    root = Path(root)
    steps = [_run_script(root, spec) for spec in RESEARCH_MODULES]

    scanner_loaded = {
        name: (root / name).is_file() for name in SCANNER_ARTIFACTS
    }

    ok = sum(1 for s in steps if s["status"] == "OK")
    skipped = sum(1 for s in steps if s["status"] == "SKIPPED")
    failed = sum(1 for s in steps if s["status"] in ("FAIL", "TIMEOUT"))

    return {
        "ok": failed == 0,
        "module_steps": steps,
        "scanner_artifacts": scanner_loaded,
        "step_counts": {"ok": ok, "skipped": skipped, "fail": failed},
        "modules_connected": [spec.name for spec in RESEARCH_MODULES],
    }
