from __future__ import annotations

from recon.application.investigation.dto.evidence import EvidencePackage
from recon.application.investigation.services.graph_traversal import GraphTraversalService
from recon.domain.graph.graph import ReconciliationGraph
from recon.domain.reconciliation.evidence import EvidenceRef    
from recon.domain.reconciliation.finding import ReconciliationFinding

class EvidenceBuilder:

    def __init__(self, graph: ReconciliationGraph) -> None:
        self._graph = graph
        self._traversal = GraphTraversalService(graph)

    def build(
        self,
        findings: list[ReconciliationFinding],
        depth: int = 2,
    ) -> EvidencePackage:
        evidence = self._extract_evidence(findings)
        node_ids = self._resolve_nodes(evidence)
        nodes, edges = self._traversal.get_subgraph(node_ids, depth)

        return EvidencePackage(
            findings=findings,
            evidence=evidence,
            records=[],
            nodes=nodes,
            edges=edges,
        )

    @staticmethod
    def _extract_evidence(
        findings: list[ReconciliationFinding],
    ) -> list[EvidenceRef]:
        evidence: list[EvidenceRef] = []
        seen: set[tuple[str, str, str, str, str | None]] = set()

        for finding in findings:
            for item in finding.evidence:
                key = (
                    item.source,
                    item.entity_type,
                    item.entity_id,
                    item.reason,
                    item.object_key,
                )

                if key in seen:
                    continue

                seen.add(key)
                evidence.append(item)

        return evidence

    def _resolve_nodes(
        self,
        evidence: list[EvidenceRef],
    ) -> set[str]:
        node_ids: set[str] = set()

        for item in evidence:
            node_id = f"{item.source}:{item.entity_type}:{item.entity_id}"

            if node_id in self._graph.nodes:
                node_ids.add(node_id)

        return node_ids