"""Counterfactual runtime orchestrator — invokes existing analysis modules only."""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PYTHON = sys.executable


@dataclass
class CounterfactualModuleSpec:
    name: str
    script: str
    artifact: str
    args: tuple[str, ...] = ()
    skip_if_artifact_present: bool = False
    needs_pythonpath: bool = True
    timeout_seconds: int = 300
    allow_missing_artifact: bool = False


COUNTERFACTUAL_MODULES: tuple[CounterfactualModuleSpec, ...] = (
    CounterfactualModuleSpec(
        name="entry_counterfactual",
        script="tae_phase7_entry_counterfactual_demo.py",
        artifact="tae_entry_counterfactual.json",
    ),
    CounterfactualModuleSpec(
        name="exit_counterfactual",
        script="tae_phase7_exit_counterfactual_demo.py",
        artifact="tae_exit_counterfactual.json",
    ),
    CounterfactualModuleSpec(
        name="shadow_validation_report",
        script="tae_shadow_validation_report.py",
        artifact="tae_shadow_validation_summary.json",
        allow_missing_artifact=True,
    ),
)


def _run_script(root: Path, spec: CounterfactualModuleSpec) -> dict[str, Any]:
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

    return {
        "name": spec.name,
        "status": "OK" if artifact_ok or spec.allow_missing_artifact else "SKIPPED",
        "artifact": spec.artifact,
        "artifact_present": artifact_ok,
        "runtime_seconds": round(time.monotonic() - started, 3),
    }


def run_counterfactual_modules(root: Path | str = ".") -> dict[str, Any]:
    root = Path(root)
    steps = [_run_script(root, spec) for spec in COUNTERFACTUAL_MODULES]
    artifacts_loaded = {
        name: (root / name).is_file()
        for name in (
            "tae_entry_counterfactual.json",
            "tae_exit_counterfactual.json",
            "tae_shadow_validation_summary.json",
            "tae_shadow_validation_events.csv",
        )
    }
    ok = sum(1 for s in steps if s["status"] == "OK")
    skipped = sum(1 for s in steps if s["status"] == "SKIPPED")
    failed = sum(1 for s in steps if s["status"] in ("FAIL", "TIMEOUT"))
    try:
        from research_core.counterfactual_runtime.counterfactual_context import CounterfactualContext

        advisory_summary = CounterfactualContext.load(root).advisory_summary()
    except Exception:
        advisory_summary = {}
    return {
        "ok": failed == 0,
        "module_steps": steps,
        "artifacts_loaded": artifacts_loaded,
        "step_counts": {"ok": ok, "skipped": skipped, "fail": failed},
        "modules_connected": [spec.name for spec in COUNTERFACTUAL_MODULES],
        "advisory_summary": advisory_summary,
    }
