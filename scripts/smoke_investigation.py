from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from decimal import Decimal

from dotenv import load_dotenv

from recon.application.investigation.dto.evidence import (
    EvidencePackage,
    EvidenceRecord,
)
from recon.application.investigation.services.investigation_service import InvestigationService
from recon.application.investigation.services.investigation_policy import InvestigationPolicy
from recon.domain.graph.edge import GraphEdge
from recon.domain.graph.entity import EntityReference
from recon.domain.graph.graph import ReconciliationGraph
from recon.domain.graph.node import GraphNode
from recon.domain.reconciliation.evidence import EvidenceRef
from recon.domain.reconciliation.finding import ReconciliationFinding
from recon.infrastructure.ai.huggingface_client import HuggingFaceLLMClient
from recon.infrastructure.investigation.investigator import LLMInvestigator
from recon.infrastructure.investigation.mcp.document_tools import DocumentTools
from recon.infrastructure.storage.minio.object_storage import MinioObjectStorage


OBJECT_KEY = "smoke/investigation/merchant_orders.csv"


def build_smoke_package() -> EvidencePackage:
    merchant_order = {
        "merchant_order_id": "MORD-07-003",
        "razorpay_order_id": "order_test_003",
        "amount": Decimal("5300.00"),
        "currency": "INR",
        "status": "paid",
        "created_at": datetime(2026, 9, 5, 10, 21, tzinfo=timezone.utc),
    }

    razorpay_order = {
        "order_id": "order_test_003",
        "amount": Decimal("5500.00"),
        "currency": "INR",
        "status": "created",
        "created_at": datetime(2026, 9, 5, 10, 20, tzinfo=timezone.utc),
    }

    payment = {
        "payment_id": "pay_test_003",
        "order_id": "order_test_003",
        "amount": Decimal("5500.00"),
        "currency": "INR",
        "status": "captured",
        "captured": True,
        "created_at": datetime(2026, 9, 5, 10, 22, tzinfo=timezone.utc),
        "captured_at": datetime(2026, 9, 5, 10, 23, tzinfo=timezone.utc),
    }

    merchant_node = GraphNode(
        node_id="merchant:merchant_order:MORD-07-003",
        source="merchant",
        entity_type="merchant_order",
        entity_id="MORD-07-003",
    )

    order_node = GraphNode(
        node_id="razorpay:razorpay_order:order_test_003",
        source="razorpay",
        entity_type="razorpay_order",
        entity_id="order_test_003",
    )

    payment_node = GraphNode(
        node_id="razorpay:payment:pay_test_003",
        source="razorpay",
        entity_type="payment",
        entity_id="pay_test_003",
    )

    edges = [
        GraphEdge(
            edge_id=(
                f"{merchant_node.node_id}"
                "->REFERENCES_RAZORPAY_ORDER->"
                f"{order_node.node_id}"
            ),
            source_node_id=merchant_node.node_id,
            target_node_id=order_node.node_id,
            edge_type="REFERENCES_RAZORPAY_ORDER",
            source="merchant",
            confidence=1.0,
        ),
        GraphEdge(
            edge_id=(
                f"{order_node.node_id}"
                "->HAS_PAYMENT->"
                f"{payment_node.node_id}"
            ),
            source_node_id=order_node.node_id,
            target_node_id=payment_node.node_id,
            edge_type="HAS_PAYMENT",
            source="razorpay",
            confidence=1.0,
        ),
    ]

    graph = ReconciliationGraph(
        nodes={
            merchant_node.node_id: merchant_node,
            order_node.node_id: order_node,
            payment_node.node_id: payment_node,
        },
        edges={
            edge.edge_id: edge
            for edge in edges
        },
        affected_node_ids={
            merchant_node.node_id,
            order_node.node_id,
            payment_node.node_id,
        },
    )

    finding = ReconciliationFinding(
        finding_id="ORDER_AMOUNT_MISMATCH:merchant_order:MORD-07-003",
        code="ORDER_AMOUNT_MISMATCH",
        severity="error",
        affected_entity=EntityReference(
            source="merchant",
            entity_type="merchant_order",
            entity_id="MORD-07-003",
        ),
        message=(
            "Merchant order amount is 5300.00 INR while "
            "the associated Razorpay order amount is 5500.00 INR."
        ),
        evidence=[
            EvidenceRef(
                evidence_id="ev_001",
                source="merchant",
                entity_type="merchant_order",
                entity_id="MORD-07-003",
                reason="ORDER_AMOUNT_MISMATCH",
                object_key=OBJECT_KEY,
            ),
            EvidenceRef(
                evidence_id="ev_002",
                source="razorpay",
                entity_type="razorpay_order",
                entity_id="order_test_003",
                reason="ORDER_AMOUNT_MISMATCH",
            ),
        ],
    )

    records = [
        EvidenceRecord(
            source="merchant",
            entity_type="merchant_order",
            entity_id="MORD-07-003",
            data=merchant_order,
        ),
        EvidenceRecord(
            source="razorpay",
            entity_type="razorpay_order",
            entity_id="order_test_003",
            data=razorpay_order,
        ),
        EvidenceRecord(
            source="razorpay",
            entity_type="payment",
            entity_id="pay_test_003",
            data=payment,
        ),
    ]

    return EvidencePackage(
        findings=[finding],
        evidence=finding.evidence,
        records=records,
        nodes=list(graph.nodes.values()),
        edges=list(graph.edges.values()),
    )


async def main() -> None:
    load_dotenv()

    storage = MinioObjectStorage(
        endpoint=os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        bucket_name=os.environ["MINIO_BUCKET"],
        secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
    )

    storage.ensure_bucket()

    document = """merchant_order_id,amount,currency,status
MORD-07-003,5300.00,INR,paid
MORD-07-004,5400.00,INR,paid
"""

    await storage.put(
        object_key=OBJECT_KEY,
        content=document.encode("utf-8"),
        content_type="text/csv",
    )

    print(f"Stored document: {OBJECT_KEY}")

    document_tools = DocumentTools(storage)

    llm_client = HuggingFaceLLMClient(
        api_key=os.environ["HF_TOKEN"],
        model=os.environ["HF_MODEL"],
    )

    investigator = LLMInvestigator(
        client=llm_client,
        document_tools=document_tools,
    )

    service = InvestigationService(
        investigator=investigator,
        policy=InvestigationPolicy(),
    )

    package = build_smoke_package()

    result = await service.investigate(package)

    print("\n=== INVESTIGATION RESULT ===")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())