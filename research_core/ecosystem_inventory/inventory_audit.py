"""
Ecosystem Inventory & Duplication Audit — Phase VIII B7

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Read-only scan of research modules, duplicates, and consolidation opportunities.
"""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from research_core.ecosystem_inventory.inventory_report import (
    ConsolidationRecommendation,
    DuplicateGroup,
    EcosystemInventoryReport,
    InventoryVerdict,
    MaturityLevel,
    ModuleInventoryEntry,
    RecommendedAction,
)

logger = logging.getLogger(__name__)

ROOT = Path(".")
PROTECTED_PATHS = [
    Path("live_bot.py"),
    Path("dashboard_v2.py"),
    Path("config/settings.py"),
    Path("portfolio.csv"),
    Path("core/trades.py"),
    Path("core/portfolio_prices.py"),
]

AUDIT_ROOTS = [
    "core",
    "research_core",
    "integration_layer",
    "tools",
]

AUDIT_SUBPACKAGES = [
    "research_core/strategy_evolution",
    "research_core/evidence_engine",
    "research_core/accounting",
    "research_core/entry_analysis",
    "research_core/exit_analysis",
    "research_core/profit_attribution",
    "research_core/score_decomposition",
    "research_core/statistical_validation",
    "research_core/simulation_lab",
    "research_core/legacy_freeze",
    "research_core/regional_validation",
    "research_core/performance",
    "research_core/evolution",
    "research_core/validation",
    "research_core/governance",
    "research_core/recalibration",
    "research_core/evidence_gap",
    "research_core/evidence_history",
    "research_core/integration",
    "research_core/review",
    "research_core/discovery",
    "research_core/hypothesis",
    "research_core/autonomy",
    "research_core/learning",
    "research_core/ecosystem",
]

DUPLICATE_THEMES: dict[str, dict[str, object]] = {
    "accounting_audit": {
        "theme": "Accounting / ledger verification",
        "patterns": [
            r"accounting/",
            r"ledger_audit",
            r"independent_double_entry",
            r"accounting_integrity",
            r"dashboard_account_reconcile",
        ],
        "recommendation": "Keep independent_double_entry as source of truth; treat others as views.",
    },
    "reconciliation_tools": {
        "theme": "Dashboard reconciliation utilities",
        "patterns": [
            r"reconcile",
            r"recompute_realized_pnl",
            r"refresh_latest_portfolio",
        ],
        "recommendation": "Consolidate dashboard reconcile scripts under one tools runner.",
    },
    "evidence_reporting": {
        "theme": "Evidence aggregation and reporting",
        "patterns": [
            r"evidence_engine/",
            r"evidence_accumulator",
            r"evidence_gap",
            r"evidence_history/",
        ],
        "recommendation": "Evidence Engine is canonical; wire accumulator/gap as readers only.",
    },
    "simulation_ranking_validation": {
        "theme": "Simulation, ranking, and validation",
        "patterns": [
            r"simulation_lab/",
            r"strategy_evolution/",
            r"cross_regime_validator",
            r"regional_validation/",
        ],
        "recommendation": "Strategy Evolution daily runner is the active pipeline; avoid parallel rankers.",
    },
    "strategy_evolution_generations": {
        "theme": "Strategy evolution (Phase V vs Phase VIII)",
        "patterns": [
            r"research_core/evolution/",
            r"research_core/strategy_evolution/",
        ],
        "recommendation": "Phase VIII strategy_evolution is active; Phase V evolution is planning-only legacy.",
    },
    "closed_freeze_analysis": {
        "theme": "CLOSED_FREEZE root cause and statistical audit",
        "patterns": [
            r"legacy_freeze/",
            r"closed_freeze",
            r"statistical_validation/",
        ],
        "recommendation": "Keep statistical audit + root cause; legacy_freeze report is archive reference.",
    },
    "performance_audit": {
        "theme": "Performance and strategic audit",
        "patterns": [
            r"performance/",
            r"strategic_performance",
            r"dashboard_performance_reconcile",
        ],
        "recommendation": "Connect performance auditor outputs into Evidence Engine, not live bot.",
    },
    "counterfactual_analysis": {
        "theme": "Entry/exit counterfactual analysis",
        "patterns": [
            r"entry_analysis/",
            r"exit_analysis/",
            r"counterfactual",
        ],
        "recommendation": "Keep both; register findings via Evidence Engine only.",
    },
}

