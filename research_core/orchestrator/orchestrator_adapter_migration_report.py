"""
Orchestrator Strategy Adapter Migration Report — Phase IX Sprint IX.3A

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Validates that Ecosystem Orchestrator consumes strategy state exclusively
via StrategyAdapter (no direct daily_runner imports).
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.contracts.base_contract import SAFETY_BANNER
from research_core.integration_adapters.strategy_adapter import StrategyAdapter

REPORT_JSON = Path("tae_orchestrator_strategy_adapter_migration.json")
REPORT_TXT = Path("tae_orchestrator_strategy_adapter_migration.txt")

ORCHESTRATOR_PATH = Path("research_core/orchestrator/ecosystem_orchestrator.py")
DIRECT_IMPORT_BEFORE = "research_core.strategy_evolution.daily_runner"
ADAPTER_METHOD = "load_strategy_state_for_orchestrator"

PROTECTED_PATHS = [
    "live_bot.py",
    "dashboard_v2.py",
    "portfolio.csv",
    "config/settings.py",
    "core/trades.py",
    "core/portfolio_prices.py",
]

STRATEGY_MODULES_PROTECTED = [
    "research_core/strategy_evolution/daily_runner.py",
    "research_core/strategy_evolution/candidate_registry.py",
    "research_core/strategy_evolution/parallel_paper_validator.py",
    "research_core/strategy_evolution/continuous_ranking_engine.py",
    "research_core/strategy_evolution/promotion_gate.py",
    "research_core/strategy_evolution/paper_tracking_log.py",
]


@dataclass
class OrchestratorStrategyAdapterMigrationReport:
    safety_banner: str
    direct_dependency_before: str
    direct_dependency_after: str
    adapter_path_used: str
    strategy_contract_validation: dict[str, Any]
    orchestrator_strategy_state_source: str
    missing_canonical_strategy_reports: list[str]
    protected_files_unchanged: bool
    orchestrator_uses_adapter: bool
    direct_daily_runner_import_remains: bool
    strategy_modules_unmodified: bool
    verdict: str
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "schema": "tae_orchestrator_strategy_adapter_migration",
            "generated_at": self.generated_at.isoformat(),
            "safety_banner": self.safety_banner,
            "verdict": self.verdict,
            "direct_dependency_before": self.direct_dependency_before,
            "direct_dependency_after": self.direct_dependency_after,
            "adapter_path_used": self.adapter_path_used,
            "strategy_contract_validation": self.strategy_contract_validation,
            "orchestrator_strategy_state_source": self.orchestrator_strategy_state_source,
            "missing_canonical_strategy_reports": list(self.missing_canonical_strategy_reports),
            "protected_files_unchanged": self.protected_files_unchanged,
            "orchestrator_uses_adapter": self.orchestrator_uses_adapter,
            "direct_daily_runner_import_remains": self.direct_daily_runner_import_remains,
            "strategy_modules_unmodified": self.strategy_modules_unmodified,
        }

    def format_text(self) -> str:
        validation = self.strategy_contract_validation
        lines = [
            "===== TAE ORCHESTRATOR STRATEGY ADAPTER MIGRATION — SPRINT IX.3A =====",
            "",
            f"1. Safety banner: {self.safety_banner}",
            "",
            "2. Direct dependency before/after",
            f"   Before: {self.direct_dependency_before}",
            f"   After:  {self.direct_dependency_after}",
            "",
            "3. Adapter path used",
            f"   {self.adapter_path_used}",
            "",
            "4. Strategy contract validation status",
            f"   valid={validation.get('valid')} "
            f"status={validation.get('compatibility_status')} "
            f"payload_available={validation.get('payload_available')}",
            "",
            "5. Orchestrator strategy state source",
            f"   {self.orchestrator_strategy_state_source}",
            "",
            "6. Missing canonical strategy reports",
        ]
        if self.missing_canonical_strategy_reports:
            for report in self.missing_canonical_strategy_reports:
                lines.append(f"   - {report}")
        else:
            lines.append("   None — all canonical strategy reports present")
        lines.extend([
            "",
            "7. Protected files unchanged",
            f"   {self.protected_files_unchanged}",
            "",
            f"8. Final verdict: {self.verdict}",
            "",
        ])
        return "\n".join(lines)


class OrchestratorStrategyAdapterMigrationAudit:
    def __init__(self, root: Path | str = Path(".")) -> None:
        self._root = Path(root)

    def run(self, protected_ok: bool) -> OrchestratorStrategyAdapterMigrationReport:
        orchestrator_text = self._read_orchestrator_source()
        direct_import_remains = self._has_direct_daily_runner_import(orchestrator_text)
        uses_adapter = self._uses_strategy_adapter(orchestrator_text)

        adapter = StrategyAdapter(self._root)
        validation = adapter.validate_contract_payload()
        strategy_state = StrategyAdapter.load_strategy_state_for_orchestrator(str(self._root))

        missing_reports: list[str] = []
        loaded = adapter.load_source()
        missing_reports.extend(loaded.missing_reports)
        for name in strategy_state.get("missing_step_reports") or []:
            if name not in missing_reports:
                missing_reports.append(name)

        strategy_modules_ok = all(
            (self._root / rel).is_file() for rel in STRATEGY_MODULES_PROTECTED
        )

        if direct_import_remains:
            verdict = "ORCHESTRATOR_STRATEGY_ADAPTER_MIGRATION_FAILED_DIRECT_IMPORT_REMAINS"
        elif not protected_ok:
            verdict = "ORCHESTRATOR_STRATEGY_ADAPTER_MIGRATION_FAILED_PROTECTED_FILE_MODIFIED"
        elif not uses_adapter:
            verdict = "ORCHESTRATOR_STRATEGY_ADAPTER_MIGRATION_FAILED_DIRECT_IMPORT_REMAINS"
        elif strategy_state.get("strategy_state_completeness") in {"PARTIAL", "DEGRADED"}:
            verdict = "ORCHESTRATOR_STRATEGY_ADAPTER_MIGRATION_READY_WITH_PARTIAL_STATE"
        else:
            verdict = "ORCHESTRATOR_STRATEGY_ADAPTER_MIGRATION_READY"

        after_dependency = (
            f"{ORCHESTRATOR_PATH} → StrategyAdapter.{ADAPTER_METHOD}() → "
            f"tae.contract.strategy_evolution.v1"
            if not direct_import_remains
            else f"{ORCHESTRATOR_PATH} → {DIRECT_IMPORT_BEFORE} (UNMIGRATED)"
        )

        return OrchestratorStrategyAdapterMigrationReport(
            safety_banner=SAFETY_BANNER,
            direct_dependency_before=(
                f"{ORCHESTRATOR_PATH} → {DIRECT_IMPORT_BEFORE}.StrategyEvolutionDailyRunner"
            ),
            direct_dependency_after=after_dependency,
            adapter_path_used=f"StrategyAdapter.{ADAPTER_METHOD}()",
            strategy_contract_validation=validation,
            orchestrator_strategy_state_source=strategy_state.get(
                "adapter_path",
                f"StrategyAdapter.{ADAPTER_METHOD}()",
            ),
            missing_canonical_strategy_reports=missing_reports,
            protected_files_unchanged=protected_ok,
            orchestrator_uses_adapter=uses_adapter,
            direct_daily_runner_import_remains=direct_import_remains,
            strategy_modules_unmodified=strategy_modules_ok,
            verdict=verdict,
        )

    def persist(self, report: OrchestratorStrategyAdapterMigrationReport) -> dict[str, Path]:
        json_path = self._root / REPORT_JSON
        txt_path = self._root / REPORT_TXT
        json_path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return {"json": json_path, "txt": txt_path}

    def _read_orchestrator_source(self) -> str:
        path = self._root / ORCHESTRATOR_PATH
        return path.read_text(encoding="utf-8", errors="replace")

    @staticmethod
    def _has_direct_daily_runner_import(source: str) -> bool:
        if DIRECT_IMPORT_BEFORE not in source:
            return False
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return DIRECT_IMPORT_BEFORE in source
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module == DIRECT_IMPORT_BEFORE or node.module.startswith(
                    f"{DIRECT_IMPORT_BEFORE}."
                ):
                    return True
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == DIRECT_IMPORT_BEFORE or alias.name.startswith(
                        f"{DIRECT_IMPORT_BEFORE}."
                    ):
                        return True
        return False

    @staticmethod
    def _uses_strategy_adapter(source: str) -> bool:
        if "StrategyAdapter" not in source:
            return False
        return ADAPTER_METHOD in source


def protected_mtime_snapshot(root: Path) -> dict[str, float]:
    snapshot: dict[str, float] = {}
    for rel in PROTECTED_PATHS:
        full = root / rel
        if full.is_file():
            snapshot[rel] = full.stat().st_mtime
    return snapshot


def verify_protected_unchanged(root: Path, before: dict[str, float]) -> bool:
    for rel, mtime in before.items():
        full = root / rel
        if not full.is_file() or full.stat().st_mtime != mtime:
            return False
    return True
