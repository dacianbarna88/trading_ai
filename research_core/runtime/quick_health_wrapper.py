"""
Quick Health Check wrapper — Phase IX Sprint IX.4

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Thin read-only wrapper over RuntimeHealth, ecosystem JSON, and live-ops signals.
Does not start/stop bot, broker, or duplicate engine logic.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.runtime.ecosystem_state import EcosystemStateLoader
from research_core.runtime.quick_health_report import (
    QuickHealthCheckItem,
    QuickHealthReport,
    QuickHealthReportStore,
    QuickHealthVerdict,
)
from research_core.runtime.runtime_health import HealthStatus, RuntimeHealth
from research_core.runtime.runtime_report import DEFAULT_JSON_PATH as RUNTIME_FOUNDATION_JSON
from research_core.runtime.learning_memory import LEARNING_JSON_PATH
from research_core.strategy_evolution.candidate_report import SAFETY_BANNER

PROTECTED_PATHS = [
    Path("live_bot.py"),
    Path("dashboard_v2.py"),
    Path("portfolio.csv"),
    Path("config/settings.py"),
    Path("core/trades.py"),
    Path("core/portfolio_prices.py"),
]

OPTIONAL_LAYER_REPORTS = {
    "accounting": Path("tae_accounting_integration_report.json"),
    "evidence": Path("tae_evidence_integration_report.json"),
    "contracts": Path("tae_contract_report.json"),
    "adapters": Path("tae_adapter_report.json"),
    "performance_pipeline": Path("tae_performance_pipeline_report.json"),
}

ORCHESTRATOR_JSON = Path("tae_ecosystem_orchestrator.json")
PROCESS_HEALTH_JSON = Path("process_health.json")
BOT_STATUS_TXT = Path("bot_status.txt")
BOT_LOG = Path("bot_output.log")
LIVE_SIGNALS_CSV = Path("live_signals.csv")
PORTFOLIO_CSV = Path("portfolio.csv")
MORNING_CONTROL_ROOM = Path("tools/morning_control_room.sh")

DASHBOARD_PORTS = (8501, 8502, 8503)


class QuickHealthWrapper:
    def __init__(self, root: Path | str = Path(".")) -> None:
        self._root = Path(root)

    def run(self) -> QuickHealthReport:
        warnings: list[str] = []
        checks: list[QuickHealthCheckItem] = []

        before_mtimes = self._protected_mtime_snapshot()
        git_status = self._git_status()
        if git_status != "CLEAN":
            warnings.append(f"Git working tree not clean: {git_status}")

        state = EcosystemStateLoader(self._root).load()
        after_mtimes = self._protected_mtime_snapshot()
        protected_ok = self._protected_unchanged(before_mtimes, after_mtimes)
        if not protected_ok:
            warnings.append("Protected file mtimes changed during quick health check")

        health_report = RuntimeHealth(protected_files_unchanged=protected_ok).evaluate(state)
        runtime_foundation = self._load_json(RUNTIME_FOUNDATION_JSON)
        learning_memory = self._load_json(LEARNING_JSON_PATH)
        orchestrator_payload = self._load_json(ORCHESTRATOR_JSON) or state.sections.get(
            "ecosystem"
        )

        live_ops = self._gather_live_ops(warnings)
        control_room_summary = self._wrap_morning_control_room()

        layer_status = {
            key: self._layer_verdict(path)
            for key, path in OPTIONAL_LAYER_REPORTS.items()
        }
        for key, status in layer_status.items():
            if status is None:
                warnings.append(f"Optional {key} integration report not available")

        paper_summary = self._paper_tracking_summary(state)
        orchestrator_verdict = None
        if isinstance(orchestrator_payload, dict):
            orchestrator_verdict = orchestrator_payload.get("verdict")

        runtime_verdict = None
        if isinstance(runtime_foundation, dict):
            runtime_verdict = runtime_foundation.get("verdict")

        canonical_artifacts = {
            "tae_runtime_foundation.json": RUNTIME_FOUNDATION_JSON.is_file(),
            "tae_runtime_foundation.txt": (self._root / "tae_runtime_foundation.txt").is_file(),
            "tae_runtime_learning_memory.json": LEARNING_JSON_PATH.is_file(),
            "tae_runtime_learning_memory.txt": (
                self._root / "tae_runtime_learning_memory.txt"
            ).is_file(),
            "tae_ecosystem_orchestrator.json": ORCHESTRATOR_JSON.is_file(),
            "tae_ecosystem_orchestrator.txt": (
                self._root / "tae_ecosystem_orchestrator.txt"
            ).is_file(),
        }
        for name, loaded in state.sources_loaded.items():
            canonical_artifacts[name] = loaded

        checks.extend(self._build_check_matrix(
            git_status=git_status,
            protected_ok=protected_ok,
            health_status=health_report.overall_status,
            orchestrator_verdict=orchestrator_verdict,
            layer_status=layer_status,
            live_ops=live_ops,
            canonical_artifacts=canonical_artifacts,
        ))

        verdict = self._final_verdict(
            protected_ok=protected_ok,
            health_status=health_report.overall_status,
            health_issues=health_report.issues,
            warnings=warnings,
        )

        if control_room_summary:
            live_ops["morning_control_room_overall"] = control_room_summary

        return QuickHealthReport(
            safety_banner=SAFETY_BANNER,
            verdict=verdict,
            checks=checks,
            warnings=warnings,
            runtime_health_status=health_report.overall_status,
            runtime_verdict=runtime_verdict,
            runtime_issues=list(health_report.issues),
            missing_connections=list(state.missing_connections),
            orchestrator_verdict=orchestrator_verdict,
            top_ranked_strategy_id=state.top_ranked_strategy_id,
            paper_tracking_summary=paper_summary,
            accounting_integration_status=layer_status.get("accounting"),
            evidence_integration_status=layer_status.get("evidence"),
            contract_layer_status=layer_status.get("contracts"),
            adapter_layer_status=layer_status.get("adapters"),
            performance_pipeline_status=layer_status.get("performance_pipeline")
            or state.verdicts.get("performance_pipeline"),
            strategic_performance_status=state.verdicts.get("strategic_performance"),
            accounting_integrity_status=state.verdicts.get("accounting_integrity"),
            git_status=git_status,
            protected_files_unchanged=protected_ok,
            live_ops_summary=live_ops,
            canonical_artifacts=canonical_artifacts,
        )

    def persist(self, report: QuickHealthReport) -> dict[str, Path]:
        store = QuickHealthReportStore()
        return {
            "json": store.persist(report),
            "txt": store.persist_txt(report),
        }

    def _final_verdict(
        self,
        protected_ok: bool,
        health_status: str,
        health_issues: list[str],
        warnings: list[str],
    ) -> QuickHealthVerdict:
        if not protected_ok:
            return QuickHealthVerdict.TAE_QUICK_HEALTH_NOT_READY
        if health_status == HealthStatus.CRITICAL.value:
            return QuickHealthVerdict.TAE_QUICK_HEALTH_NOT_READY

        has_warnings = bool(warnings)
        degraded = health_status == HealthStatus.DEGRADED.value
        backlog_only = degraded and RuntimeHealth.integration_backlog_only(health_issues)

        if has_warnings or degraded:
            if backlog_only and protected_ok and health_status != HealthStatus.CRITICAL.value:
                return QuickHealthVerdict.TAE_QUICK_HEALTH_READY_WITH_WARNINGS
            if has_warnings:
                return QuickHealthVerdict.TAE_QUICK_HEALTH_READY_WITH_WARNINGS
            if degraded:
                return QuickHealthVerdict.TAE_QUICK_HEALTH_READY_WITH_WARNINGS

        return QuickHealthVerdict.TAE_QUICK_HEALTH_READY

    def _gather_live_ops(self, warnings: list[str]) -> dict[str, Any]:
        summary: dict[str, Any] = {}

        bot_running = self._process_detected("live_bot")
        summary["bot_process"] = "RUNNING" if bot_running else "NOT DETECTED"
        if not bot_running:
            warnings.append("Bot process not detected (PAPER_ONLY — warning only)")

        dashboard_port = self._dashboard_port_status()
        streamlit_running = self._process_detected("streamlit") or self._process_detected(
            "dashboard_v2"
        )
        if dashboard_port or streamlit_running:
            summary["dashboard_process"] = (
                f"RUNNING (port {dashboard_port})" if dashboard_port else "RUNNING (process detected)"
            )
        else:
            summary["dashboard_process"] = "NOT DETECTED"
            warnings.append("Dashboard/Streamlit not detected (warning only)")

        if PROCESS_HEALTH_JSON.is_file():
            payload = self._load_json(PROCESS_HEALTH_JSON) or {}
            summary["process_health"] = payload.get("status", "UNKNOWN")
            summary["process_health_checked_at"] = payload.get("checked_at")
        else:
            summary["process_health"] = "MISSING"
            warnings.append("process_health.json missing")

        if BOT_STATUS_TXT.is_file():
            summary["bot_status_txt"] = BOT_STATUS_TXT.read_text(
                encoding="utf-8", errors="replace"
            ).strip()[:120]
        else:
            summary["bot_status_txt"] = "MISSING"

        summary["live_signals_freshness"] = self._file_freshness(LIVE_SIGNALS_CSV)
        if not LIVE_SIGNALS_CSV.is_file():
            warnings.append("live_signals.csv missing")

        summary["portfolio_readable"] = self._portfolio_readable()
        summary["logs_readable"] = self._logs_readable()

        return summary

    def _wrap_morning_control_room(self) -> str | None:
        script = self._root / MORNING_CONTROL_ROOM
        if not script.is_file():
            return None
        try:
            result = subprocess.run(
                ["bash", str(script)],
                cwd=self._root,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        output = result.stdout or ""
        for line in output.splitlines():
            stripped = line.strip()
            if stripped in {"SYSTEM HEALTHY", "CHECK REQUIRED"}:
                return stripped
        return None

    @staticmethod
    def _paper_tracking_summary(state) -> str | None:
        verdict = state.verdicts.get("paper_tracking")
        count = len(state.paper_tracking_needs)
        if verdict:
            return f"{verdict} ({count} entries)"
        if count:
            return f"{count} entries (verdict unavailable)"
        return None

    def _build_check_matrix(
        self,
        git_status: str,
        protected_ok: bool,
        health_status: str,
        orchestrator_verdict: str | None,
        layer_status: dict[str, str | None],
        live_ops: dict[str, Any],
        canonical_artifacts: dict[str, bool],
    ) -> list[QuickHealthCheckItem]:
        return [
            QuickHealthCheckItem("safety_banner", "OK", SAFETY_BANNER),
            QuickHealthCheckItem(
                "git_status",
                "WARN" if git_status != "CLEAN" else "OK",
                git_status,
            ),
            QuickHealthCheckItem(
                "protected_files",
                "OK" if protected_ok else "FAIL",
                "unchanged" if protected_ok else "modified during check",
            ),
            QuickHealthCheckItem(
                "runtime_health",
                health_status,
                f"RuntimeHealth overall={health_status}",
            ),
            QuickHealthCheckItem(
                "orchestrator",
                "OK" if orchestrator_verdict else "WARN",
                orchestrator_verdict or "orchestrator report unavailable",
            ),
            QuickHealthCheckItem(
                "accounting_integration",
                "OK" if layer_status.get("accounting") else "WARN",
                layer_status.get("accounting") or "report missing",
            ),
            QuickHealthCheckItem(
                "evidence_integration",
                "OK" if layer_status.get("evidence") else "WARN",
                layer_status.get("evidence") or "report missing",
            ),
            QuickHealthCheckItem(
                "contract_layer",
                "OK" if layer_status.get("contracts") else "WARN",
                layer_status.get("contracts") or "report missing",
            ),
            QuickHealthCheckItem(
                "adapter_layer",
                "OK" if layer_status.get("adapters") else "WARN",
                layer_status.get("adapters") or "report missing",
            ),
            QuickHealthCheckItem(
                "performance_pipeline",
                "OK" if layer_status.get("performance_pipeline") else "WARN",
                layer_status.get("performance_pipeline")
                or "pipeline report missing — run tae_phase9_performance_pipeline_demo.py",
            ),
            QuickHealthCheckItem(
                "bot_process",
                "WARN" if live_ops.get("bot_process") == "NOT DETECTED" else "OK",
                str(live_ops.get("bot_process")),
            ),
            QuickHealthCheckItem(
                "dashboard_process",
                "WARN" if "NOT DETECTED" in str(live_ops.get("dashboard_process")) else "OK",
                str(live_ops.get("dashboard_process")),
            ),
            QuickHealthCheckItem(
                "live_signals",
                "OK" if LIVE_SIGNALS_CSV.is_file() else "WARN",
                str(live_ops.get("live_signals_freshness")),
            ),
            QuickHealthCheckItem(
                "portfolio",
                "OK" if live_ops.get("portfolio_readable") == "readable" else "WARN",
                str(live_ops.get("portfolio_readable")),
            ),
            QuickHealthCheckItem(
                "logs",
                "OK" if live_ops.get("logs_readable") == "readable" else "WARN",
                str(live_ops.get("logs_readable")),
            ),
            QuickHealthCheckItem(
                "runtime_artifacts",
                "OK" if canonical_artifacts.get("tae_runtime_foundation.json") else "WARN",
                "runtime foundation artifact presence checked",
            ),
        ]

    def _protected_mtime_snapshot(self) -> dict[str, float]:
        snapshot: dict[str, float] = {}
        for path in PROTECTED_PATHS:
            full = self._root / path
            if full.is_file():
                snapshot[str(path)] = full.stat().st_mtime
        return snapshot

    @staticmethod
    def _protected_unchanged(before: dict[str, float], after: dict[str, float]) -> bool:
        for key, mtime in before.items():
            if key not in after or after[key] != mtime:
                return False
        return True

    def _git_status(self) -> str:
        if shutil.which("git") is None:
            return "GIT_UNAVAILABLE"
        try:
            result = subprocess.run(
                ["git", "status", "--short"],
                cwd=self._root,
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired):
            return "GIT_ERROR"
        if result.returncode != 0:
            return "NOT_A_REPOSITORY"
        output = (result.stdout or "").strip()
        return "CLEAN" if not output else output.replace("\n", "; ")[:500]

    def _process_detected(self, pattern: str) -> bool:
        if shutil.which("pgrep") is None:
            return False
        try:
            result = subprocess.run(
                ["pgrep", "-fl", pattern],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return bool((result.stdout or "").strip())

    def _dashboard_port_status(self) -> int | None:
        if shutil.which("lsof") is None:
            return None
        for port in DASHBOARD_PORTS:
            try:
                result = subprocess.run(
                    ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=10,
                )
            except (OSError, subprocess.TimeoutExpired):
                continue
            if result.returncode == 0 and (result.stdout or "").strip():
                return port
        return None

    def _file_freshness(self, path: Path) -> str:
        full = self._root / path
        if not full.is_file():
            return "missing"
        mtime = datetime.fromtimestamp(full.stat().st_mtime, tz=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - mtime).total_seconds() / 3600
        return f"updated {mtime.isoformat()} ({age_hours:.1f}h ago)"

    def _portfolio_readable(self) -> str:
        full = self._root / PORTFOLIO_CSV
        if not full.is_file():
            return "missing"
        try:
            with full.open(encoding="utf-8", errors="replace") as handle:
                handle.readline()
            return "readable"
        except OSError:
            return "unreadable"

    def _logs_readable(self) -> str:
        full = self._root / BOT_LOG
        if not full.is_file():
            return "bot_output.log missing"
        try:
            with full.open(encoding="utf-8", errors="replace") as handle:
                handle.readline()
            return "readable"
        except OSError:
            return "unreadable"

    def _load_json(self, path: Path) -> dict[str, Any] | None:
        full = self._root / path
        if not full.is_file():
            return None
        try:
            payload = json.loads(full.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def _layer_verdict(self, path: Path) -> str | None:
        payload = self._load_json(path)
        if payload is None:
            return None
        return str(payload.get("verdict", "UNKNOWN"))
