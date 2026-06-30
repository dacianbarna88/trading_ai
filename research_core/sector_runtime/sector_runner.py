"""Sector runtime orchestrator — invokes existing sector_intelligence modules only."""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PYTHON = sys.executable


@dataclass
class SectorModuleSpec:
    name: str
    script: str
    artifact: str
    requires_artifacts: tuple[str, ...] = ()
    skip_if_artifact_present: bool = False
    needs_pythonpath: bool = True
    timeout_seconds: int = 180
    allow_missing_artifact: bool = False


SECTOR_MODULES: tuple[SectorModuleSpec, ...] = (
    SectorModuleSpec(
        name="sector_history",
        script="sector_intelligence/sector_history_engine.py",
        artifact="sector_rotation_history.csv",
        requires_artifacts=("sector_rotation.csv",),
    ),
    SectorModuleSpec(
        name="sector_flow",
        script="sector_intelligence/sector_flow_analyzer.py",
        artifact="sector_flow_summary.txt",
        allow_missing_artifact=True,
    ),
    SectorModuleSpec(
        name="sector_momentum",
        script="sector_intelligence/sector_momentum_analyzer.py",
        artifact="sector_momentum_summary.txt",
        allow_missing_artifact=True,
    ),
    SectorModuleSpec(
        name="sector_rotation_summary",
        script="sector_intelligence/sector_rotation_summary_layer.py",
        artifact="sector_intelligence_summary.txt",
        allow_missing_artifact=True,
    ),
)

READ_ONLY_ARTIFACTS: tuple[str, ...] = (
    "sector_rotation.csv",
    "sector_rotation_history.csv",
    "sector_flow_summary.txt",
    "sector_momentum_summary.txt",
    "sector_intelligence_summary.txt",
    "sector_rotation_summary.txt",
)


def _run_script(root: Path, spec: SectorModuleSpec) -> dict[str, Any]:
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
        "status": "OK" if artifact_ok else "SKIPPED",
        "artifact": spec.artifact,
        "artifact_present": artifact_ok,
        "runtime_seconds": round(time.monotonic() - started, 3),
    }


def run_sector_modules(root: Path | str = ".") -> dict[str, Any]:
    root = Path(root)
    steps = [_run_script(root, spec) for spec in SECTOR_MODULES]
    artifacts_loaded = {name: (root / name).is_file() for name in READ_ONLY_ARTIFACTS}
    ok = sum(1 for s in steps if s["status"] == "OK")
    skipped = sum(1 for s in steps if s["status"] == "SKIPPED")
    failed = sum(1 for s in steps if s["status"] in ("FAIL", "TIMEOUT"))
    try:
        from research_core.sector_runtime.sector_context import SectorContext

        advisory_summary = SectorContext.load(root).advisory_summary()
    except Exception:
        advisory_summary = {}
    return {
        "ok": failed == 0,
        "module_steps": steps,
        "artifacts_loaded": artifacts_loaded,
        "step_counts": {"ok": ok, "skipped": skipped, "fail": failed},
        "modules_connected": [spec.script for spec in SECTOR_MODULES],
        "read_only_artifacts": list(READ_ONLY_ARTIFACTS),
        "advisory_summary": advisory_summary,
    }
