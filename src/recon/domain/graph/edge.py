from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class GraphEdge:
    edge_id: str
    source_node_id: str
    target_node_id: str
    edge_type: str
    source: str
    confidence: float