DO_NOT_REWRITE_PATHS = [
    "live_bot.py",
    "dashboard_v2.py",
    "config/settings.py",
    "portfolio.csv",
    "core/trades.py",
    "core/portfolio_prices.py",
    "core/portfolio.py",
    "core/entry_filter.py",
    "core/exit_intelligence.py",
    "core/risk.py",
    "core/allocation.py",
    "research_core/strategy_evolution/daily_runner.py",
    "research_core/evidence_engine/evidence_registry.py",
    "research_core/accounting/independent_double_entry.py",
    "integration_layer/evidence_gate.py",
]

PIPELINE_MODULES = {
    "research_core/strategy_evolution/candidate_registry.py",
    "research_core/strategy_evolution/parallel_paper_validator.py",
    "research_core/strategy_evolution/continuous_ranking_engine.py",
    "research_core/strategy_evolution/promotion_gate.py",
    "research_core/strategy_evolution/paper_tracking_log.py",
    "research_core/strategy_evolution/daily_runner.py",
}

EVIDENCE_SOURCES = {
    "research_core/accounting/independent_double_entry.py",
    "research_core/exit_analysis/counterfactual_exit.py",
    "research_core/entry_analysis/counterfactual_entry.py",
    "research_core/profit_attribution/profit_attribution.py",
    "research_core/score_decomposition/score_decomposition_analyzer.py",
    "research_core/statistical_validation/closed_freeze_statistical_audit.py",
    "research_core/simulation_lab/strategy_simulation_lab.py",
}


@dataclass
class _ScanResult:
    path: Path
    module_name: str
    purpose: str
    inputs: list[str]
    outputs: list[str]
    related_reports: list[str]


