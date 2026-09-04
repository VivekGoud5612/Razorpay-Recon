from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from recon.application.reconciliation.dto.data import SettlementReconciliationData
from recon.application.reconciliation.dto.response import ReconcileSettlementResponse
from recon.application.reconciliation.graph.relation_rules import RELATION_RULES
from recon.domain.graph.edge import GraphEdge
from recon.domain.graph.graph import ReconciliationGraph
from recon.domain.graph.node import GraphNode


@dataclass(frozen=True, slots=True)
class _EntitySpec:
    source: str
    entity_type: str
    collection: str
    id_field: str


class ReconciliationGraphBuilder:

    _ENTITY_SPECS = (
        _EntitySpec("merchant", "merchant_order", "merchant_orders", "order_id"),
        _EntitySpec("merchant", "ledger_entry", "ledger_entries", "entry_id"),
        _EntitySpec("bank", "bank_transaction", "bank_transactions", "transaction_id"),
        _EntitySpec("merchant", "pos_transaction", "pos_transactions", "transaction_id"),
        _EntitySpec("merchant", "gateway_transaction", "gateway_transactions", "transaction_id"),
        _EntitySpec("razorpay", "razorpay_order", "orders", "order_id"),
        _EntitySpec("razorpay", "payment", "payments", "payment_id"),
        _EntitySpec("razorpay", "refund", "refunds", "refund_id"),
        _EntitySpec("razorpay", "transfer", "transfers", "transfer_id"),
        _EntitySpec("razorpay", "adjustment", "adjustments", "adjustment_id"),
        _EntitySpec("razorpay", "settlement", "settlement", "settlement_id"),
        _EntitySpec("razorpay", "settlement_entry", "settlement_entries", "entry_id"),
    )

    def build(
        self,
        data: SettlementReconciliationData,
        response: ReconcileSettlementResponse,
    ) -> ReconciliationGraph:
        entities = self._entities(data)
        specs = {spec.entity_type: spec for spec in self._ENTITY_SPECS}

        nodes = self._build_nodes(entities, specs)
        node_index = self._build_node_index(nodes)
        field_index = self._build_field_index(entities, specs, node_index)
        edges = self._build_edges(entities, specs, node_index, field_index)
        affected_node_ids = self._affected_nodes(response, nodes)

        return ReconciliationGraph(
            nodes=nodes,
            edges=edges,
            affected_node_ids=affected_node_ids,
        )

    @staticmethod
    def _entities(data: SettlementReconciliationData) -> dict[str, list[Any]]:
        return {
            "merchant_orders": data.merchant_orders,
            "ledger_entries": data.ledger_entries,
            "bank_transactions": data.bank_transactions,
            "pos_transactions": data.pos_transactions,
            "gateway_transactions": data.gateway_transactions,
            "orders": data.orders,
            "payments": data.payments,
            "refunds": data.refunds,
            "transfers": data.transfers,
            "adjustments": data.adjustments,
            "settlement": [data.settlement],
            "settlement_entries": data.settlement_entries,
        }

    @staticmethod
    def _build_nodes(
        entities: dict[str, list[Any]],
        specs: dict[str, _EntitySpec],
    ) -> dict[str, GraphNode]:
        nodes: dict[str, GraphNode] = {}

        for spec in specs.values():
            for entity in entities.get(spec.collection, []):
                entity_id = getattr(entity, spec.id_field)
                node_id = f"{spec.source}:{spec.entity_type}:{entity_id}"

                nodes[node_id] = GraphNode(
                    node_id=node_id,
                    source=spec.source,
                    entity_type=spec.entity_type,
                    entity_id=entity_id,
                )

        return nodes

    @staticmethod
    def _build_node_index(
        nodes: dict[str, GraphNode],
    ) -> dict[tuple[str, str], GraphNode]:
        return {
            (node.entity_type, node.entity_id): node
            for node in nodes.values()
        }

    @staticmethod
    def _build_field_index(
        entities: dict[str, list[Any]],
        specs: dict[str, _EntitySpec],
        node_index: dict[tuple[str, str], GraphNode],
    ) -> dict[tuple[str, str, Any], GraphNode]:
        index: dict[tuple[str, str, Any], GraphNode] = {}

        target_fields: dict[str, set[str]] = {}

        for rule in RELATION_RULES:
            target_fields.setdefault(rule.target_type, set()).add(
                rule.target_field
            )

        for entity_type, fields in target_fields.items():
            spec = specs[entity_type]

            for entity in entities.get(spec.collection, []):
                entity_id = getattr(entity, spec.id_field)
                node = node_index.get((entity_type, entity_id))

                if node is None:
                    continue

                for field in fields:
                    value = getattr(entity, field, None)

                    if value is None:
                        continue

                    index[(entity_type, field, value)] = node

        return index

    @staticmethod
    def _build_edges(
        entities: dict[str, list[Any]],
        specs: dict[str, _EntitySpec],
        node_index: dict[tuple[str, str], GraphNode],
        field_index: dict[tuple[str, str, Any], GraphNode],
    ) -> dict[str, GraphEdge]:
        edges: dict[str, GraphEdge] = {}

        for rule in RELATION_RULES:
            source_spec = specs[rule.source_type]

            for entity in entities.get(source_spec.collection, []):
                source_value = getattr(
                    entity,
                    rule.source_field,
                    None,
                )

                if source_value is None:
                    continue

                source_id = getattr(
                    entity,
                    source_spec.id_field,
                )

                source_node = node_index.get(
                    (rule.source_type, source_id)
                )

                if source_node is None:
                    continue

                target_node = field_index.get(
                    (
                        rule.target_type,
                        rule.target_field,
                        source_value,
                    )
                )

                if target_node is None:
                    continue

                edge = ReconciliationGraphBuilder._edge(
                    source_node,
                    target_node,
                    rule.edge_type,
                )

                edges[edge.edge_id] = edge

        return edges

    @staticmethod
    def _affected_nodes(
        response: ReconcileSettlementResponse,
        nodes: dict[str, GraphNode],
    ) -> set[str]:
        affected: set[str] = set()

        for evidence in response.evidence:
            node_id = (
                f"{evidence.source}:"
                f"{evidence.entity_type}:"
                f"{evidence.entity_id}"
            )

            if node_id in nodes:
                affected.add(node_id)

        return affected

    @staticmethod
    def _edge(
        source: GraphNode,
        target: GraphNode,
        edge_type: str,
    ) -> GraphEdge:
        return GraphEdge(
            edge_id=f"{source.node_id}->{edge_type}->{target.node_id}",
            source_node_id=source.node_id,
            target_node_id=target.node_id,
            edge_type=edge_type,
            source=source.source,
            confidence=1.0,
        )