from __future__ import annotations

from recon.application.investigation.dto.evidence import EvidencePackage, EvidenceRecord
from recon.application.investigation.ports.repository import InvestigationRepository
from recon.application.investigation.services.graph_traversal import GraphTraversalService
from recon.domain.graph.graph import ReconciliationGraph
from recon.domain.reconciliation.evidence import EvidenceRef
from recon.domain.reconciliation.finding import ReconciliationFinding

class EvidenceBuilder:

    def __init__(
        self,
        graph: ReconciliationGraph,
        records: InvestigationRepository,
        settlement_id: str,
    ) -> None:
        self._graph = graph
        self._traversal = GraphTraversalService(graph)
        self._records = records
        self._settlement_id = settlement_id

    async def build(
        self,
        findings: list[ReconciliationFinding],
        depth: int = 2,
    ) -> EvidencePackage:
        evidence = self._extract_evidence(findings)
        node_ids = self._resolve_nodes(evidence)
        nodes, edges = self._traversal.get_subgraph(node_ids, depth)
        records = await self._fetch_records(evidence)

        return EvidencePackage(
            findings=findings,
            evidence=evidence,
            records=records,
            nodes=nodes,
            edges=edges,
        )

    async def _fetch_records(
        self,
        evidence: list[EvidenceRef],
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []
        seen: set[tuple[str, str, str]] = set()

        for item in evidence:
            key = (item.source, item.entity_type, item.entity_id)

            if key in seen:
                continue

            seen.add(key)

            data = await self._records.get_entity_record(
                item.source,
                item.entity_type,
                item.entity_id,
                self._settlement_id,
            )

            if data is None:
                continue

            records.append(
                EvidenceRecord(
                    source=item.source,
                    entity_type=item.entity_type,
                    entity_id=item.entity_id,
                    data=data,
                )
            )

        return records

    @staticmethod
    def _extract_evidence(
        findings: list[ReconciliationFinding],
    ) -> list[EvidenceRef]:
        evidence: list[EvidenceRef] = []
        seen: set[tuple[str, str, str, str, str | None]] = set()
        covered_entities: set[tuple[str, str, str]] = set()

        def add(item: EvidenceRef) -> None:
            key = (
                item.source,
                item.entity_type,
                item.entity_id,
                item.reason,
                item.object_key,
            )
            if key in seen:
                return
            seen.add(key)
            evidence.append(item)
            covered_entities.add((item.source, item.entity_type, item.entity_id))

        for finding in findings:
            for item in finding.evidence:
                add(item)

        for finding in findings:
            # A finding's own affected_entity is not always repeated inside
            # finding.evidence (checks attach the *other* entities involved
            # in the discrepancy, e.g. the two candidate payments, without
            # re-listing the merchant_order the finding is already anchored
            # on). But that entity's own fields (e.g. its order date) are
            # sometimes exactly the evidence needed to explain the finding's
            # own stated conclusion, so back-fill a record for it -- but only
            # when no real evidence item already covers that same entity
            # (checking that first avoids ever emitting a second EvidenceRef
            # with the same evidence_id but a different/blank object_key).
            entity = finding.affected_entity
            entity_key = (entity.source, entity.entity_type, entity.entity_id)
            if entity_key in covered_entities:
                continue
            add(
                EvidenceRef(
                    evidence_id=f"ev:{entity.source}:{entity.entity_type}:{entity.entity_id}:{finding.code}",
                    source=entity.source,
                    entity_type=entity.entity_type,
                    entity_id=entity.entity_id,
                    reason=finding.code,
                    object_key=None,
                )
            )

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