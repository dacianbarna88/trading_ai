#!/usr/bin/env python3
"""
Canonical runtime path resolver — LIVE vs Parallel V1 vs Parallel V2.

PAPER_ONLY | NO_BROKER
No trading logic. Absolute paths only; cwd-independent.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

RuntimeId = Literal["live", "parallel_v1", "parallel_v2"]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ENV = "TAE_RUNTIME_ID"
DEFAULT_RUNTIME: RuntimeId = "live"

VALID_RUNTIMES: tuple[RuntimeId, ...] = ("live", "parallel_v1", "parallel_v2")


@dataclass(frozen=True)
class RuntimePaths:
    runtime_id: RuntimeId
    project_root: Path
    portfolio: Path
    portfolio_lock: Path
    portfolio_owner_sidecar: Path
    signals: Path
    alerts: Path
    bot_log: Path
    bot_pid: Path
    bot_status: Path
    advisory: Path
    accounting_snapshot: Path
    execution_journal: Path
    learning_root: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "runtime_id": self.runtime_id,
            "project_root": str(self.project_root),
            "portfolio": str(self.portfolio),
            "portfolio_lock": str(self.portfolio_lock),
            "portfolio_owner_sidecar": str(self.portfolio_owner_sidecar),
            "signals": str(self.signals),
            "alerts": str(self.alerts),
            "bot_log": str(self.bot_log),
            "bot_pid": str(self.bot_pid),
            "bot_status": str(self.bot_status),
            "advisory": str(self.advisory),
            "accounting_snapshot": str(self.accounting_snapshot),
            "execution_journal": str(self.execution_journal),
            "learning_root": str(self.learning_root),
        }


def normalize_runtime_id(raw: str | None) -> RuntimeId:
    if raw is None or str(raw).strip() == "":
        return DEFAULT_RUNTIME
    value = str(raw).strip().lower()
    aliases = {
        "live": "live",
        "v2": "live",  # operator/docs "TAE V2" live ledger
        "live_v2": "live",
        "parallel_v1": "parallel_v1",
        "v1": "parallel_v1",
        "paper_v1": "parallel_v1",
        "parallel_v2": "parallel_v2",
        "paper_v2": "parallel_v2",
    }
    if value not in aliases:
        raise ValueError(
            f"RUNTIME_ISOLATION_VIOLATION: unknown runtime_id={raw!r}; "
            f"allowed={sorted(set(aliases))}"
        )
    return aliases[value]  # type: ignore[return-value]


def resolve_runtime_id(
    *,
    explicit: str | None = None,
    require_explicit: bool = False,
) -> RuntimeId:
    env_val = os.environ.get(RUNTIME_ENV)
    if require_explicit and explicit is None and not env_val:
        raise ValueError(
            "RUNTIME_ISOLATION_VIOLATION: runtime version required "
            f"(pass explicit id or set {RUNTIME_ENV})"
        )
    return normalize_runtime_id(explicit if explicit is not None else env_val)


def get_runtime_paths(
    runtime_id: str | None = None,
    *,
    project_root: Path | str | None = None,
    require_explicit: bool = False,
) -> RuntimePaths:
    root = Path(project_root or PROJECT_ROOT).resolve()
    rid = resolve_runtime_id(explicit=runtime_id, require_explicit=require_explicit)

    if rid == "live":
        # LIVE capital stays at project root for compatibility; always absolute.
        portfolio = root / "portfolio.csv"
        return RuntimePaths(
            runtime_id=rid,
            project_root=root,
            portfolio=portfolio,
            portfolio_lock=root / "portfolio.csv.lock",
            portfolio_owner_sidecar=root / "portfolio.csv.runtime.json",
            signals=root / "live_signals.csv",
            alerts=root / "alerts_log.csv",
            bot_log=root / "bot_output.log",
            bot_pid=root / "bot_pid.txt",
            bot_status=root / "bot_status.txt",
            advisory=root / "tae_live_advisory.json",
            accounting_snapshot=root / "tae_accounting_snapshot.json",
            execution_journal=root / "runtime_outputs" / "live" / "execution_journal.jsonl",
            learning_root=root / "runtime_outputs" / "canonical_learning",
        )

    if rid == "parallel_v1":
        base = root / "runtime_outputs" / "parallel_paper" / "v1"
        return RuntimePaths(
            runtime_id=rid,
            project_root=root,
            portfolio=base / "portfolio.json",
            portfolio_lock=base / "portfolio.lock",
            portfolio_owner_sidecar=base / "portfolio.runtime.json",
            signals=base / "signals.csv",
            alerts=base / "alerts.jsonl",
            bot_log=base / "daemon.log",
            bot_pid=base / "runtime.pid",
            bot_status=base / "health.json",
            advisory=base / "advisory.json",
            accounting_snapshot=base / "accounting_snapshot.json",
            execution_journal=base / "journals" / "executions.jsonl",
            learning_root=root / "runtime_outputs" / "canonical_learning",
        )

    base = root / "runtime_outputs" / "parallel_paper" / "v2"
    return RuntimePaths(
        runtime_id=rid,
        project_root=root,
        portfolio=base / "portfolio.json",
        portfolio_lock=base / "portfolio.lock",
        portfolio_owner_sidecar=base / "portfolio.runtime.json",
        signals=base / "signals.csv",
        alerts=base / "alerts.jsonl",
        bot_log=base / "daemon.log",
        bot_pid=base / "runtime.pid",
        bot_status=base / "health.json",
        advisory=base / "advisory.json",
        accounting_snapshot=base / "accounting_snapshot.json",
        execution_journal=base / "journals" / "executions.jsonl",
        learning_root=root / "runtime_outputs" / "canonical_learning",
    )


def mutable_isolation_paths(paths: RuntimePaths) -> set[Path]:
    """Critical mutable surfaces that must not collide across runtimes."""
    return {
        paths.portfolio.resolve(),
        paths.portfolio_lock.resolve(),
        paths.portfolio_owner_sidecar.resolve(),
        paths.signals.resolve(),
        paths.alerts.resolve(),
        paths.bot_log.resolve(),
        paths.bot_pid.resolve(),
        paths.bot_status.resolve(),
        paths.advisory.resolve(),
        paths.accounting_snapshot.resolve(),
        paths.execution_journal.resolve(),
    }


def assert_paths_isolated(a: RuntimePaths, b: RuntimePaths) -> None:
    if a.runtime_id == b.runtime_id:
        raise ValueError("runtimes must differ for isolation assert")
    overlap = mutable_isolation_paths(a) & mutable_isolation_paths(b)
    if overlap:
        raise RuntimeError(
            "RUNTIME_ISOLATION_VIOLATION: mutable path collision "
            + ", ".join(str(p) for p in sorted(overlap))
        )


def health_runtime_report(runtime_id: str | None = None) -> dict[str, Any]:
    paths = get_runtime_paths(runtime_id)
    return {
        "runtime_version": paths.runtime_id,
        "project_root": str(paths.project_root),
        "paths": paths.as_dict(),
        "cwd_independent": True,
    }


def read_owner_sidecar(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def write_owner_sidecar(
    paths: RuntimePaths,
    *,
    writer_module: str,
    writer_pid: int | None = None,
) -> dict[str, Any]:
    payload = {
        "runtime_version": paths.runtime_id,
        "project_root": str(paths.project_root),
        "writer_module": writer_module,
        "writer_pid": int(writer_pid or os.getpid()),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "portfolio_path": str(paths.portfolio),
    }
    paths.portfolio_owner_sidecar.parent.mkdir(parents=True, exist_ok=True)
    tmp = paths.portfolio_owner_sidecar.with_suffix(
        paths.portfolio_owner_sidecar.suffix + ".tmp"
    )
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(paths.portfolio_owner_sidecar)
    return payload


def verify_write_allowed(
    paths: RuntimePaths,
    *,
    target: Path,
    writer_module: str,
) -> None:
    """Refuse cross-runtime / cross-project overwrites."""
    target = target.resolve()
    expected = {
        paths.portfolio.resolve(),
        paths.advisory.resolve(),
        paths.accounting_snapshot.resolve(),
        paths.signals.resolve(),
        paths.alerts.resolve(),
        paths.bot_log.resolve(),
        paths.bot_status.resolve(),
        paths.execution_journal.resolve(),
        paths.portfolio_lock.resolve(),
        paths.portfolio_owner_sidecar.resolve(),
    }
    if target not in expected:
        raise RuntimeError(
            f"RUNTIME_ISOLATION_VIOLATION: {writer_module} cannot write {target} "
            f"for runtime={paths.runtime_id}"
        )

    sidecar = read_owner_sidecar(paths.portfolio_owner_sidecar)
    if sidecar:
        if sidecar.get("runtime_version") not in (None, paths.runtime_id):
            raise RuntimeError(
                "RUNTIME_ISOLATION_VIOLATION: sidecar runtime_version="
                f"{sidecar.get('runtime_version')} expected={paths.runtime_id}"
            )
        side_root = sidecar.get("project_root")
        if side_root and Path(str(side_root)).resolve() != paths.project_root.resolve():
            raise RuntimeError(
                "RUNTIME_ISOLATION_VIOLATION: sidecar project_root mismatch "
                f"{side_root} != {paths.project_root}"
            )


def portfolio_write_guard(
    paths: RuntimePaths,
    *,
    writer_module: str,
    new_is_empty: bool,
) -> None:
    verify_write_allowed(paths, target=paths.portfolio, writer_module=writer_module)
    if new_is_empty and paths.portfolio.is_file() and paths.portfolio.stat().st_size > 64:
        raise RuntimeError(
            "PORTFOLIO_WRITE_FAILED: refusing to overwrite non-empty "
            f"{paths.portfolio} with empty frame"
        )
