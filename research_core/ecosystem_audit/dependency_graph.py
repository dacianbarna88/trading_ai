"""
Real Module Dependency Graph — Phase IX Sprint IX.1

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Builds import edges via AST analysis across the TAE Python tree.
"""

from __future__ import annotations

import ast
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.ecosystem_audit.audit_constants import (
    CANONICAL_MODULES,
    EXCLUDE_DIR_NAMES,
    PRIMARY_RUNNERS,
    SCAN_FILES,
    SCAN_ROOTS,
)
from research_core.ecosystem_audit.master_inventory import MasterInventoryBuilder
from research_core.strategy_evolution.candidate_report import SAFETY_BANNER

logger = logging.getLogger(__name__)

GRAPH_JSON = Path("tae_dependency_graph.json")
GRAPH_TXT = Path("tae_dependency_graph.txt")


@dataclass
class DependencyEdge:
    source: str
    target: str
    import_kind: str

    def to_dict(self) -> dict[str, str]:
        return {
            "source": self.source,
            "target": self.target,
            "import_kind": self.import_kind,
        }


@dataclass
class DependencyGraphReport:
    nodes: list[str]
    edges: list[DependencyEdge]
    incoming_counts: dict[str, int]
    outgoing_counts: dict[str, int]
    canonical_subgraph: list[DependencyEdge]
    anchor_reachable: list[str]
    verdict: str = "DEPENDENCY_GRAPH_READY"
    safety_mode: str = SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "schema": "tae_dependency_graph",
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "verdict": self.verdict,
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "nodes": list(self.nodes),
            "edges": [e.to_dict() for e in self.edges],
            "incoming_counts": dict(self.incoming_counts),
            "outgoing_counts": dict(self.outgoing_counts),
            "canonical_subgraph": [e.to_dict() for e in self.canonical_subgraph],
            "anchor_reachable": list(self.anchor_reachable),
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE MODULE DEPENDENCY GRAPH — SPRINT IX.1 =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Generat: {self.generated_at.isoformat()}",
            f"Verdict: {self.verdict}",
            f"Nodes: {len(self.nodes)} | Edges: {len(self.edges)}",
            "",
            "===== CANONICAL SUBGRAPH (edges between canonical modules) =====",
        ]
        for edge in self.canonical_subgraph:
            lines.append(f"  {edge.source} → {edge.target} ({edge.import_kind})")
        lines.extend(["", "===== ANCHOR REACHABLE (from orchestrator + daily_runner) ====="])
        for path in self.anchor_reachable[:40]:
            lines.append(f"  {path}")
        if len(self.anchor_reachable) > 40:
            lines.append(f"  ... and {len(self.anchor_reachable) - 40} more")
        lines.extend(["", "===== TOP INCOMING (most referenced) ====="])
        top_in = sorted(self.incoming_counts.items(), key=lambda x: -x[1])[:20]
        for path, count in top_in:
            lines.append(f"  {count:3d} ← {path}")
        lines.append("")
        return "\n".join(lines)


