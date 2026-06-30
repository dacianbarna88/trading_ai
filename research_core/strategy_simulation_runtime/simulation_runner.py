"""Strategy simulation runtime orchestrator — invokes existing simulation scripts only."""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PYTHON = sys.executable


@dataclass
class SimulationModuleSpec:
    name: str
    script: str
    artifact: str
    args: tuple[str, ...] = ()
    requires_artifacts: tuple[str, ...] = ()
    skip_if_artifact_present: bool = False
    needs_pythonpath: bool = True
    timeout_seconds: int = 600
    allow_missing_artifact: bool = False


SIMULATION_MODULES: tuple[SimulationModuleSpec, ...] = (
    SimulationModuleSpec(
        name="strategy_simulation_engine",
        script="tae_phase10_strategy_simulation_demo.py",
        artifact="tae_strategy_simulation.json",
        requires_artifacts=("tae_strategy_discovery.json",),
    ),
    SimulationModuleSpec(
        name="historical_research_engine",
        script="tae_phase10_historical_research_demo.py",
        artifact="tae_historical_research.json",
    ),
    SimulationModuleSpec(
        name="historical_execution_batch",
        script="tae_phase10_historical_execution_demo.py",
        artifact="tae_historical_execution.json",
        args=("--batch-size", "5"),
        timeout_seconds=900,
    ),
    SimulationModuleSpec(
        name="historical_results_analysis",
        script="tae_historical_results_analysis_demo.py",
        artifact="tae_historical_results_analysis.json",
        allow_missing_artifact=True,
    ),
)

CONNECTED_MANUAL_MODULES: tuple[str, ...] = (
    "tae_historical_execution_runner.py",
)


def _run_script(root: Path, spec: SimulationModuleSpec) -> dict[str, Any]:
    script_path = root / spec.script
    artifact_path = root / spec.artifact
    started = time.monotonic()

    for req in spec.requires_artifacts:
        if not (root / req).is_file():
            return {
                "name": spec.name,
                "status": "SKIPPED",
                "reason": f"Missing required artifact: {req}",
                "artifact": spec.artifact,
                "runtime_seconds": round(time.monotonic() - started, 3),
            }

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

    cmd = [PYTHON, str(script_path), *spec.args]
    try:
        proc = subprocess.run(
            cmd,
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
    if proc.returncode != 0 and not artifact_ok:
        if spec.allow_missing_artifact:
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

    status = "OK" if artifact_ok or spec.allow_missing_artifact else "SKIPPED"
    return {
        "name": spec.name,
        "status": status,
        "artifact": spec.artifact,
        "artifact_present": artifact_ok,
        "runtime_seconds": round(time.monotonic() - started, 3),
    }


def _advisory_summary(root: Path) -> dict[str, Any]:
    try:
        from research_core.strategy_simulation_runtime.strategy_context import StrategyContext

        return StrategyContext.load(root).advisory_summary()
    except Exception:
        return {}


def run_simulation_modules(root: Path | str = ".") -> dict[str, Any]:
    root = Path(root)
    steps = [_run_script(root, spec) for spec in SIMULATION_MODULES]
    artifacts_loaded = {
        name: (root / name).is_file()
        for name in (
            "tae_strategy_simulation.json",
            "tae_historical_research.json",
            "tae_historical_execution.json",
            "tae_historical_results_analysis.json",
        )
    }
    ok = sum(1 for s in steps if s["status"] == "OK")
    skipped = sum(1 for s in steps if s["status"] == "SKIPPED")
    failed = sum(1 for s in steps if s["status"] in ("FAIL", "TIMEOUT"))
    return {
        "ok": failed == 0,
        "module_steps": steps,
        "artifacts_loaded": artifacts_loaded,
        "step_counts": {"ok": ok, "skipped": skipped, "fail": failed},
        "modules_connected": [spec.name for spec in SIMULATION_MODULES],
        "manual_modules_connected": list(CONNECTED_MANUAL_MODULES),
        "advisory_summary": _advisory_summary(root),
    }
