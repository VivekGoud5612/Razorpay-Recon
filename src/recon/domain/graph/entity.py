from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EntityReference:
    source: str
    entity_type: str
    entity_id: str