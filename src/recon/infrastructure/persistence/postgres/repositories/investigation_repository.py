from __future__ import annotations

import json

import asyncpg

from recon.application.investigation.dto.response import (
    Hypothesis,
    InvestigationEvidence,
    InvestigationResponse,
    RootCause,
)
from recon.application.investigation.ports.repository import InvestigationRepository
from recon.domain.graph.edge import GraphEdge
from recon.domain.graph.entity import EntityReference
from recon.domain.graph.graph import ReconciliationGraph
from recon.domain.graph.node import GraphNode
from recon.domain.reconciliation.evidence import EvidenceRef
from recon.domain.reconciliation.finding import ReconciliationFinding


class InvestigationPostgresRepository(InvestigationRepository):

    def __init__(self, db) -> None:
        self._db = db

    async def get_graph(self, settlement_id: str) -> ReconciliationGraph:
        async with self._db.acquire() as conn:
            node_rows = await conn.fetch(
                """
                SELECT id, source, entity_type, entity_id
                FROM graph_nodes
                WHERE settlement_id = $1
                """,
                settlement_id,
            )

            edge_rows = await conn.fetch(
                """
                SELECT source_node_id, target_node_id, edge_type, confidence
                FROM graph_edges
                WHERE settlement_id = $1
                """,
                settlement_id,
            )

        nodes = {
            f"{row['source']}:{row['entity_type']}:{row['entity_id']}": GraphNode(
                node_id=f"{row['source']}:{row['entity_type']}:{row['entity_id']}",
                source=row["source"],
                entity_type=row["entity_type"],
                entity_id=row["entity_id"],
            )
            for row in node_rows
        }

        db_id_to_node_id = {
            row["id"]: f"{row['source']}:{row['entity_type']}:{row['entity_id']}"
            for row in node_rows
        }

        edges: dict[str, GraphEdge] = {}

        for row in edge_rows:
            source_node_id = db_id_to_node_id.get(row["source_node_id"])
            target_node_id = db_id_to_node_id.get(row["target_node_id"])

            if source_node_id is None or target_node_id is None:
                continue

            edge = GraphEdge(
                edge_id=f"{source_node_id}->{row['edge_type']}->{target_node_id}",
                source_node_id=source_node_id,
                target_node_id=target_node_id,
                edge_type=row["edge_type"],
                source=nodes[source_node_id].source,
                confidence=float(row["confidence"]),
            )

            edges[edge.edge_id] = edge

        return ReconciliationGraph(
            nodes=nodes,
            edges=edges,
            affected_node_ids=set(nodes),
        )

    async def get_findings(
        self,
        settlement_id: str,
        finding_ids: list[str],
    ) -> list[ReconciliationFinding]:
        if not finding_ids:
            return []

        async with self._db.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    f.finding_id,
                    f.code,
                    f.severity,
                    f.source,
                    f.entity_type,
                    f.entity_id,
                    f.message,
                    e.evidence_id,
                    e.source AS evidence_source,
                    e.entity_type AS evidence_entity_type,
                    e.entity_id AS evidence_entity_id,
                    e.reason,
                    e.object_key
                FROM reconciliation_findings f
                LEFT JOIN reconciliation_finding_evidence fe
                    ON fe.settlement_id = f.settlement_id
                   AND fe.finding_id = f.finding_id
                LEFT JOIN reconciliation_evidence e
                    ON e.settlement_id = fe.settlement_id
                   AND e.evidence_id = fe.evidence_id
                WHERE f.settlement_id = $1
                  AND f.finding_id = ANY($2::text[])
                ORDER BY f.finding_id, e.evidence_id
                """,
                settlement_id,
                finding_ids,
            )

        grouped: dict[str, list[asyncpg.Record]] = {}

        for row in rows:
            grouped.setdefault(row["finding_id"], []).append(row)

        findings: list[ReconciliationFinding] = []

        for finding_id in finding_ids:
            finding_rows = grouped.get(finding_id)

            if not finding_rows:
                continue

            row = finding_rows[0]

            evidence = [
                EvidenceRef(
                    evidence_id=evidence_row["evidence_id"],
                    source=evidence_row["evidence_source"],
                    entity_type=evidence_row["evidence_entity_type"],
                    entity_id=evidence_row["evidence_entity_id"],
                    reason=evidence_row["reason"],
                    object_key=evidence_row["object_key"],
                )
                for evidence_row in finding_rows
                if evidence_row["evidence_id"] is not None
            ]

            findings.append(
                ReconciliationFinding(
                    finding_id=row["finding_id"],
                    code=row["code"],
                    severity=row["severity"],
                    affected_entity=EntityReference(
                        source=row["source"],
                        entity_type=row["entity_type"],
                        entity_id=row["entity_id"],
                    ),
                    message=row["message"],
                    evidence=evidence,
                )
            )

        return findings

    async def save(
        self,
        response: InvestigationResponse,
    ) -> None:
        payload = self._serialize(response)

        async with self._db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO investigations (
                    investigation_id,
                    settlement_id,
                    finding_ids,
                    status,
                    response,
                    created_at
                )
                VALUES ($1, $2, $3, $4, $5::jsonb, COALESCE($6, now()))
                ON CONFLICT (investigation_id)
                DO UPDATE SET
                    status = EXCLUDED.status,
                    response = EXCLUDED.response
                """,
                response.investigation_id,
                response.settlement_id,
                response.finding_ids,
                response.status,
                json.dumps(payload, default=str),
                response.created_at,
            )

    async def get(
        self,
        investigation_id: str,
    ) -> InvestigationResponse | None:
        async with self._db.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    investigation_id,
                    settlement_id,
                    finding_ids,
                    status,
                    response,
                    created_at
                FROM investigations
                WHERE investigation_id = $1
                """,
                investigation_id,
            )

        if row is None:
            return None

        payload = json.loads(row["response"])

        return self._deserialize(
            payload,
            investigation_id=row["investigation_id"],
            settlement_id=row["settlement_id"],
            finding_ids=list(row["finding_ids"]),
            status=row["status"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _serialize(response: InvestigationResponse) -> dict:
        return {
            "factual_observations": response.factual_observations,
            "hypotheses": [
                {
                    "hypothesis_id": item.hypothesis_id,
                    "statement": item.statement,
                    "supporting_evidence_ids": item.supporting_evidence_ids,
                    "confidence": item.confidence,
                }
                for item in response.hypotheses
            ],
            "root_cause": (
                {
                    "hypothesis_id": response.root_cause.hypothesis_id,
                    "confidence": response.root_cause.confidence,
                }
                if response.root_cause is not None
                else None
            ),
            "evidence": [
                {
                    "evidence_id": item.evidence_id,
                    "source": item.source,
                    "entity_type": item.entity_type,
                    "entity_id": item.entity_id,
                    "reason": item.reason,
                    "data": item.data,
                    "object_key": item.object_key,
                }
                for item in response.evidence
            ],
            "missing_evidence": response.missing_evidence,
            "should_abstain": response.should_abstain,
            "abstain_reason": response.abstain_reason,
        }

    @staticmethod
    def _deserialize(
        payload: dict,
        *,
        investigation_id: str,
        settlement_id: str,
        finding_ids: list[str],
        status: str,
        created_at,
    ) -> InvestigationResponse:
        root_cause = payload["root_cause"]

        return InvestigationResponse(
            factual_observations=payload["factual_observations"],
            hypotheses=[
                Hypothesis(
                    hypothesis_id=item["hypothesis_id"],
                    statement=item["statement"],
                    supporting_evidence_ids=item["supporting_evidence_ids"],
                    confidence=item["confidence"],
                )
                for item in payload["hypotheses"]
            ],
            root_cause=(
                RootCause(
                    hypothesis_id=root_cause["hypothesis_id"],
                    confidence=root_cause["confidence"],
                )
                if root_cause is not None
                else None
            ),
            evidence=[
                InvestigationEvidence(
                    evidence_id=item["evidence_id"],
                    source=item["source"],
                    entity_type=item["entity_type"],
                    entity_id=item["entity_id"],
                    reason=item["reason"],
                    data=item["data"],
                    object_key=item["object_key"],
                )
                for item in payload["evidence"]
            ],
            missing_evidence=payload["missing_evidence"],
            should_abstain=payload["should_abstain"],
            abstain_reason=payload["abstain_reason"],
            investigation_id=investigation_id,
            settlement_id=settlement_id,
            finding_ids=finding_ids,
            status=status,
            created_at=created_at,
        )