"""
Strategy Dependency Map — Phase IX Sprint IX.2C

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from research_core.strategy_evolution.pipeline_integration import (
    CANONICAL_PIPELINE_MODULE,
    CANONICAL_REPORT_PATH,
)
from research_core.strategy_evolution.daily_runner_report import SCHEMA_NAME as CANONICAL_SCHEMA
from research_core.strategy_evolution.candidate_report import SAFETY_BANNER

MAP_JSON = Path("tae_strategy_dependency_map.json")
MAP_TXT = Path("tae_strategy_dependency_map.txt")

CANONICAL_RUNNER_PATH = CANONICAL_PIPELINE_MODULE

INTEGRATION_TARGETS = [
    "research_core/strategy_evolution/candidate_registry.py",
    "research_core/strategy_evolution/parallel_paper_validator.py",
    "research_core/strategy_evolution/continuous_ranking_engine.py",
    "research_core/strategy_evolution/promotion_gate.py",
    "research_core/strategy_evolution/paper_tracking_log.py",
    "research_core/simulation_lab/strategy_simulation_lab.py",
    "research_core/regional_validation/regional_gap_closure.py",
    "research_core/regional_validation/regional_validation_report.py",
    "research_core/evolution/strategy_evolution.py",
]

RUNNER_CLASS_NAME = "StrategyEvolutionDailyRunner"

EXCLUDE_FROM_RUNNER_SCAN = {
    "research_core/strategy_evolution/strategy_dependency_map.py",
    "research_core/strategy_evolution/strategy_integration_report.py",
}

STRATEGY_MODULE_PATTERNS = [
    r"research_core/strategy_evolution/",
    r"research_core/simulation_lab/",
    r"research_core/regional_validation/",
    r"research_core/evolution/strategy_evolution",
]

COMPETING_DEMOS = [
    "tae_phase8_candidate_strategy_registry_demo.py",
    "tae_phase8_parallel_paper_validator_demo.py",
    "tae_phase8_continuous_ranking_engine_demo.py",
    "tae_phase8_strategy_promotion_gate_demo.py",
    "tae_phase8_paper_tracking_log_demo.py",
    "tae_phase5_strategy_evolution_demo.py",
]


class ModuleRole(str, Enum):
    CANONICAL_RUNNER = "CANONICAL_RUNNER"
    PIPELINE_STEP = "PIPELINE_STEP"
    PIPELINE_STEP_REVIEW = "PIPELINE_STEP_REVIEW_ONLY"
    PIPELINE_STEP_PAPER = "PIPELINE_STEP_PAPER_ONLY"
    FEEDER_READER = "FEEDER_READER"
    VALIDATION_FEEDER = "VALIDATION_FEEDER"
    REPORT_SCHEMA = "REPORT_SCHEMA"
    LEGACY_PLANNING = "LEGACY_PLANNING_ONLY"
    INTEGRATION_META = "INTEGRATION_META"
    COMPETING_DEMO = "COMPETING_DEMO"


@dataclass
class StrategyModuleNode:
    module_path: str
    role: ModuleRole
    reads_canonical_json: bool
    imports_pipeline: bool
    defines_runner: bool
    pipeline_role: str | None
    tae_outputs: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_path": self.module_path,
            "role": self.role.value,
            "reads_canonical_json": self.reads_canonical_json,
            "imports_pipeline": self.imports_pipeline,
            "defines_runner": self.defines_runner,
            "pipeline_role": self.pipeline_role,
            "tae_outputs": list(self.tae_outputs),
        }


@dataclass
class StrategyDependencyMap:
    canonical_runner: str
    canonical_json: str
    canonical_schema: str
    runner_count: int
    integration_targets: list[str]
    nodes: list[StrategyModuleNode]
    edges: list[dict[str, str]]
    competing_demos: list[str]
    bypass_risks: list[str]
    verdict: str = "STRATEGY_DEPENDENCY_MAP_READY"
    safety_mode: str = SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "schema": "tae_strategy_dependency_map",
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "verdict": self.verdict,
            "canonical_runner": self.canonical_runner,
            "canonical_json": self.canonical_json,
            "canonical_schema": self.canonical_schema,
            "runner_count": self.runner_count,
            "integration_targets": list(self.integration_targets),
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": list(self.edges),
            "competing_demos": list(self.competing_demos),
            "bypass_risks": list(self.bypass_risks),
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE STRATEGY DEPENDENCY MAP — SPRINT IX.2C =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Generat: {self.generated_at.isoformat()}",
            f"Verdict: {self.verdict}",
            "",
            f"Canonical runner: {self.canonical_runner}",
            f"Canonical JSON:   {self.canonical_json}",
            f"Runner count:     {self.runner_count} (must be 1)",
            "",
            "===== INTEGRATION TARGETS =====",
        ]
        for target in self.integration_targets:
            node = next((n for n in self.nodes if n.module_path == target), None)
            if node:
                lines.append(
                    f"  {target} [{node.role.value}] role={node.pipeline_role}"
                )
        lines.extend(["", "===== COMPETING DEMOS (not official entry) ====="])
        for demo in self.competing_demos:
            lines.append(f"  {demo}")
        lines.extend(["", "===== BYPASS RISKS ====="])
        for risk in self.bypass_risks:
            lines.append(f"  • {risk}")
        lines.append("")
        return "\n".join(lines)


class StrategyDependencyMapBuilder:
    ROOT = Path(".")

    ROLE_BY_PATH: dict[str, ModuleRole] = {
        CANONICAL_RUNNER_PATH: ModuleRole.CANONICAL_RUNNER,
        "research_core/strategy_evolution/candidate_registry.py": ModuleRole.PIPELINE_STEP,
        "research_core/strategy_evolution/parallel_paper_validator.py": ModuleRole.PIPELINE_STEP,
        "research_core/strategy_evolution/continuous_ranking_engine.py": ModuleRole.PIPELINE_STEP,
        "research_core/strategy_evolution/promotion_gate.py": ModuleRole.PIPELINE_STEP_REVIEW,
        "research_core/strategy_evolution/paper_tracking_log.py": ModuleRole.PIPELINE_STEP_PAPER,
        "research_core/simulation_lab/strategy_simulation_lab.py": ModuleRole.FEEDER_READER,
        "research_core/regional_validation/regional_gap_closure.py": ModuleRole.VALIDATION_FEEDER,
        "research_core/regional_validation/regional_validation_report.py": ModuleRole.REPORT_SCHEMA,
        "research_core/evolution/strategy_evolution.py": ModuleRole.LEGACY_PLANNING,
        "research_core/strategy_evolution/strategy_dependency_map.py": ModuleRole.INTEGRATION_META,
        "research_core/strategy_evolution/strategy_integration_report.py": ModuleRole.INTEGRATION_META,
    }

    PIPELINE_ROLE_BY_PATH: dict[str, str] = {
        "research_core/strategy_evolution/candidate_registry.py": "PIPELINE_STEP_REGISTRY",
        "research_core/strategy_evolution/parallel_paper_validator.py": "PIPELINE_STEP_VALIDATOR",
        "research_core/strategy_evolution/continuous_ranking_engine.py": "PIPELINE_STEP_RANKING",
        "research_core/strategy_evolution/promotion_gate.py": "PIPELINE_STEP_PROMOTION_REVIEW_ONLY",
        "research_core/strategy_evolution/paper_tracking_log.py": "PIPELINE_STEP_PAPER_TRACKING",
        "research_core/simulation_lab/strategy_simulation_lab.py": "FEEDER_READER",
        "research_core/regional_validation/regional_gap_closure.py": "VALIDATION_FEEDER",
        "research_core/evolution/strategy_evolution.py": "LEGACY_PLANNING_ONLY",
    }

    def build(self) -> StrategyDependencyMap:
        paths = self._discover_modules()
        path_to_text = {
            p: (self.ROOT / p).read_text(encoding="utf-8", errors="replace") for p in paths
        }
        edges = self._build_edges(paths, path_to_text)
        runner_count = sum(
            1 for p in paths if self._defines_runner(path_to_text[p], p)
        )
        nodes: list[StrategyModuleNode] = []
        bypass_risks: list[str] = []

        for path in sorted(paths):
            text = path_to_text[path]
            role = self.ROLE_BY_PATH.get(path, self._infer_role(path, text))
            reads = self._reads_canonical(text)
            imports_pipe = self._imports_pipeline(text)
            defines = self._defines_runner(text, path)
            pipe_role = self.PIPELINE_ROLE_BY_PATH.get(path) or self._extract_pipeline_role(text)

            if path in INTEGRATION_TARGETS and not reads and path not in (
                "research_core/regional_validation/regional_validation_report.py",
                "research_core/evolution/strategy_evolution.py",
            ):
                bypass_risks.append(f"{path} not reading canonical daily runner JSON")

            nodes.append(
                StrategyModuleNode(
                    module_path=path,
                    role=role,
                    reads_canonical_json=reads,
                    imports_pipeline=imports_pipe,
                    defines_runner=defines,
                    pipeline_role=pipe_role,
                    tae_outputs=sorted(self._tae_outputs(text)),
                )
            )

        competing = self._find_competing_demos()

        return StrategyDependencyMap(
            canonical_runner=CANONICAL_RUNNER_PATH,
            canonical_json=str(CANONICAL_REPORT_PATH),
            canonical_schema=CANONICAL_SCHEMA,
            runner_count=runner_count,
            integration_targets=list(INTEGRATION_TARGETS),
            nodes=nodes,
            edges=edges,
            competing_demos=competing,
            bypass_risks=bypass_risks,
        )

    def _discover_modules(self) -> list[str]:
        found: set[str] = set(INTEGRATION_TARGETS)
        found.add(CANONICAL_RUNNER_PATH)
        found.add("research_core/strategy_evolution/daily_runner.py")
        found.add("research_core/strategy_evolution/pipeline_integration.py")
        for py in self.ROOT.rglob("*.py"):
            rel = py.relative_to(self.ROOT).as_posix()
            if "__pycache__" in rel:
                continue
            if any(re.search(pat, rel) for pat in STRATEGY_MODULE_PATTERNS):
                found.add(rel)
        for demo in COMPETING_DEMOS:
            if (self.ROOT / demo).is_file():
                found.add(demo)
        return sorted(found)

    def _find_competing_demos(self) -> list[str]:
        return sorted(d for d in COMPETING_DEMOS if (self.ROOT / d).is_file())

    def _build_edges(
        self,
        paths: list[str],
        path_to_text: dict[str, str],
    ) -> list[dict[str, str]]:
        path_set = set(paths)
        index: dict[str, str] = {}
        for path in paths:
            parts = path.replace(".py", "").split("/")
            index[".".join(parts)] = path
            if parts[-1] != "__init__":
                index[parts[-1]] = path

        edges: list[dict[str, str]] = []
        for source, text in path_to_text.items():
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        target = self._resolve(alias.name, index, path_set)
                        if target:
                            edges.append({"source": source, "target": target, "kind": "import"})
                elif isinstance(node, ast.ImportFrom) and node.module:
                    target = self._resolve(node.module, index, path_set)
                    if target:
                        edges.append({"source": source, "target": target, "kind": "from"})
        return edges

    @staticmethod
    def _resolve(module: str, index: dict[str, str], path_set: set[str]) -> str | None:
        for cand in (module, module.split(".")[0]):
            if cand in index and index[cand] in path_set:
                return index[cand]
        parts = module.split(".")
        for i in range(len(parts), 0, -1):
            sub = ".".join(parts[:i])
            if sub in index and index[sub] in path_set:
                return index[sub]
        return None

    @staticmethod
    def _reads_canonical(text: str) -> bool:
        return (
            "load_canonical_daily_runner_report" in text
            or "pipeline_reference" in text
            or "tae_strategy_evolution_daily_runner.json" in text
            or "CANONICAL_REPORT_PATH" in text
            or "CANONICAL_PIPELINE" in text
            or "CANONICAL_PIPELINE_MODULE" in text
        )

    @staticmethod
    def _imports_pipeline(text: str) -> bool:
        return (
            "pipeline_integration" in text
            or "StrategyEvolutionDailyRunner" in text
            or "from research_core.strategy_evolution.daily_runner import" in text
        )

    @staticmethod
    def _defines_runner(text: str, path: str) -> bool:
        if path in EXCLUDE_FROM_RUNNER_SCAN:
            return False
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return False
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == RUNNER_CLASS_NAME:
                return True
        return False

    @staticmethod
    def _extract_pipeline_role(text: str) -> str | None:
        match = re.search(r'PIPELINE_ROLE\s*=\s*["\']([^"\']+)["\']', text)
        return match.group(1) if match else None

    @staticmethod
    def _infer_role(path: str, text: str) -> ModuleRole:
        if path.startswith("tae_phase"):
            return ModuleRole.COMPETING_DEMO
        return ModuleRole.PIPELINE_STEP

    @staticmethod
    def _tae_outputs(text: str) -> set[str]:
        outputs: set[str] = set()
        for match in re.finditer(r'Path\(\s*["\'](tae_[^"\']+)["\']\s*\)', text):
            outputs.add(match.group(1))
        return outputs


class StrategyDependencyMapStore:
    def persist(self, report: StrategyDependencyMap) -> Path:
        MAP_JSON.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return MAP_JSON

    def persist_txt(self, report: StrategyDependencyMap) -> Path:
        MAP_TXT.write_text(report.format_text() + "\n", encoding="utf-8")
        return MAP_TXT