class EcosystemInventoryAudit:
    def __init__(self, root: Path | str = ROOT) -> None:
        self._root = Path(root)

    def audit(self) -> EcosystemInventoryReport:
        before_mtimes = self._snapshot_mtimes()
        scan_results = self._scan_modules()
        modules = [self._classify(result) for result in scan_results]
        duplicate_groups = self._detect_duplicate_groups(modules)
        self._apply_overlap_metadata(modules, duplicate_groups)
        consolidation = self._top_consolidation_recommendations(duplicate_groups)
        missing_connections = self._missing_connections(modules)
        after_mtimes = self._snapshot_mtimes()

        active = sum(1 for m in modules if m.is_active)
        legacy = sum(1 for m in modules if m.is_legacy)

        return EcosystemInventoryReport(
            verdict=InventoryVerdict.ECOSYSTEM_INVENTORY_AUDIT_READY,
            modules=sorted(modules, key=lambda m: m.path),
            total_modules_scanned=len(modules),
            active_modules=active,
            legacy_modules=legacy,
            duplicate_groups=duplicate_groups,
            top_consolidation_recommendations=consolidation,
            do_not_rewrite=list(DO_NOT_REWRITE_PATHS),
            next_best_implementation=self._next_best_implementation(modules, missing_connections),
            missing_connections=missing_connections,
            protected_files_unchanged=self._mtimes_unchanged(before_mtimes, after_mtimes),
        )

    def _scan_modules(self) -> list[_ScanResult]:
        paths: set[Path] = set()
        for rel_root in AUDIT_ROOTS:
            root_path = self._root / rel_root
            if root_path.is_dir():
                for py_file in root_path.rglob("*.py"):
                    if "__pycache__" not in py_file.parts:
                        paths.add(py_file)
        for rel_pkg in AUDIT_SUBPACKAGES:
            pkg_path = self._root / rel_pkg
            if pkg_path.is_dir():
                for py_file in pkg_path.rglob("*.py"):
                    if "__pycache__" not in py_file.parts:
                        paths.add(py_file)

        dashboard_tools = [
            self._root / "tools/dashboard_performance_reconcile.py",
            self._root / "tools/dashboard_account_reconcile.py",
        ]
        for tool in dashboard_tools:
            if tool.is_file():
                paths.add(tool)

        return [self._scan_file(path) for path in sorted(paths)]

    def _scan_file(self, path: Path) -> _ScanResult:
        rel_path = path.relative_to(self._root).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        purpose = self._extract_purpose(text, path.stem)
        inputs, outputs, reports = self._extract_io(text)
        return _ScanResult(
            path=path,
            module_name=path.stem,
            purpose=purpose,
            inputs=sorted(inputs),
            outputs=sorted(outputs),
            related_reports=sorted(reports),
        )

    @staticmethod
    def _extract_purpose(text: str, fallback: str) -> str:
        doc = ast.get_docstring(ast.parse(text)) or ""
        doc = " ".join(line.strip() for line in doc.splitlines() if line.strip())
        if doc:
            return doc[:240]
        return fallback.replace("_", " ")

    @staticmethod
    def _extract_io(text: str) -> tuple[set[str], set[str], set[str]]:
        inputs: set[str] = set()
        outputs: set[str] = set()
        reports: set[str] = set()

        for match in re.finditer(r'Path\(\s*["\']([^"\']+)["\']\s*\)', text):
            value = match.group(1)
            if value.endswith(".json") or value.endswith(".txt"):
                reports.add(value)
            elif value.endswith(".csv"):
                inputs.add(value)

        for match in re.finditer(r'["\'](tae_[^"\']+\.(?:json|txt))["\']', text):
            token = match.group(1)
            reports.add(token)

        for token in ("portfolio.csv", "live_bot.py", "config/settings.py"):
            if token in text:
                inputs.add(token)

        for report in reports:
            if "DEFAULT" in text or "persist" in text or "write_text" in text:
                outputs.add(report)

        if not outputs:
            outputs = {r for r in reports if "report" in r or "audit" in r or "validation" in r}

        return inputs, outputs, reports

    def _classify(self, result: _ScanResult) -> ModuleInventoryEntry:
        rel_path = result.path.relative_to(self._root).as_posix()
        maturity = self._infer_maturity(rel_path, result.module_name)
        action = self._infer_action(rel_path, maturity)
        is_legacy = maturity == MaturityLevel.LEGACY or "_before_" in rel_path
        is_active = self._infer_active(rel_path, maturity, is_legacy)
        research_only = not rel_path.startswith("core/") and rel_path != "live_bot.py"
        integration_ready = rel_path.startswith("integration_layer/") or rel_path in {
            "research_core/evidence_engine/evidence_registry.py",
            "integration_layer/evidence_gate.py",
        }

        return ModuleInventoryEntry(
            module_name=result.module_name,
            path=rel_path,
            purpose=result.purpose,
            maturity_level=maturity,
            inputs=result.inputs,
            outputs=result.outputs,
            related_reports=result.related_reports,
            possible_duplicates=[],
            overlaps_with=[],
            recommended_action=action,
            is_active=is_active,
            is_legacy=is_legacy,
            research_only=research_only,
            integration_ready=integration_ready,
        )

    @staticmethod
    def _infer_maturity(rel_path: str, module_name: str) -> MaturityLevel:
        if "_before_" in rel_path or rel_path.startswith("research_core/legacy_freeze/"):
            return MaturityLevel.LEGACY
        if rel_path.startswith("core/"):
            return MaturityLevel.L6_PRODUCTION_CANDIDATE
        if rel_path.startswith("integration_layer/"):
            return MaturityLevel.L5_INTEGRATION_READY
        if rel_path.startswith("research_core/strategy_evolution/"):
            if "daily_runner" in module_name:
                return MaturityLevel.L4_PAPER_TRACKING
            return MaturityLevel.L4_PAPER_TRACKING
        if any(
            rel_path.startswith(prefix)
            for prefix in (
                "research_core/evidence_engine/",
                "research_core/entry_analysis/",
                "research_core/exit_analysis/",
                "research_core/profit_attribution/",
                "research_core/score_decomposition/",
                "research_core/statistical_validation/",
                "research_core/simulation_lab/",
                "research_core/accounting/",
            )
        ):
            return MaturityLevel.L3_VALIDATED
        if rel_path.startswith("research_core/evolution/"):
            return MaturityLevel.L2_FUNCTIONAL
        if rel_path.startswith("tools/"):
            return MaturityLevel.L2_FUNCTIONAL
        if rel_path.endswith("_report.py") or rel_path.endswith("Report.py"):
            return MaturityLevel.L2_FUNCTIONAL
        if any(
            rel_path.startswith(prefix)
            for prefix in (
                "research_core/discovery/",
                "research_core/hypothesis/",
                "research_core/ecosystem/",
                "research_core/life/",
            )
        ):
            return MaturityLevel.L1_PROTOTYPE
        return MaturityLevel.L2_FUNCTIONAL

    @staticmethod
    def _infer_action(rel_path: str, maturity: MaturityLevel) -> RecommendedAction:
        if rel_path in DO_NOT_REWRITE_PATHS or rel_path.startswith("core/"):
            return RecommendedAction.DO_NOT_TOUCH
        if maturity == MaturityLevel.LEGACY or "_before_" in rel_path:
            return RecommendedAction.ARCHIVE_LATER
        if rel_path in PIPELINE_MODULES:
            return RecommendedAction.KEEP
        if rel_path in EVIDENCE_SOURCES:
            return RecommendedAction.KEEP
        if rel_path.startswith("research_core/evolution/"):
            return RecommendedAction.CONSOLIDATE
        if rel_path.startswith("research_core/strategy_evolution/"):
            return RecommendedAction.KEEP
        if rel_path.startswith("integration_layer/"):
            return RecommendedAction.KEEP
        if rel_path.startswith("tools/"):
            return RecommendedAction.CONSOLIDATE
        if rel_path.startswith("research_core/performance/"):
            return RecommendedAction.CONNECT_TO_PIPELINE
        if rel_path.startswith("research_core/evidence_gap/"):
            return RecommendedAction.CONNECT_TO_PIPELINE
        if rel_path.startswith("research_core/regional_validation/"):
            return RecommendedAction.NEEDS_VALIDATION
        if rel_path.startswith("research_core/recalibration/"):
            return RecommendedAction.NEEDS_VALIDATION
        if maturity in (MaturityLevel.L0_IDEA, MaturityLevel.L1_PROTOTYPE):
            return RecommendedAction.NEEDS_VALIDATION
        return RecommendedAction.KEEP

    @staticmethod
    def _infer_active(rel_path: str, maturity: MaturityLevel, is_legacy: bool) -> bool:
        if is_legacy:
            return False
        if rel_path.startswith("research_core/strategy_evolution/"):
            return True
        if rel_path.startswith("research_core/evidence_engine/"):
            return True
        if rel_path.startswith("integration_layer/"):
            return True
        if rel_path in EVIDENCE_SOURCES:
            return True
        if rel_path.startswith("core/") and "_before_" not in rel_path:
            return True
        if rel_path.startswith("research_core/evolution/"):
            return False
        if maturity in (MaturityLevel.L3_VALIDATED, MaturityLevel.L4_PAPER_TRACKING, MaturityLevel.L5_INTEGRATION_READY):
            return True
        return maturity == MaturityLevel.L2_FUNCTIONAL

    def _detect_duplicate_groups(
        self,
        modules: list[ModuleInventoryEntry],
    ) -> list[DuplicateGroup]:
        groups: list[DuplicateGroup] = []
        for group_id, spec in DUPLICATE_THEMES.items():
            patterns = spec["patterns"]
            matched = [
                module.path
                for module in modules
                if any(re.search(pat, module.path) for pat in patterns)
            ]
            if len(matched) >= 2:
                groups.append(
                    DuplicateGroup(
                        group_id=group_id,
                        theme=str(spec["theme"]),
                        module_paths=sorted(matched),
                        recommendation=str(spec["recommendation"]),
                    )
                )
        return groups

    @staticmethod
    def _apply_overlap_metadata(
        modules: list[ModuleInventoryEntry],
        duplicate_groups: list[DuplicateGroup],
    ) -> None:
        path_to_group: dict[str, list[str]] = {}
        for group in duplicate_groups:
            for path in group.module_paths:
                path_to_group.setdefault(path, []).append(group.group_id)

        for module in modules:
            overlaps = path_to_group.get(module.path, [])
            module.overlaps_with = [
                other
                for group in duplicate_groups
                if group.group_id in overlaps
                for other in group.module_paths
                if other != module.path
            ]
            module.possible_duplicates = sorted(set(module.overlaps_with))

    @staticmethod
    def _top_consolidation_recommendations(
        duplicate_groups: list[DuplicateGroup],
    ) -> list[ConsolidationRecommendation]:
        items: list[ConsolidationRecommendation] = []
        rank = 1
        for group in duplicate_groups:
            items.append(
                ConsolidationRecommendation(
                    rank=rank,
                    title=group.theme,
                    modules=group.module_paths,
                    rationale=group.recommendation,
                )
            )
            rank += 1

        extras = [
            ConsolidationRecommendation(
                rank=rank,
                title="Wire Phase VII analyzers into daily runner pre-step",
                modules=sorted(EVIDENCE_SOURCES),
                rationale=(
                    "Evidence Engine already aggregates these; add optional refresh step "
                    "before Strategy Evolution daily runner."
                ),
            ),
            ConsolidationRecommendation(
                rank=rank + 1,
                title="Unify Phase V evolution planning with Phase VIII paper pipeline",
                modules=[
                    "research_core/evolution/strategy_evolution.py",
                    "research_core/strategy_evolution/daily_runner.py",
                ],
                rationale=(
                    "Keep Phase VIII as operational pipeline; demote Phase V evolution "
                    "to human-review planning only."
                ),
            ),
            ConsolidationRecommendation(
                rank=rank + 2,
                title="Dashboard reconcile tools → read-only audit subcommand",
                modules=[
                    "tools/dashboard_account_reconcile.py",
                    "tools/dashboard_performance_reconcile.py",
                ],
                rationale="Expose as audit-only CLI; never mutate portfolio or live bot.",
            ),
        ]
        items.extend(extras)
        return items[:10]

    @staticmethod
    def _missing_connections(modules: list[ModuleInventoryEntry]) -> list[str]:
        module_paths = {m.path for m in modules}
        missing: list[str] = []

        checks = [
            (
                "research_core/evolution/strategy_evolution.py",
                "Phase VIII strategy_evolution daily runner",
                "Phase V evolution manager parallel to Phase VIII pipeline",
            ),
        ]
        for path, _target, message in checks:
            if path in module_paths:
                missing.append(message)

        if "research_core/evidence_gap/evidence_gap.py" in module_paths:
            from research_core.evidence_engine.evidence_gap_registration import (
                MISSING_CONNECTION_EVIDENCE_GAP_REGISTRY,
                is_evidence_gap_wired_in_registry,
            )

            if not is_evidence_gap_wired_in_registry():
                missing.append(MISSING_CONNECTION_EVIDENCE_GAP_REGISTRY)

        if "research_core/regional_validation/regional_gap_closure.py" in module_paths:
            from research_core.strategy_evolution.regional_validation_integration import (
                MISSING_CONNECTION_REGIONAL_PROMOTION_GATE,
                is_regional_validation_wired_in_promotion_gate,
            )

            if not is_regional_validation_wired_in_promotion_gate():
                missing.append(MISSING_CONNECTION_REGIONAL_PROMOTION_GATE)

        if "research_core/recalibration/confidence_recalibration.py" in module_paths:
            from research_core.evidence_engine.confidence_registration import (
                MISSING_CONNECTION_CONFIDENCE_EVIDENCE,
                is_confidence_wired_in_registry,
            )

            if not is_confidence_wired_in_registry():
                missing.append(MISSING_CONNECTION_CONFIDENCE_EVIDENCE)

        if "integration_layer/evidence_gate.py" in module_paths:
            from integration_layer.integration_gate_chain import (
                MISSING_CONNECTION_INTEGRATION_GATE_CHAIN,
                is_integration_gate_chained,
            )

            if not is_integration_gate_chained():
                missing.append(MISSING_CONNECTION_INTEGRATION_GATE_CHAIN)

        if "research_core/performance/strategic_performance_auditor.py" in module_paths:
            from research_core.performance.performance_pipeline_integration import (
                MISSING_CONNECTION_PERFORMANCE_DAILY_RUNNER,
                is_daily_runner_performance_wired,
            )

            if not is_daily_runner_performance_wired():
                missing.append(MISSING_CONNECTION_PERFORMANCE_DAILY_RUNNER)

        if "research_core/governance/daily_intelligence.py" in module_paths:
            missing.append(
                "Governance daily intelligence reads legacy JSON set; "
                "extend to Phase VIII strategy_evolution outputs"
            )
        return missing

    @staticmethod
    def _next_best_implementation(
        modules: list[ModuleInventoryEntry],
        missing_connections: list[str],
    ) -> str:
        pipeline_ready = all(
            any(m.path == path for m in modules) for path in PIPELINE_MODULES
        )
        if pipeline_ready and missing_connections:
            return (
                "Extend Strategy Evolution daily runner with an optional Evidence Engine "
                "refresh pre-step and post-promotion Integration Gate hook — reuse existing "
                "modules; do not rewrite live bot or core execution paths."
            )
        return (
            "Continue Phase VIII paper pipeline maturation: accumulate trades for "
            "SCORE_90_PLUS_NO_CLOSED_FREEZE and feed daily runner outputs into governance."
        )

    def _snapshot_mtimes(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for path in PROTECTED_PATHS:
            full = self._root / path
            if full.is_file():
                out[str(path)] = full.stat().st_mtime
        return out

    @staticmethod
    def _mtimes_unchanged(before: dict[str, float], after: dict[str, float]) -> bool:
        for key, mtime in before.items():
            if key not in after or after[key] != mtime:
                return False
        return True
