from recon.domain.graph.edge import GraphEdge
from recon.domain.graph.node import GraphNode


def test_graph_node():
    node = GraphNode(
        node_id="node_001",
        source="razorpay",
        entity_type="payment",
        entity_id="pay_001",
    )

    assert node.node_id == "node_001"
    assert node.source == "razorpay"
    assert node.entity_type == "payment"
    assert node.entity_id == "pay_001"


def test_graph_edge():
    edge = GraphEdge(
        edge_id="edge_001",
        source_node_id="node_payment",
        target_node_id="node_settlement",
        edge_type="settled_in",
        source="deterministic",
        confidence=1.0,
    )

    assert edge.edge_id == "edge_001"
    assert edge.source_node_id == "node_payment"
    assert edge.target_node_id == "node_settlement"
    assert edge.edge_type == "settled_in"
    assert edge.source == "deterministic"
    assert edge.confidence == 1.0