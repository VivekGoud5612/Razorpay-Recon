from __future__ import annotations

from dataclasses import dataclass

from recon.domain.graph.edge import GraphEdge
from recon.domain.graph.node import GraphNode


@dataclass(slots=True)
class ReconciliationGraph:
    nodes: dict[str, GraphNode]
    edges: dict[str, GraphEdge]
    affected_node_ids: set[str]