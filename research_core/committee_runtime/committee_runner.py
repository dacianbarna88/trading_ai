"""
Committee runtime orchestrator — invokes existing committee scripts only.
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
class CommitteeModuleSpec:
    name: str
    script: str
    artifact: str
    skip_if_artifact_present: bool = False
    needs_pythonpath: bool = True
    timeout_seconds: int = 120
    allow_missing_artifact: bool = False


COMMITTEE_MODULES: tuple[CommitteeModuleSpec, ...] = (
    CommitteeModuleSpec(
        name="strategic_committee_votes",
        script="strategic_intelligence/strategic_committee_engine.py",
        artifact="strategic_committee_summary.txt",
    ),
    CommitteeModuleSpec(
        name="adaptive_committee",
        script="strategic_committee.py",
        artifact="strategic_committee_summary.txt",
    ),
    CommitteeModuleSpec(
        name="committee_confidence_engine",
        script="committee_confidence_engine.py",
        artifact="committee_confidence_breakdown.txt",
        allow_missing_artifact=True,
    ),
    CommitteeModuleSpec(
        name="vote_accuracy_tracker",
        script="confidence_intelligence/vote_accuracy_engine.py",
        artifact="vote_accuracy.csv",
        skip_if_artifact_present=False,
    ),
    CommitteeModuleSpec(
        name="adaptive_weights",
        script="adaptive_weight_engine.py",
        artifact="adaptive_weights.csv",
        skip_if_artifact_present=True,
        allow_missing_artifact=True,
    ),
    CommitteeModuleSpec(
        name="weighted_committee",
        script="confidence_intelligence/weighted_committee_engine.py",
        artifact="weighted_committee_summary.txt",
        allow_missing_artifact=True,
    ),
    CommitteeModuleSpec(
        name="weighted_decision_engine",
        script="weighted_committee_decision.py",
        artifact="weighted_committee_decision.txt",
    ),
    CommitteeModuleSpec(
        name="committee_learning",
        script="committee_learning_engine.py",
        artifact="committee_learning_summary.txt",
        skip_if_artifact_present=True,
        allow_missing_artifact=True,
    ),
    CommitteeModuleSpec(
        name="committee_learning_analytics",
        script="committee_learning_analytics.py",
        artifact="committee_learning_analytics.txt",
        skip_if_artifact_present=True,
        allow_missing_artifact=True,
    ),
    CommitteeModuleSpec(
        name="committee_evolution",
        script="confidence_intelligence/confidence_evolution_summary.py",
        artifact="confidence_evolution_summary.txt",
        allow_missing_artifact=True,
    ),
    CommitteeModuleSpec(
        name="daily_committee_snapshot",
        script="daily_committee_snapshot.py",
        artifact="latest_committee_snapshot.txt",
        allow_missing_artifact=True,
    ),
)


def _run_script(root: Path, spec: CommitteeModuleSpec) -> dict[str, Any]:
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

    artifact_ok = artifact_path.is_file()
    if proc.returncode != 0:
        if spec.allow_missing_artifact and not artifact_ok:
            return {
                "name": spec.name,
                "status": "SKIPPED",
                "reason": f"Exit {proc.returncode}; artifact optional",
                "artifact": spec.artifact,
                "runtime_seconds": round(time.monotonic() - started, 3),
                "stderr_tail": (proc.stderr or "")[-500:],
            }
        return {
            "name": spec.name,
            "status": "FAIL",
            "returncode": proc.returncode,
            "artifact": spec.artifact,
            "artifact_present": artifact_ok,
            "runtime_seconds": round(time.monotonic() - started, 3),
            "stderr_tail": (proc.stderr or "")[-800:],
        }

    if not artifact_ok and not spec.allow_missing_artifact:
        return {
            "name": spec.name,
            "status": "FAIL",
            "reason": "Command succeeded but expected artifact missing",
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


def run_committee_modules(root: Path | str = ".") -> dict[str, Any]:
    root = Path(root)
    steps = [_run_script(root, spec) for spec in COMMITTEE_MODULES]

    ok = sum(1 for s in steps if s["status"] == "OK")
    skipped = sum(1 for s in steps if s["status"] == "SKIPPED")
    failed = sum(1 for s in steps if s["status"] in ("FAIL", "TIMEOUT"))

    try:
        from research_core.committee_runtime.live_signals_enricher import CommitteeContext

        advisory_summary = CommitteeContext.load(root).advisory_summary()
    except Exception:
        advisory_summary = {}

    return {
        "ok": failed == 0,
        "module_steps": steps,
        "step_counts": {"ok": ok, "skipped": skipped, "fail": failed},
        "modules_connected": [spec.name for spec in COMMITTEE_MODULES],
        "advisory_summary": advisory_summary,
    }
