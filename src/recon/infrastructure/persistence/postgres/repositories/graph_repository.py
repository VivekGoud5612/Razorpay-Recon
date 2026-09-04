from __future__ import annotations

import asyncpg

from recon.application.reconciliation.ports.graph_repository import ReconciliationGraphRepository
from recon.domain.graph.edge import GraphEdge
from recon.domain.graph.graph import ReconciliationGraph
from recon.domain.graph.node import GraphNode


class ReconciliationPostgresGraphRepository(ReconciliationGraphRepository):

    def __init__(self, db) -> None:
        self._db = db

    async def get(
        self,
        settlement_id: str,
    ) -> ReconciliationGraph:
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

    async def save(
        self,
        settlement_id: str,
        graph: ReconciliationGraph,
    ) -> None:
        async with self._db.acquire() as conn:
            async with conn.transaction():
                node_ids = await self._save_nodes(conn, settlement_id, graph)
                await self._save_edges(conn, settlement_id, graph, node_ids)

    async def _save_nodes(
        self,
        conn: asyncpg.Connection,
        settlement_id: str,
        graph: ReconciliationGraph,
    ) -> dict[str, int]:
        rows = await conn.fetch(
            """
            INSERT INTO graph_nodes (
                settlement_id,
                source,
                entity_type,
                entity_id
            )
            SELECT *
            FROM UNNEST(
                $1::text[],
                $2::text[],
                $3::text[],
                $4::text[]
            )
            ON CONFLICT (
                settlement_id,
                source,
                entity_type,
                entity_id
            )
            DO UPDATE SET created_at = graph_nodes.created_at
            RETURNING id, source, entity_type, entity_id
            """,
            [settlement_id] * len(graph.nodes),
            [node.source for node in graph.nodes.values()],
            [node.entity_type for node in graph.nodes.values()],
            [node.entity_id for node in graph.nodes.values()],
        )

        return {
            f"{row['source']}:{row['entity_type']}:{row['entity_id']}": row["id"]
            for row in rows
        }

    async def _save_edges(
        self,
        conn: asyncpg.Connection,
        settlement_id: str,
        graph: ReconciliationGraph,
        node_ids: dict[str, int],
    ) -> None:
        rows = [
            (
                settlement_id,
                node_ids[edge.source_node_id],
                node_ids[edge.target_node_id],
                edge.edge_type,
                "explicit_reference",
                edge.confidence,
            )
            for edge in graph.edges.values()
            if edge.source_node_id in node_ids
            and edge.target_node_id in node_ids
        ]

        if not rows:
            return

        await conn.executemany(
            """
            INSERT INTO graph_edges (
                settlement_id,
                source_node_id,
                target_node_id,
                edge_type,
                evidence_type,
                confidence
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (
                settlement_id,
                source_node_id,
                target_node_id,
                edge_type
            )
            DO UPDATE SET
                evidence_type = EXCLUDED.evidence_type,
                confidence = EXCLUDED.confidence
            """,
            rows,
        )