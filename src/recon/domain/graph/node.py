from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class GraphNode:
    node_id: str
    source: str
    entity_type: str
    entity_id: str