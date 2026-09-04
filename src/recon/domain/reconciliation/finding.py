from __future__ import annotations

from dataclasses import dataclass

from recon.domain.graph.entity import EntityReference
from recon.domain.reconciliation.evidence import EvidenceRef


@dataclass(slots=True, frozen=True)
class ReconciliationFinding:
    finding_id: str
    code: str
    severity: str
    affected_entity: EntityReference
    message: str
    evidence: list[EvidenceRef]