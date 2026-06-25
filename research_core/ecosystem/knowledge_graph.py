"""Knowledge graph — relational memory of ecosystem entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class NodeType(str, Enum):
    ORGANISM = "organism"
    EVIDENCE_TYPE = "evidence_type"
    MARKET_REGIME = "market_regime"
    PATTERN = "pattern"
    DECISION_LEVEL = "decision_level"
    RISK_CONDITION = "risk_condition"


class EdgeType(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    DEPENDS_ON = "depends_on"
    OBSERVED_IN = "observed_in"
    VALIDATED_BY = "validated_by"
    WEAKENED_BY = "weakened_by"


@dataclass
class GraphNode:
    node_id: str
    node_type: NodeType
    label: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class GraphEdge:
    source_id: str
    target_id: str
    edge_type: EdgeType
    weight: float = 1.0
    explanation: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class KnowledgeGraph:
    """
    In-memory graph linking organisms, evidence, regimes, patterns, and decisions.
    Foundation for explainable relational cognition in later sprints.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: list[GraphEdge] = []
        self._adjacency: dict[str, list[GraphEdge]] = {}

    def add_node(
        self,
        node_id: str,
        node_type: NodeType | str,
        label: str,
        metadata: dict[str, Any] | None = None,
    ) -> GraphNode:
        ntype = NodeType(node_type) if isinstance(node_type, str) else node_type
        node = GraphNode(
            node_id=node_id,
            node_type=ntype,
            label=label,
            metadata=metadata or {},
        )
        self._nodes[node_id] = node
        self._adjacency.setdefault(node_id, [])
        return node

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType | str,
        weight: float = 1.0,
        explanation: str = "",
    ) -> GraphEdge | None:
        if source_id not in self._nodes or target_id not in self._nodes:
            return None
        etype = EdgeType(edge_type) if isinstance(edge_type, str) else edge_type
        edge = GraphEdge(
            source_id=source_id,
            target_id=target_id,
            edge_type=etype,
            weight=max(0.0, min(1.0, weight)),
            explanation=explanation,
        )
        self._edges.append(edge)
        self._adjacency.setdefault(source_id, []).append(edge)
        self._adjacency.setdefault(target_id, []).append(edge)
        return edge

    def neighbors(self, node_id: str, edge_type: EdgeType | str | None = None) -> list[str]:
        if node_id not in self._nodes:
            return []
        etype = EdgeType(edge_type) if isinstance(edge_type, str) and edge_type else edge_type
        result: list[str] = []
        for edge in self._adjacency.get(node_id, []):
            if etype is not None and edge.edge_type != etype:
                continue
            other = edge.target_id if edge.source_id == node_id else edge.source_id
            if other not in result:
                result.append(other)
        return result

    def explain_relationship(self, source_id: str, target_id: str) -> str:
        explanations: list[str] = []
        for edge in self._edges:
            if edge.source_id == source_id and edge.target_id == target_id:
                src = self._nodes[source_id].label
                tgt = self._nodes[target_id].label
                explanations.append(
                    f"{src} {edge.edge_type.value} {tgt} (weight={edge.weight:.2f}): {edge.explanation}"
                )
            if edge.source_id == target_id and edge.target_id == source_id:
                src = self._nodes[target_id].label
                tgt = self._nodes[source_id].label
                explanations.append(
                    f"{src} {edge.edge_type.value} {tgt} (weight={edge.weight:.2f}): {edge.explanation}"
                )
        if not explanations:
            return f"No direct relationship recorded between {source_id} and {target_id}."
        return " | ".join(explanations)

    def graph_statistics(self) -> dict[str, Any]:
        by_type: dict[str, int] = {}
        for node in self._nodes.values():
            by_type[node.node_type.value] = by_type.get(node.node_type.value, 0) + 1
        edge_counts: dict[str, int] = {}
        for edge in self._edges:
            edge_counts[edge.edge_type.value] = edge_counts.get(edge.edge_type.value, 0) + 1
        return {
            "node_count": len(self._nodes),
            "edge_count": len(self._edges),
            "nodes_by_type": by_type,
            "edges_by_type": edge_counts,
        }

    def get_node(self, node_id: str) -> GraphNode | None:
        return self._nodes.get(node_id)

    def all_nodes(self) -> list[GraphNode]:
        return list(self._nodes.values())
