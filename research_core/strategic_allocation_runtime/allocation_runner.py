"""Strategic allocation runtime orchestrator — invokes existing allocation scripts only."""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PYTHON = sys.executable


@dataclass
class AllocationModuleSpec:
    name: str
    script: str
    artifact: str
    skip_if_artifact_present: bool = False
    needs_pythonpath: bool = True
    timeout_seconds: int = 120
    allow_missing_artifact: bool = False


ALLOCATION_MODULES: tuple[AllocationModuleSpec, ...] = (
    AllocationModuleSpec(
        name="adaptive_allocation_summary",
        script="adaptive_allocation_summary.py",
        artifact="adaptive_allocation_summary.txt",
        allow_missing_artifact=True,
    ),
    AllocationModuleSpec(
        name="strategic_allocation_engine",
        script="strategic_intelligence/strategic_allocation_engine.py",
        artifact="strategic_allocation.csv",
        skip_if_artifact_present=True,
    ),
    AllocationModuleSpec(
        name="allocation_gap",
        script="allocation_gap_analyzer.py",
        artifact="allocation_gap_analysis.json",
        allow_missing_artifact=True,
    ),
    AllocationModuleSpec(
        name="allocator_health",
        script="research/allocator_health_monitor.py",
        artifact="allocator_health.csv",
        skip_if_artifact_present=True,
        allow_missing_artifact=True,
    ),
    AllocationModuleSpec(
        name="allocation_drift",
        script="research/allocation_drift_forecast.py",
        artifact="allocation_drift_forecast.csv",
        skip_if_artifact_present=True,
        allow_missing_artifact=True,
    ),
    AllocationModuleSpec(
        name="horizon_allocation",
        script="strategic_intelligence/horizon_vote_engine.py",
        artifact="horizon_vote_summary.txt",
        allow_missing_artifact=True,
    ),
    AllocationModuleSpec(
        name="capital_flow_delta",
        script="strategic_intelligence/capital_flow_delta.py",
        artifact="capital_flow_delta_summary.txt",
        skip_if_artifact_present=True,
        allow_missing_artifact=True,
    ),
    AllocationModuleSpec(
        name="capital_flow_momentum",
        script="strategic_intelligence/capital_flow_momentum.py",
        artifact="capital_flow_momentum_summary.txt",
        skip_if_artifact_present=True,
        allow_missing_artifact=True,
    ),
    AllocationModuleSpec(
        name="capital_flow_summary",
        script="strategic_intelligence/capital_flow_summary_layer.py",
        artifact="capital_flow_summary.txt",
        allow_missing_artifact=True,
    ),
    AllocationModuleSpec(
        name="strategic_intelligence_summary",
        script="strategic_intelligence/strategic_intelligence_summary_layer.py",
        artifact="strategic_intelligence_summary.txt",
        allow_missing_artifact=True,
    ),
    AllocationModuleSpec(
        name="strategic_portfolio_score",
        script="research/strategic_portfolio_score.py",
        artifact="strategic_portfolio_score.csv",
        skip_if_artifact_present=True,
        allow_missing_artifact=True,
    ),
)

SCANNER_ARTIFACTS = (
    "regional_strength.csv",
    "sector_rotation.csv",
    "adaptive_allocation.json",
)


def _run_script(root: Path, spec: AllocationModuleSpec) -> dict[str, Any]:
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

    artifact_ok = artifact_path.is_file()
    if proc.returncode != 0:
        if spec.allow_missing_artifact and not artifact_ok:
            return {
                "name": spec.name,
                "status": "SKIPPED",
                "reason": f"Exit {proc.returncode}; optional",
                "artifact": spec.artifact,
                "runtime_seconds": round(time.monotonic() - started, 3),
            }
        return {
            "name": spec.name,
            "status": "FAIL",
            "returncode": proc.returncode,
            "artifact": spec.artifact,
            "runtime_seconds": round(time.monotonic() - started, 3),
            "stderr_tail": (proc.stderr or "")[-800:],
        }

    if not artifact_ok and not spec.allow_missing_artifact:
        return {
            "name": spec.name,
            "status": "FAIL",
            "reason": "Expected artifact missing",
            "artifact": spec.artifact,
            "runtime_seconds": round(time.monotonic() - started, 3),
        }

    return {
        "name": spec.name,
        "status": "OK",
        "artifact": spec.artifact,
        "artifact_present": artifact_ok,
        "runtime_seconds": round(time.monotonic() - started, 3),
    }


def run_allocation_modules(root: Path | str = ".") -> dict[str, Any]:
    root = Path(root)
    steps = [_run_script(root, spec) for spec in ALLOCATION_MODULES]
    ok = sum(1 for s in steps if s["status"] == "OK")
    skipped = sum(1 for s in steps if s["status"] == "SKIPPED")
    failed = sum(1 for s in steps if s["status"] in ("FAIL", "TIMEOUT"))

    try:
        from research_core.strategic_allocation_runtime.live_signals_enricher import AllocationContext

        advisory_summary = AllocationContext.load(root).advisory_summary()
    except Exception:
        advisory_summary = {}

    return {
        "ok": failed == 0,
        "module_steps": steps,
        "scanner_artifacts": {name: (root / name).is_file() for name in SCANNER_ARTIFACTS},
        "step_counts": {"ok": ok, "skipped": skipped, "fail": failed},
        "modules_connected": [spec.name for spec in ALLOCATION_MODULES],
        "advisory_summary": advisory_summary,
    }
