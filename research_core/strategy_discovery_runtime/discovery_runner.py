"""Strategy discovery runtime orchestrator — invokes existing discovery scripts only."""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PYTHON = sys.executable


@dataclass
class DiscoveryModuleSpec:
    name: str
    script: str
    artifact: str
    skip_if_artifact_present: bool = False
    needs_pythonpath: bool = True
    timeout_seconds: int = 300
    allow_missing_artifact: bool = False


DISCOVERY_MODULES: tuple[DiscoveryModuleSpec, ...] = (
    DiscoveryModuleSpec(
        name="strategy_discovery_engine",
        script="tae_phase10_strategy_discovery_demo.py",
        artifact="tae_strategy_discovery.json",
    ),
)

READ_ONLY_ARTIFACTS: tuple[str, ...] = (
    "tae_strategy_discovery.json",
    "tae_strategy_discovery.txt",
)


def _run_script(root: Path, spec: DiscoveryModuleSpec) -> dict[str, Any]:
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

    status = "OK" if artifact_ok else "SKIPPED"
    return {
        "name": spec.name,
        "status": status,
        "artifact": spec.artifact,
        "artifact_present": artifact_ok,
        "runtime_seconds": round(time.monotonic() - started, 3),
    }


def _advisory_summary(root: Path) -> dict[str, Any]:
    path = root / "tae_strategy_discovery.json"
    if not path.is_file():
        return {}
    try:
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    registry = payload.get("discovery_registry") or []
    top = sorted(registry, key=lambda x: float(x.get("confidence_seed") or 0), reverse=True)[:10]
    return {
        "verdict": payload.get("verdict"),
        "candidate_count": payload.get("candidate_count"),
        "average_confidence_seed": payload.get("average_confidence_seed"),
        "top_discovered_strategies": [
            {
                "discovery_id": item.get("discovery_id"),
                "market": item.get("market"),
                "confidence_seed": item.get("confidence_seed"),
                "risk": item.get("risk"),
            }
            for item in top
        ],
    }


def run_discovery_modules(root: Path | str = ".") -> dict[str, Any]:
    root = Path(root)
    steps = [_run_script(root, spec) for spec in DISCOVERY_MODULES]
    artifacts_loaded = {name: (root / name).is_file() for name in READ_ONLY_ARTIFACTS}
    ok = sum(1 for s in steps if s["status"] == "OK")
    skipped = sum(1 for s in steps if s["status"] == "SKIPPED")
    failed = sum(1 for s in steps if s["status"] in ("FAIL", "TIMEOUT"))
    return {
        "ok": failed == 0,
        "module_steps": steps,
        "artifacts_loaded": artifacts_loaded,
        "step_counts": {"ok": ok, "skipped": skipped, "fail": failed},
        "modules_connected": [spec.name for spec in DISCOVERY_MODULES],
        "read_only_artifacts": list(READ_ONLY_ARTIFACTS),
        "advisory_summary": _advisory_summary(root),
    }
