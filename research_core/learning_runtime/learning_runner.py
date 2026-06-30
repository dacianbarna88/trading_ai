"""Learning runtime orchestrator — invokes existing learning scripts only."""

from __future__ import annotations

import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PYTHON = sys.executable


@dataclass
class LearningModuleSpec:
    name: str
    script: str
    artifact: str
    skip_if_artifact_present: bool = False
    needs_pythonpath: bool = True
    timeout_seconds: int = 120
    allow_missing_artifact: bool = False


LEARNING_MODULES: tuple[LearningModuleSpec, ...] = (
    LearningModuleSpec(
        name="learning_health",
        script="learning_health_engine.py",
        artifact="learning_health_summary.txt",
    ),
    LearningModuleSpec(
        name="learning_recommendations",
        script="learning_recommendations_engine.py",
        artifact="learning_recommendations_engine_summary.txt",
        allow_missing_artifact=True,
    ),
    LearningModuleSpec(
        name="feedback_update",
        script="feedback_update_engine.py",
        artifact="feedback_update_summary.txt",
        skip_if_artifact_present=True,
        allow_missing_artifact=True,
    ),
)


def _parse_health_score(text: str) -> float | None:
    match = re.search(r"Learning Health Score:\s*([\d.]+)/100", text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def _run_script(root: Path, spec: LearningModuleSpec) -> dict[str, Any]:
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
                "reason": f"Exit {proc.returncode}; optional artifact",
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


def _advisory_summary(root: Path) -> dict[str, Any]:
    health_path = root / "learning_health_summary.txt"
    health_text = health_path.read_text(encoding="utf-8", errors="replace") if health_path.is_file() else ""
    score = _parse_health_score(health_text)
    status = "UNKNOWN"
    if "Status:" in health_text:
        for line in health_text.splitlines():
            if line.strip() in {"HEALTHY", "DEVELOPING", "LIMITED", "WEAK"}:
                status = line.strip()
                break
    return {
        "learning_health_score": score,
        "learning_health_status": status,
        "learning_summary": f"score={score} status={status}" if score is not None else "NO_DATA",
    }


def run_learning_modules(root: Path | str = ".") -> dict[str, Any]:
    root = Path(root)
    steps = [_run_script(root, spec) for spec in LEARNING_MODULES]
    ok = sum(1 for s in steps if s["status"] == "OK")
    skipped = sum(1 for s in steps if s["status"] == "SKIPPED")
    failed = sum(1 for s in steps if s["status"] in ("FAIL", "TIMEOUT"))
    return {
        "ok": failed == 0,
        "module_steps": steps,
        "step_counts": {"ok": ok, "skipped": skipped, "fail": failed},
        "modules_connected": [spec.name for spec in LEARNING_MODULES],
        "advisory_summary": _advisory_summary(root),
    }
