from __future__ import annotations

from dataclasses import dataclass

from recon.domain.graph.entity import EntityReference


@dataclass(frozen=True, slots=True)
class EvidenceRef(EntityReference):
    evidence_id: str
    reason: str
    object_key: str | None = None