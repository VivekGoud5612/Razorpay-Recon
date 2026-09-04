from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from recon.domain.graph.edge import GraphEdge
from recon.domain.graph.node import GraphNode
from recon.domain.reconciliation.evidence import EvidenceRef
from recon.domain.reconciliation.finding import ReconciliationFinding


@dataclass(slots=True, frozen=True)
class EvidenceRecord:
    source: str
    entity_type: str
    entity_id: str
    data: dict[str, Any]


@dataclass(slots=True, frozen=True)
class EvidencePackage:
    findings: list[ReconciliationFinding]
    evidence: list[EvidenceRef]
    records: list[EvidenceRecord]
    nodes: list[GraphNode]
    edges: list[GraphEdge]