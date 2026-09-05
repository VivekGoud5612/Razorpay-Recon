import asyncio

from recon.application.investigation.services.evidence_builder import EvidenceBuilder
from recon.domain.graph.edge import GraphEdge
from recon.domain.graph.entity import EntityReference
from recon.domain.graph.graph import ReconciliationGraph
from recon.domain.graph.node import GraphNode
from recon.domain.reconciliation.evidence import EvidenceRef
from recon.domain.reconciliation.finding import ReconciliationFinding


class _FakeRecords:
    """Stand-in for InvestigationRepository.get_entity_record(). These tests
    exercise evidence/graph-traversal wiring, not record content, so no
    entity has a backing record -- build() must tolerate that (records stays
    empty) rather than require it.
    """

    async def get_entity_record(self, source, entity_type, entity_id, settlement_id):
        return None


def _build(graph, findings, depth):
    return asyncio.run(
        EvidenceBuilder(graph, _FakeRecords(), settlement_id="SETL-TEST").build(
            findings=findings, depth=depth
        )
    )


def _node(node_id: str, source: str, entity_type: str, entity_id: str) -> GraphNode:
    return GraphNode(
        node_id=node_id,
        source=source,
        entity_type=entity_type,
        entity_id=entity_id,
    )


def _edge(edge_id: str, source_node_id: str, target_node_id: str, edge_type: str) -> GraphEdge:
    return GraphEdge(
        edge_id=edge_id,
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        edge_type=edge_type,
        source="deterministic",
        confidence=1.0,
    )


def _build_graph() -> ReconciliationGraph:
    # A chain A -> B -> C -> D, plus an unrelated node U with no edges.
    # A is the node the selected finding's evidence points at.
    nodes = {
        n.node_id: n
        for n in [
            _node("merchant:merchant_order:MORD-1", "merchant", "merchant_order", "MORD-1"),  # A
            _node("razorpay:razorpay_order:RZP-1", "razorpay", "razorpay_order", "RZP-1"),  # B
            _node("razorpay:payment:PAY-1", "razorpay", "payment", "PAY-1"),  # C
            _node("razorpay:refund:REF-1", "razorpay", "refund", "REF-1"),  # D (depth 3 from A)
            _node("merchant:ledger_entry:UNRELATED-1", "merchant", "ledger_entry", "UNRELATED-1"),  # U
        ]
    }

    edges = {
        e.edge_id: e
        for e in [
            _edge("e_ab", "merchant:merchant_order:MORD-1", "razorpay:razorpay_order:RZP-1", "REFERENCES_RAZORPAY_ORDER"),
            _edge("e_bc", "razorpay:razorpay_order:RZP-1", "razorpay:payment:PAY-1", "HAS_PAYMENT"),
            _edge("e_cd", "razorpay:payment:PAY-1", "razorpay:refund:REF-1", "HAS_REFUND"),
        ]
    }

    return ReconciliationGraph(nodes=nodes, edges=edges, affected_node_ids=set())


def _finding_for_mord_1() -> ReconciliationFinding:
    evidence = EvidenceRef(
        source="merchant",
        entity_type="merchant_order",
        entity_id="MORD-1",
        evidence_id="ev:merchant:merchant_order:MORD-1:ORDER_AMOUNT_MISMATCH",
        reason="ORDER_AMOUNT_MISMATCH",
        object_key="imports/merchant_orders/imp_1/merchant_orders.csv",
    )

    return ReconciliationFinding(
        finding_id="ORDER_AMOUNT_MISMATCH:merchant_order:MORD-1",
        code="ORDER_AMOUNT_MISMATCH",
        severity="error",
        affected_entity=EntityReference(source="merchant", entity_type="merchant_order", entity_id="MORD-1"),
        message="Amount mismatch for MORD-1",
        evidence=[evidence],
    )


def _unrelated_finding() -> ReconciliationFinding:
    evidence = EvidenceRef(
        source="merchant",
        entity_type="ledger_entry",
        entity_id="UNRELATED-1",
        evidence_id="ev:merchant:ledger_entry:UNRELATED-1:SOME_OTHER_CODE",
        reason="SOME_OTHER_CODE",
        object_key=None,
    )

    return ReconciliationFinding(
        finding_id="SOME_OTHER_CODE:ledger_entry:UNRELATED-1",
        code="SOME_OTHER_CODE",
        severity="warning",
        affected_entity=EntityReference(source="merchant", entity_type="ledger_entry", entity_id="UNRELATED-1"),
        message="Unrelated finding, not selected for investigation",
        evidence=[evidence],
    )


def test_selected_finding_and_its_evidence_are_included():
    graph = _build_graph()
    finding = _finding_for_mord_1()

    package = _build(graph, [finding], 2)

    assert package.findings == [finding]
    assert len(package.evidence) == 1
    assert package.evidence[0].evidence_id == "ev:merchant:merchant_order:MORD-1:ORDER_AMOUNT_MISMATCH"


