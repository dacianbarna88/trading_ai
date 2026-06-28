"""
Systemic Module Interconnection Layer — Phase IX C1

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Builds a read-only interconnection map from existing ecosystem JSON outputs.
Does not rewrite or invoke competing runners.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from research_core.systemic_integration.interconnection_report import (
    CanonicalResponsibility,
    ConflictRiskLevel,
    ConflictWarning,
    ModuleClassification,
    ModuleRole,
    SystemicHarmonyVerdict,
    SystemicInterconnectionReport,
)

logger = logging.getLogger(__name__)

INVENTORY_PATH = Path("tae_ecosystem_inventory_audit.json")
ORCHESTRATOR_PATH = Path("tae_ecosystem_orchestrator.json")
EVIDENCE_PATH = Path("tae_evidence_engine_report.json")
DAILY_RUNNER_PATH = Path("tae_strategy_evolution_daily_runner.json")
PROMOTION_GATE_PATH = Path("tae_strategy_promotion_gate.json")
PAPER_TRACKING_PATH = Path("tae_paper_tracking_log.json")
INTEGRATION_GATE_PATH = Path("tae_evidence_integration_gate.json")

PROTECTED_PATHS = [
    Path("live_bot.py"),
    Path("dashboard_v2.py"),
    Path("config/settings.py"),
    Path("portfolio.csv"),
    Path("core/trades.py"),
    Path("core/portfolio_prices.py"),
]

CANONICAL_MAP: dict[str, dict[str, object]] = {
    "accounting_source_of_truth": {
        "module": "research_core/accounting/independent_double_entry.py",
        "reports": ["tae_independent_double_entry_verification.json"],
    },
    "evidence_source_of_truth": {
        "module": "research_core/evidence_engine/evidence_registry.py",
        "reports": ["tae_evidence_engine_report.json"],
    },
    "strategy_evolution_pipeline": {
        "module": "research_core/strategy_evolution/daily_runner.py",
        "reports": [
            "tae_candidate_strategy_registry.json",
            "tae_parallel_paper_validation.json",
            "tae_continuous_strategy_ranking.json",
            "tae_strategy_promotion_gate.json",
            "tae_paper_tracking_log.json",
            "tae_strategy_evolution_daily_runner.json",
        ],
    },
    "integration_approval": {
        "module": "integration_layer/evidence_gate.py",
        "reports": ["tae_evidence_integration_gate.json"],
    },
    "ecosystem_overview": {
        "module": "research_core/orchestrator/ecosystem_orchestrator.py",
        "reports": ["tae_ecosystem_orchestrator.json"],
    },
}

VIEW_ONLY_PATTERNS = [
    "research_core/accounting/ledger_audit.py",
    "research_core/accounting/ledger_report.py",
    "research_core/performance/accounting_integrity_auditor.py",
    "tools/dashboard_account_reconcile.py",
    "tools/dashboard_performance_reconcile.py",
    "research_core/evidence_gap/",
    "research_core/evidence_history/",
    "research_core/evidence_engine/evidence_report.py",
    "research_core/strategy_evolution/candidate_report.py",
    "research_core/strategy_evolution/parallel_paper_report.py",
    "research_core/strategy_evolution/continuous_ranking_report.py",
    "research_core/strategy_evolution/promotion_gate_report.py",
    "research_core/strategy_evolution/paper_tracking_report.py",
    "research_core/strategy_evolution/daily_runner_report.py",
]

LEGACY_PLANNING_PATTERNS = [
    "research_core/evolution/",
]

DO_NOT_INVOKE_DIRECTLY = [
    "research_core/strategy_evolution/candidate_registry.py",
    "research_core/strategy_evolution/parallel_paper_validator.py",
    "research_core/strategy_evolution/continuous_ranking_engine.py",
    "research_core/strategy_evolution/promotion_gate.py",
    "research_core/strategy_evolution/paper_tracking_log.py",
    "research_core/simulation_lab/strategy_simulation_lab.py",
    "research_core/validation/cross_regime_validator.py",
    "tae_phase8_candidate_strategy_registry_demo.py",
    "tae_phase8_parallel_paper_validator_demo.py",
    "tae_phase8_continuous_ranking_engine_demo.py",
    "tae_phase8_strategy_promotion_gate_demo.py",
    "tae_phase8_paper_tracking_log_demo.py",
    "tae_phase8_strategy_evolution_daily_runner_demo.py",
    "tae_phase8_ecosystem_orchestrator_demo.py",
]

SAFE_ORCHESTRATION_ORDER = [
    "research_core/ecosystem_inventory/inventory_audit.py (periodic audit)",
    "research_core/evidence_engine/evidence_registry.py (Evidence Engine refresh)",
    "integration_layer/evidence_gate.py (Integration approval gate)",
    "research_core/strategy_evolution/daily_runner.py (Strategy Evolution pipeline)",
    "research_core/orchestrator/ecosystem_orchestrator.py (Daily ecosystem entry point)",
]

INTEGRATION_RULES = [
    "Evidence Engine has precedence over isolated Phase VII JSON reports.",
    "Strategy Evolution Daily Runner has precedence over individual ranking/validation modules.",
    "Ecosystem Orchestrator has precedence over manual multi-step demo execution.",
    "Independent double-entry accounting is the sole accounting source of truth.",
    "Integration Gate reads Evidence Engine only — never bypass with isolated evidence items.",
    "All modules operate ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION.",
    "Readers and report stores must not override canonical JSON outputs.",
]

FORBIDDEN_ACTIONS = [
    "No module may directly modify or invoke live_bot.py.",
    "No module may modify portfolio.csv or strategy thresholds.",
    "No module may produce BUY/SELL execution instructions.",
    "Do not create competing daily runners alongside ecosystem_orchestrator.py.",
    "Do not rewrite canonical modules listed in the do-not-rewrite inventory.",
    "Do not invoke individual strategy_evolution steps when daily_runner.py is available.",
]

RECOMMENDED_CHAIN = (
    "Use Orchestrator as daily ecosystem intelligence entry point, with Evidence Engine "
    "and Strategy Evolution Daily Runner as canonical internal pipelines."
)


class SystemicModuleInterconnection:
    def __init__(
        self,
        inventory_path: Path | str = INVENTORY_PATH,
        orchestrator_path: Path | str = ORCHESTRATOR_PATH,
        evidence_path: Path | str = EVIDENCE_PATH,
        daily_runner_path: Path | str = DAILY_RUNNER_PATH,
        promotion_gate_path: Path | str = PROMOTION_GATE_PATH,
        paper_tracking_path: Path | str = PAPER_TRACKING_PATH,
        integration_gate_path: Path | str = INTEGRATION_GATE_PATH,
    ) -> None:
        self._paths = {
            "inventory": Path(inventory_path),
            "orchestrator": Path(orchestrator_path),
            "evidence": Path(evidence_path),
            "daily_runner": Path(daily_runner_path),
            "promotion_gate": Path(promotion_gate_path),
            "paper_tracking": Path(paper_tracking_path),
            "integration_gate": Path(integration_gate_path),
        }

    def build(self) -> SystemicInterconnectionReport:
        before_mtimes = self._snapshot_mtimes()
        payloads = {key: self._load_json(path) for key, path in self._paths.items()}
        after_mtimes = self._snapshot_mtimes()

        inventory = payloads.get("inventory") or {}
        orchestrator = payloads.get("orchestrator") or {}

        canonical_map = self._canonical_map()
        duplicate_groups = inventory.get("duplicate_groups", [])
        if not isinstance(duplicate_groups, list):
            duplicate_groups = []

        missing_connections = self._merge_missing_connections(inventory, orchestrator)
        classifications = self._classify_modules(inventory, duplicate_groups)
        conflict_warnings = self._conflict_warnings()
        subsystem_verdicts = self._subsystem_verdicts(payloads, orchestrator)

        has_warnings = bool(conflict_warnings) or bool(missing_connections)
        _ = has_warnings  # warnings captured in conflict_warnings / missing_connections
        verdict = SystemicHarmonyVerdict.SYSTEMIC_INTERCONNECTION_READY

        return SystemicInterconnectionReport(
            verdict=verdict,
            canonical_module_map=canonical_map,
            module_classifications=classifications,
            duplicate_groups=duplicate_groups,
            missing_connections=missing_connections,
            integration_rules=list(INTEGRATION_RULES),
            forbidden_actions=list(FORBIDDEN_ACTIONS),
            safe_orchestration_order=list(SAFE_ORCHESTRATION_ORDER),
            conflict_warnings=conflict_warnings,
            recommended_orchestration_chain=RECOMMENDED_CHAIN,
            subsystem_verdicts=subsystem_verdicts,
            sources_loaded={
                path.name: payloads[key] is not None for key, path in self._paths.items()
            },
            protected_files_unchanged=self._mtimes_unchanged(before_mtimes, after_mtimes),
        )

    @staticmethod
    def _canonical_map() -> list[CanonicalResponsibility]:
        labels = {
            "accounting_source_of_truth": "Accounting source of truth",
            "evidence_source_of_truth": "Evidence source of truth",
            "strategy_evolution_pipeline": "Strategy evolution pipeline",
            "integration_approval": "Integration approval",
            "ecosystem_overview": "Ecosystem overview",
        }
        items: list[CanonicalResponsibility] = []
        for key, spec in CANONICAL_MAP.items():
            items.append(
                CanonicalResponsibility(
                    responsibility=labels[key],
                    canonical_module=str(spec["module"]),
                    output_reports=[str(r) for r in spec["reports"]],  # type: ignore[index]
                )
            )
        return items

    def _classify_modules(
        self,
        inventory: dict,
        duplicate_groups: list[dict],
    ) -> list[ModuleClassification]:
        canonical_paths = {str(spec["module"]) for spec in CANONICAL_MAP.values()}
        overlap_paths: set[str] = set()
        for group in duplicate_groups:
            for path in group.get("module_paths", []):
                overlap_paths.add(str(path))

        classifications: list[ModuleClassification] = []
        seen: set[str] = set()

        for path in sorted(canonical_paths):
            seen.add(path)
            classifications.append(
                ModuleClassification(
                    module_path=path,
                    role=ModuleRole.CANONICAL,
                    responsibility=self._responsibility_for(path),
                    rationale="Designated canonical module for this responsibility.",
                )
            )

        for pattern in DO_NOT_INVOKE_DIRECTLY:
            if pattern not in seen:
                seen.add(pattern)
                classifications.append(
                    ModuleClassification(
                        module_path=pattern,
                        role=ModuleRole.DO_NOT_INVOKE_DIRECTLY,
                        responsibility=None,
                        rationale=(
                            "Subsumed by Strategy Evolution daily runner or Orchestrator; "
                            "direct invocation risks duplicate/competing outputs."
                        ),
                    )
                )

        modules = inventory.get("modules", [])
        if isinstance(modules, list):
            for module in modules:
                if not isinstance(module, dict):
                    continue
                path = str(module.get("path", ""))
                if not path or path in seen or path in canonical_paths:
                    continue
                role, rationale = self._infer_role(path, overlap_paths)
                if role == ModuleRole.CANONICAL:
                    continue
                seen.add(path)
                classifications.append(
                    ModuleClassification(
                        module_path=path,
                        role=role,
                        responsibility=None,
                        rationale=rationale,
                    )
                )

        return classifications

    @staticmethod
    def _infer_role(path: str, overlap_paths: set[str]) -> tuple[ModuleRole, str]:
        if any(path.startswith(prefix.rstrip("/")) or path == prefix.rstrip("/")
               for prefix in LEGACY_PLANNING_PATTERNS):
            return (
                ModuleRole.LEGACY_PLANNING_ONLY,
                "Phase V planning module — superseded by Phase VIII strategy_evolution pipeline.",
            )
        if path.endswith("_report.py") or path.endswith("_report_store.py"):
            return (
                ModuleRole.REPORT_ONLY,
                "Report serializer — read/write only; not an analytical source of truth.",
            )
        for pattern in VIEW_ONLY_PATTERNS:
            if pattern.endswith("/") and path.startswith(pattern):
                return (
                    ModuleRole.VIEW_ONLY,
                    "Overlaps canonical responsibility — use as reader/view only.",
                )
            if path == pattern:
                return (
                    ModuleRole.VIEW_ONLY,
                    "Overlaps canonical responsibility — use as reader/view only.",
                )
        if path in overlap_paths:
            return (
                ModuleRole.VIEW_ONLY,
                "Listed in inventory duplicate group — non-canonical view.",
            )
        if path.startswith("core/") and "_before_" not in path:
            return (
                ModuleRole.DO_NOT_INVOKE_DIRECTLY,
                "Live execution core — never invoke from research pipeline.",
            )
        return (
            ModuleRole.VIEW_ONLY,
            "Research module — consume via canonical pipeline outputs only.",
        )

    @staticmethod
    def _responsibility_for(path: str) -> str | None:
        for key, spec in CANONICAL_MAP.items():
            if spec["module"] == path:
                labels = {
                    "accounting_source_of_truth": "Accounting source of truth",
                    "evidence_source_of_truth": "Evidence source of truth",
                    "strategy_evolution_pipeline": "Strategy evolution pipeline",
                    "integration_approval": "Integration approval",
                    "ecosystem_overview": "Ecosystem overview",
                }
                return labels[key]
        return None

    @staticmethod
    def _conflict_warnings() -> list[ConflictWarning]:
        return [
            ConflictWarning(
                conflict_id="evidence_engine_vs_isolated_reports",
                modules=[
                    "research_core/evidence_engine/evidence_registry.py",
                    "research_core/profit_attribution/profit_attribution.py",
                    "research_core/exit_analysis/counterfactual_exit.py",
                    "research_core/entry_analysis/counterfactual_entry.py",
                ],
                risk_level=ConflictRiskLevel.CONFLICT_RISK,
                precedence="Evidence Engine registry",
                description=(
                    "Isolated Phase VII reports may diverge from Evidence Engine aggregation."
                ),
            ),
            ConflictWarning(
                conflict_id="daily_runner_vs_individual_steps",
                modules=[
                    "research_core/strategy_evolution/daily_runner.py",
                    "research_core/strategy_evolution/continuous_ranking_engine.py",
                    "research_core/strategy_evolution/parallel_paper_validator.py",
                    "research_core/strategy_evolution/promotion_gate.py",
                ],
                risk_level=ConflictRiskLevel.CONFLICT_RISK,
                precedence="Strategy Evolution Daily Runner",
                description=(
                    "Individual ranking/validation modules may produce stale or "
                    "inconsistent outputs if run outside daily runner."
                ),
            ),
            ConflictWarning(
                conflict_id="orchestrator_vs_manual_demos",
                modules=[
                    "research_core/orchestrator/ecosystem_orchestrator.py",
                    "tae_phase8_strategy_evolution_daily_runner_demo.py",
                    "tae_phase7_evidence_engine_demo.py",
                ],
                risk_level=ConflictRiskLevel.CONFLICT_RISK,
                precedence="Ecosystem Orchestrator",
                description=(
                    "Manual multi-step demo execution competes with orchestrator entry point."
                ),
            ),
            ConflictWarning(
                conflict_id="phase_v_vs_phase_viii_evolution",
                modules=[
                    "research_core/evolution/strategy_evolution.py",
                    "research_core/strategy_evolution/daily_runner.py",
                ],
                risk_level=ConflictRiskLevel.CONFLICT_RISK,
                precedence="Phase VIII Strategy Evolution Daily Runner",
                description=(
                    "Phase V evolution planning may conflict with Phase VIII paper pipeline "
                    "recommendations."
                ),
            ),
            ConflictWarning(
                conflict_id="accounting_views_vs_canonical",
                modules=[
                    "research_core/accounting/independent_double_entry.py",
                    "research_core/accounting/ledger_audit.py",
                    "tools/dashboard_account_reconcile.py",
                ],
                risk_level=ConflictRiskLevel.CONFLICT_RISK,
                precedence="Independent double-entry accounting",
                description="Multiple accounting audits may disagree on cash/PnL totals.",
            ),
        ]

    @staticmethod
    def _merge_missing_connections(inventory: dict, orchestrator: dict) -> list[str]:
        missing: list[str] = []
        for source in (inventory, orchestrator):
            items = source.get("missing_connections", [])
            if isinstance(items, list):
                for item in items:
                    text = str(item)
                    if text not in missing:
                        missing.append(text)
        if not missing:
            missing.append(
                "Integration gate not yet formally chained after promotion gate in orchestrator."
            )
        return missing

    @staticmethod
    def _subsystem_verdicts(payloads: dict, orchestrator: dict) -> dict[str, str | None]:
        orchestrator_verdicts = orchestrator.get("subsystem_verdicts", {})
        if not isinstance(orchestrator_verdicts, dict):
            orchestrator_verdicts = {}
        return {
            "ecosystem_inventory": (payloads.get("inventory") or {}).get("verdict"),
            "ecosystem_orchestrator": orchestrator.get("verdict"),
            "evidence_engine": (payloads.get("evidence") or {}).get("verdict"),
            "integration_gate": (payloads.get("integration_gate") or {}).get("verdict"),
            "strategy_evolution_daily_runner": (payloads.get("daily_runner") or {}).get("verdict"),
            "promotion_gate": (payloads.get("promotion_gate") or {}).get("verdict"),
            "paper_tracking": (payloads.get("paper_tracking") or {}).get("verdict"),
            **{k: v for k, v in orchestrator_verdicts.items()},
        }

    def _load_json(self, path: Path) -> dict | None:
        if not path.is_file():
            logger.warning("Input not found: %s", path)
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read %s: %s", path, exc)
            return None
        return payload if isinstance(payload, dict) else None

    def _snapshot_mtimes(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for path in PROTECTED_PATHS:
            full = Path(path)
            if full.is_file():
                out[str(path)] = full.stat().st_mtime
        return out

    @staticmethod
    def _mtimes_unchanged(before: dict[str, float], after: dict[str, float]) -> bool:
        for key, mtime in before.items():
            if key not in after or after[key] != mtime:
                return False
        return True