class DependencyGraphBuilder:
    ANCHORS = [
        "research_core/orchestrator/ecosystem_orchestrator.py",
        "research_core/strategy_evolution/daily_runner.py",
        "tae_phase8_ecosystem_orchestrator_demo.py",
        "tae_phase9_runtime_foundation_demo.py",
    ]

    def __init__(self, root: Path | str = Path(".")) -> None:
        self._root = Path(root)
        self._module_map: dict[str, str] = {}
        self._package_dirs: set[str] = set()

    def build(self) -> DependencyGraphReport:
        self._index_modules()
        file_paths = sorted(set(self._module_map.values()))
        edges: list[DependencyEdge] = []
        for rel_path in file_paths:
            full = self._root / rel_path
            if not full.is_file():
                continue
            try:
                tree = ast.parse(full.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                continue
            for imp in self._extract_imports(tree):
                target = self._resolve_import(rel_path, imp)
                if target and target != rel_path:
                    edges.append(
                        DependencyEdge(
                            source=rel_path,
                            target=target,
                            import_kind=imp["kind"],
                        )
                    )

        nodes = sorted(set(file_paths))
        incoming: dict[str, int] = {n: 0 for n in nodes}
        outgoing: dict[str, int] = {n: 0 for n in nodes}
        for edge in edges:
            incoming[edge.target] = incoming.get(edge.target, 0) + 1
            outgoing[edge.source] = outgoing.get(edge.source, 0) + 1

        canonical_paths = set(CANONICAL_MODULES.values())
        canonical_subgraph = [
            e for e in edges if e.source in canonical_paths and e.target in canonical_paths
        ]
        anchor_reachable = sorted(self._reachable_from_anchors(edges))

        return DependencyGraphReport(
            nodes=nodes,
            edges=edges,
            incoming_counts=incoming,
            outgoing_counts=outgoing,
            canonical_subgraph=canonical_subgraph,
            anchor_reachable=anchor_reachable,
        )

    def connected_paths(self, report: DependencyGraphReport) -> set[str]:
        return set(report.anchor_reachable) | set(CANONICAL_MODULES.values()) | set(
            PRIMARY_RUNNERS
        )

    def _index_modules(self) -> None:
        self._module_map.clear()
        self._package_dirs.clear()
        inventory = MasterInventoryBuilder(self._root)
        for path in inventory._discover_python_files():
            rel = path.relative_to(self._root).as_posix()
            parts = rel.replace(".py", "").split("/")
            if path.stem == "__init__":
                module_name = ".".join(parts[:-1])
            else:
                module_name = ".".join(parts)
            self._module_map[module_name] = rel
            if path.stem != "__init__":
                existing = self._module_map.get(path.stem)
                if existing is None or existing == rel:
                    self._module_map[path.stem] = rel
            for i in range(len(parts) - (1 if path.stem == "__init__" else 0)):
                pkg = ".".join(parts[: i + 1])
                self._package_dirs.add(pkg)

    def _extract_imports(self, tree: ast.AST) -> list[dict[str, str]]:
        imports: list[dict[str, str]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({"module": alias.name, "kind": "import"})
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append({"module": node.module, "kind": "from"})
        return imports

    def _resolve_import(self, source_rel: str, imp: dict[str, str]) -> str | None:
        module = imp["module"]
        candidates = [module, module.split(".")[0]]
        for cand in candidates:
            if cand in self._module_map:
                return self._module_map[cand]
        parts = module.split(".")
        for i in range(len(parts), 0, -1):
            sub = ".".join(parts[:i])
            if sub in self._module_map:
                return self._module_map[sub]
        source_parts = source_rel.replace(".py", "").split("/")
        if imp["kind"] == "from" and len(source_parts) > 1:
            relative = ".".join(source_parts[:-1] + [parts[0]]) if parts else ""
            if relative.replace(".", "/") + ".py" in {
                v for v in self._module_map.values()
            }:
                return relative.replace(".", "/") + ".py"
        return None

    def _reachable_from_anchors(self, edges: list[DependencyEdge]) -> set[str]:
        adjacency: dict[str, set[str]] = {}
        for edge in edges:
            adjacency.setdefault(edge.source, set()).add(edge.target)
            adjacency.setdefault(edge.target, set()).add(edge.source)

        reachable: set[str] = set()
        queue = [a for a in self.ANCHORS if a in self._module_map.values()]
        reachable.update(queue)
        while queue:
            current = queue.pop()
            for neighbor in adjacency.get(current, set()):
                if neighbor not in reachable:
                    reachable.add(neighbor)
                    queue.append(neighbor)
        return reachable


class DependencyGraphStore:
    def persist(self, report: DependencyGraphReport) -> Path:
        GRAPH_JSON.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return GRAPH_JSON

    def persist_txt(self, report: DependencyGraphReport) -> Path:
        GRAPH_TXT.write_text(report.format_text() + "\n", encoding="utf-8")
        return GRAPH_TXT