def test_evidence_ids_remain_stable():
    graph = _build_graph()
    finding = _finding_for_mord_1()

    package = _build(graph, [finding], 2)

    # The evidence_id emitted by the deterministic reconciliation service
    # must survive untouched through the builder (the LLM prompt and the
    # policy both key off this exact string).
    assert package.evidence[0].evidence_id == finding.evidence[0].evidence_id


def test_graph_traversal_uses_the_requested_depth():
    graph = _build_graph()
    finding = _finding_for_mord_1()

    package = _build(graph, [finding], 2)
    node_ids = {n.node_id for n in package.nodes}
    edge_ids = {e.edge_id for e in package.edges}

    # depth=2 from A (merchant_order) reaches B (razorpay_order, depth 1)
    # and C (payment, depth 2), but not D (refund, depth 3).
    assert node_ids == {
        "merchant:merchant_order:MORD-1",
        "razorpay:razorpay_order:RZP-1",
        "razorpay:payment:PAY-1",
    }
    assert edge_ids == {"e_ab", "e_bc"}
    assert "razorpay:refund:REF-1" not in node_ids
    assert "e_cd" not in edge_ids


def test_graph_traversal_depth_is_configurable():
    graph = _build_graph()
    finding = _finding_for_mord_1()

    package = _build(graph, [finding], 3)
    node_ids = {n.node_id for n in package.nodes}

    # With depth=3, D becomes reachable.
    assert "razorpay:refund:REF-1" in node_ids


def test_unrelated_evidence_and_nodes_are_not_pulled_in():
    graph = _build_graph()
    selected = _finding_for_mord_1()
    unrelated = _unrelated_finding()

    # Only `selected` is passed to build() — as InvestigateExceptionUseCase
    # does for the findings the caller actually chose to investigate.
    package = _build(graph, [selected], 2)

    evidence_ids = {e.evidence_id for e in package.evidence}
    node_ids = {n.node_id for n in package.nodes}

    assert unrelated.evidence[0].evidence_id not in evidence_ids
    assert "merchant:ledger_entry:UNRELATED-1" not in node_ids


def test_duplicate_evidence_across_findings_is_deduplicated():
    graph = _build_graph()
    finding = _finding_for_mord_1()
    # A second finding citing the exact same evidence (same source/type/id/
    # reason/object_key) as the first, as can genuinely happen when two
    # deterministic rules flag the same entity for the same reason.
    duplicate = ReconciliationFinding(
        finding_id="OTHER_CODE:merchant_order:MORD-1",
        code="OTHER_CODE",
        severity="error",
        affected_entity=EntityReference(source="merchant", entity_type="merchant_order", entity_id="MORD-1"),
        message="Different finding, same underlying evidence",
        evidence=list(finding.evidence),
    )

    package = _build(graph, [finding, duplicate], 2)

    assert len(package.evidence) == 1


def test_evidence_without_a_matching_graph_node_is_kept_but_does_not_seed_traversal():
    graph = _build_graph()
    evidence = EvidenceRef(
        source="bank",
        entity_type="bank_transaction",
        entity_id="BNK-NOT-IN-GRAPH",
        evidence_id="ev:bank:bank_transaction:BNK-NOT-IN-GRAPH:BANK_TRANSACTION_MISSING",
        reason="BANK_TRANSACTION_MISSING",
        object_key=None,
    )
    finding = ReconciliationFinding(
        finding_id="BANK_TRANSACTION_MISSING:settlement:SETL-1",
        code="BANK_TRANSACTION_MISSING",
        severity="error",
        affected_entity=EntityReference(source="razorpay", entity_type="settlement", entity_id="SETL-1"),
        message="No bank transaction found",
        evidence=[evidence],
    )

    package = _build(graph, [finding], 2)

    # The evidence reference is still reported, plus a back-filled record
    # request for the finding's own affected_entity (the settlement itself),
    # since nothing in finding.evidence already covers that entity.
    assert evidence in package.evidence
    assert len(package.evidence) == 2
    synthetic = next(e for e in package.evidence if e.entity_type == "settlement")
    assert synthetic.entity_id == "SETL-1"
    assert synthetic.reason == "BANK_TRANSACTION_MISSING"
    # ...but since no graph node exists for either, they contribute nothing
    # to the traversal (no crash, no phantom node/edge).
    assert package.nodes == []
    assert package.edges == []


def test_evidence_package_satisfies_investigation_service_input_contract():
    graph = _build_graph()
    finding = _finding_for_mord_1()

    package = _build(graph, [finding], 2)

    # InvestigationService/LLMInvestigator/InvestigationPolicy all read
    # these five fields off the package; each must be present and typed
    # as a list (not None), even when empty.
    assert isinstance(package.findings, list)
    assert isinstance(package.evidence, list)
    assert isinstance(package.records, list)
    assert isinstance(package.nodes, list)
    assert isinstance(package.edges, list)

    # Regression guard: EvidenceBuilder.build() must always pass `records`
    # explicitly — EvidencePackage has no default for it, so omitting the
    # kwarg raises TypeError at construction time.
    assert package.records == []
