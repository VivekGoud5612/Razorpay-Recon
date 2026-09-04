from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RelationRule:
    source_type: str
    target_type: str
    edge_type: str
    source_field: str
    target_field: str