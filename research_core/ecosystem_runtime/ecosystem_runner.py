"""Ecosystem runtime orchestrator — invokes existing ecosystem modules only."""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PYTHON = sys.executable


@dataclass
class EcosystemModuleSpec:
    name: str
    script: str
    artifact: str
    skip_if_artifact_present: bool = False
    needs_pythonpath: bool = True
    timeout_seconds: int = 900
    allow_missing_artifact: bool = False


ECOSYSTEM_MODULES: tuple[EcosystemModuleSpec, ...] = (
    EcosystemModuleSpec(
        name="full_ecosystem_run",
        script="tae_full_ecosystem_run.py",
        artifact="tae_full_ecosystem_run.json",
        timeout_seconds=900,
    ),
    EcosystemModuleSpec(
        name="legacy_daily_intelligence_runner",
        script="daily_intelligence_runner.py",
        artifact="daily_intelligence_report.txt",
        allow_missing_artifact=True,
        timeout_seconds=120,
    ),
)

MODULES_CONNECTED: tuple[str, ...] = (
    "tae_full_ecosystem_run.py",
    "research_core/full_ecosystem/full_ecosystem_run.py",
    "research_core/orchestrator/ecosystem_orchestrator.py",
    "research_core/evidence_engine/evidence_registry.py",
    "integration_layer/evidence_gate.py",
    "research_core/governance/daily_intelligence.py",
    "daily_intelligence_runner.py",
)

READ_ONLY_ARTIFACTS: tuple[str, ...] = (
    "tae_full_ecosystem_run.json",
    "tae_ecosystem_orchestrator.json",
    "tae_evidence_engine_report.json",
    "tae_evidence_integration_gate.json",
    "tae_daily_intelligence_report.json",
    "daily_intelligence_report.txt",
)


def _run_script(root: Path, spec: EcosystemModuleSpec) -> dict[str, Any]:
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
        "returncode": proc.returncode,
        "runtime_seconds": round(time.monotonic() - started, 3),
    }


def _advisory_summary(root: Path) -> dict[str, Any]:
    try:
        from research_core.ecosystem_runtime.ecosystem_context import EcosystemContext

        return EcosystemContext.load(root).advisory_summary()
    except Exception:
        return {}


def run_ecosystem_modules(root: Path | str = ".") -> dict[str, Any]:
    root = Path(root)
    steps = [_run_script(root, spec) for spec in ECOSYSTEM_MODULES]
    artifacts_loaded = {name: (root / name).is_file() for name in READ_ONLY_ARTIFACTS}
    ok = sum(1 for s in steps if s["status"] == "OK")
    skipped = sum(1 for s in steps if s["status"] == "SKIPPED")
    failed = sum(1 for s in steps if s["status"] in ("FAIL", "TIMEOUT"))
    return {
        "ok": failed == 0,
        "module_steps": steps,
        "artifacts_loaded": artifacts_loaded,
        "step_counts": {"ok": ok, "skipped": skipped, "fail": failed},
        "modules_connected": list(MODULES_CONNECTED),
        "read_only_artifacts": list(READ_ONLY_ARTIFACTS),
        "advisory_summary": _advisory_summary(root),
    }
