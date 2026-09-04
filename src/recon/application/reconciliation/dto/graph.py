from __future__ import annotations

from dataclasses import dataclass

from recon.domain.graph.edge import GraphEdge
from recon.domain.graph.node import GraphNode


@dataclass(slots=True, frozen=True, kw_only=True)
class GraphResponse:
    nodes: list[GraphNode]
    edges: list[GraphEdge]
